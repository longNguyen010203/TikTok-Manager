"""Private durable storage for Android automation artifacts."""

from __future__ import annotations

import hashlib
import fcntl
import os
import re
import stat
import unicodedata
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.config import load_application_config
from app.models import Job, JobArtifact
from app.models.timestamps import utc_now
from app.services.automation_errors import AutomationError, automation_error


_STORAGE_KEY = re.compile(r"^[0-9a-f]{32}$")


class ArtifactConfigurationError(ValueError):
    """Raised when the trusted artifact-store configuration is unsafe."""


class ArtifactCleanupBusy(RuntimeError):
    """Raised when another process already owns artifact maintenance."""


@dataclass(frozen=True)
class ArtifactCleanupResult:
    expired: int
    missing: int
    failed: int
    bytes_released: int
    active_bytes: int


class AutomationArtifactStore:
    """Store files beneath one private, manager-owned directory."""

    def __init__(
        self,
        root: Path,
        *,
        max_size_bytes: int,
        max_total_bytes: int = 1024 * 1024 * 1024,
        retention_days: int = 30,
        upload_retention_days: int = 7,
    ) -> None:
        self.root = Path(root).expanduser()
        if not self.root.is_absolute():
            raise ArtifactConfigurationError("artifact root must be absolute")
        if max_size_bytes <= 0:
            raise ArtifactConfigurationError(
                "artifact maximum size must be greater than zero"
            )
        self.max_size_bytes = max_size_bytes
        if max_total_bytes < max_size_bytes:
            raise ArtifactConfigurationError(
                "artifact total quota must not be smaller than one artifact"
            )
        if retention_days <= 0 or upload_retention_days <= 0:
            raise ArtifactConfigurationError("artifact retention must be positive")
        self.max_total_bytes = max_total_bytes
        self.retention_days = retention_days
        self.upload_retention_days = upload_retention_days

    @classmethod
    def from_application_config(cls) -> "AutomationArtifactStore":
        config = load_application_config()
        return cls(
            config.artifact_root,
            max_size_bytes=config.artifact_max_size_bytes,
            max_total_bytes=config.artifact_max_total_bytes,
            retention_days=config.artifact_retention_days,
            upload_retention_days=config.artifact_upload_retention_days,
        )

    def store_bytes(
        self,
        session: Session,
        *,
        data: bytes,
        kind: str,
        original_filename: str,
        mime_type: str,
        job_id: int | None = None,
        expires_at: datetime | None = None,
    ) -> JobArtifact:
        """Atomically persist bytes and their database metadata."""
        if not isinstance(data, bytes):
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        if len(data) > self.max_size_bytes:
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        safe_name = self.normalize_filename(original_filename)
        if not kind or len(kind) > 50 or not mime_type or len(mime_type) > 255:
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        digest = hashlib.sha256(data).hexdigest()
        if job_id is not None:
            existing = session.scalar(
                select(JobArtifact).where(
                    JobArtifact.job_id == job_id,
                    JobArtifact.kind == kind,
                    JobArtifact.original_filename == safe_name,
                    JobArtifact.size_bytes == len(data),
                    JobArtifact.sha256 == digest,
                    JobArtifact.cleanup_status == "active",
                )
            )
            if existing is not None:
                self.path_for(existing)
                return existing
        self._prepare_root()
        with self.maintenance_lock():
            self._cleanup_locked(session, now=utc_now(), required_bytes=len(data))
            active_bytes = self._active_bytes(session)
            if active_bytes + len(data) > self.max_total_bytes:
                raise automation_error("ARTIFACT_STORAGE_FULL")
            storage_key = uuid.uuid4().hex
            temporary_name = f".incoming-{uuid.uuid4().hex}"
            directory_fd = self._open_root()
            finalized = False
            try:
                flags = (
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | getattr(os, "O_NOFOLLOW", 0)
                )
                descriptor = os.open(
                    temporary_name, flags, 0o600, dir_fd=directory_fd
                )
                try:
                    with os.fdopen(descriptor, "wb", closefd=False) as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                os.replace(
                    temporary_name,
                    storage_key,
                    src_dir_fd=directory_fd,
                    dst_dir_fd=directory_fd,
                )
                finalized = True
            except OSError as error:
                raise automation_error("ARTIFACT_POLICY_VIOLATION") from error
            finally:
                if not finalized:
                    try:
                        os.unlink(temporary_name, dir_fd=directory_fd)
                    except FileNotFoundError:
                        pass
                os.close(directory_fd)

            artifact = JobArtifact(
                job_id=job_id,
                kind=kind,
                original_filename=safe_name,
                storage_key=storage_key,
                mime_type=mime_type,
                size_bytes=len(data),
                sha256=digest,
                expires_at=expires_at or self._default_expiry(kind),
                cleanup_status="active",
            )
            try:
                session.add(artifact)
                session.commit()
                session.refresh(artifact)
            except Exception:
                session.rollback()
                self._unlink_storage_key(storage_key)
                raise
        return artifact

    def cleanup(
        self,
        session: Session,
        *,
        now: datetime | None = None,
        wait: bool = False,
    ) -> ArtifactCleanupResult:
        """Expire eligible bytes while preserving durable artifact metadata."""
        self._prepare_root()
        with self.maintenance_lock(wait=wait):
            return self._cleanup_locked(session, now=now or utc_now())

    @contextmanager
    def maintenance_lock(self, *, wait: bool = True) -> Iterator[None]:
        """Serialize writers and cleanup across backend/timer processes."""
        self._prepare_root()
        directory_fd = self._open_root()
        descriptor: int | None = None
        try:
            descriptor = os.open(
                ".cleanup.lock",
                os.O_RDWR
                | os.O_CREAT
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=directory_fd,
            )
            operation = fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB)
            try:
                fcntl.flock(descriptor, operation)
            except BlockingIOError as error:
                raise ArtifactCleanupBusy(
                    "artifact maintenance is already running"
                ) from error
            yield
        finally:
            if descriptor is not None:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                finally:
                    os.close(descriptor)
            os.close(directory_fd)

    def get(self, session: Session, artifact_id: int) -> JobArtifact:
        """Load an active artifact and verify its backing file is safe."""
        if isinstance(artifact_id, bool) or not isinstance(artifact_id, int) or artifact_id <= 0:
            raise automation_error("ARTIFACT_NOT_FOUND")
        artifact = session.get(JobArtifact, artifact_id)
        if artifact is None or artifact.cleanup_status != "active":
            raise automation_error("ARTIFACT_NOT_FOUND")
        self.path_for(artifact)
        return artifact

    def path_for(self, artifact: JobArtifact) -> Path:
        """Resolve a generated storage key without following symlinks."""
        if not _STORAGE_KEY.fullmatch(artifact.storage_key):
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        self._prepare_root()
        path = self.root / artifact.storage_key
        try:
            info = path.lstat()
        except FileNotFoundError as error:
            raise automation_error("ARTIFACT_NOT_FOUND") from error
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        if info.st_size != artifact.size_bytes or info.st_size > self.max_size_bytes:
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        return path

    @contextmanager
    def staging_path(self) -> Iterator[Path]:
        """Provide a private temporary file for a typed ADB pull."""
        self._prepare_root()
        name = f".pull-{uuid.uuid4().hex}"
        directory_fd = self._open_root()
        try:
            descriptor = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=directory_fd,
            )
            os.close(descriptor)
        finally:
            os.close(directory_fd)
        path = self.root / name
        try:
            yield path
        finally:
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def read_staged(self, path: Path) -> bytes:
        """Read a bounded staging file after verifying containment and type."""
        if path.parent != self.root or not path.name.startswith(".pull-"):
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        try:
            info = path.lstat()
        except FileNotFoundError as error:
            raise automation_error("FILE_TRANSFER_FAILED") from error
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        if info.st_uid != os.getuid():
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        if info.st_size > self.max_size_bytes:
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        os.chmod(path, 0o600)
        with path.open("rb") as stream:
            data = stream.read(self.max_size_bytes + 1)
        if len(data) > self.max_size_bytes:
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        return data

    @staticmethod
    def normalize_filename(filename: str) -> str:
        """Return a safe ASCII display filename, rejecting path syntax."""
        if not isinstance(filename, str):
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        normalized = unicodedata.normalize("NFKC", filename).strip()
        if (
            not normalized
            or normalized in {".", ".."}
            or "/" in normalized
            or "\\" in normalized
            or any(ord(character) < 32 or ord(character) == 127 for character in normalized)
        ):
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", normalized)
        safe = safe.strip(".")
        if not safe:
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        return safe[:255]

    def _prepare_root(self) -> None:
        self._reject_symlink_components()
        try:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            info = self.root.lstat()
        except OSError as error:
            raise ArtifactConfigurationError("artifact root is unavailable") from error
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ArtifactConfigurationError("artifact root must be a real directory")
        if info.st_uid != os.getuid():
            raise ArtifactConfigurationError("artifact root has the wrong owner")
        if stat.S_IMODE(info.st_mode) & 0o077:
            os.chmod(self.root, 0o700)

    def _reject_symlink_components(self) -> None:
        current = self.root
        while True:
            try:
                info = current.lstat()
                if stat.S_ISLNK(info.st_mode):
                    raise ArtifactConfigurationError(
                        "artifact root cannot traverse a symlink"
                    )
            except FileNotFoundError:
                pass
            if current.parent == current:
                return
            current = current.parent

    def _open_root(self) -> int:
        try:
            return os.open(
                self.root,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
        except OSError as error:
            raise ArtifactConfigurationError("artifact root is unsafe") from error

    def _unlink_storage_key(self, storage_key: str) -> None:
        try:
            (self.root / storage_key).unlink()
        except FileNotFoundError:
            pass

    def _cleanup_locked(
        self,
        session: Session,
        *,
        now: datetime,
        required_bytes: int = 0,
    ) -> ArtifactCleanupResult:
        artifacts = list(
            session.scalars(
                select(JobArtifact)
                .where(JobArtifact.cleanup_status == "active")
                .order_by(JobArtifact.created_at, JobArtifact.id)
            )
        )
        active_bytes = sum(artifact.size_bytes for artifact in artifacts)
        expired = missing = failed = released = 0
        for artifact in artifacts:
            over_quota = active_bytes + required_bytes > self.max_total_bytes
            if self._job_is_active(artifact.job):
                continue
            if not over_quota and not self._is_expired(artifact, now):
                continue
            try:
                was_missing = self._delete_managed_file(artifact)
            except AutomationError:
                artifact.cleanup_status = "failed"
                failed += 1
                continue
            artifact.cleanup_status = "expired"
            active_bytes -= artifact.size_bytes
            released += 0 if was_missing else artifact.size_bytes
            if was_missing:
                missing += 1
            else:
                expired += 1
        session.commit()
        return ArtifactCleanupResult(
            expired=expired,
            missing=missing,
            failed=failed,
            bytes_released=released,
            active_bytes=active_bytes,
        )

    def _delete_managed_file(self, artifact: JobArtifact) -> bool:
        if not _STORAGE_KEY.fullmatch(artifact.storage_key):
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        directory_fd = self._open_root()
        try:
            try:
                info = os.stat(
                    artifact.storage_key,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                return True
            if (
                stat.S_ISLNK(info.st_mode)
                or not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077
                or info.st_size != artifact.size_bytes
            ):
                raise automation_error("ARTIFACT_POLICY_VIOLATION")
            os.unlink(artifact.storage_key, dir_fd=directory_fd)
            return False
        finally:
            os.close(directory_fd)

    def _default_expiry(self, kind: str) -> datetime:
        days = (
            self.upload_retention_days
            if kind == "upload"
            else self.retention_days
        )
        return utc_now() + timedelta(days=days)

    def _is_expired(self, artifact: JobArtifact, now: datetime) -> bool:
        deadline = artifact.expires_at
        if deadline is None:
            days = (
                self.upload_retention_days
                if artifact.kind == "upload"
                else self.retention_days
            )
            deadline = artifact.created_at + timedelta(days=days)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return deadline <= now

    @staticmethod
    def _job_is_active(job: Job | None) -> bool:
        return job is not None and job.status in {
            "pending",
            "retrying",
            "running",
            "cancelling",
        }

    @staticmethod
    def _active_bytes(session: Session) -> int:
        return int(
            session.scalar(
                select(func.coalesce(func.sum(JobArtifact.size_bytes), 0)).where(
                    JobArtifact.cleanup_status == "active"
                )
            )
            or 0
        )
