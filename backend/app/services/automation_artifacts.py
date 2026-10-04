"""Private durable storage for Android automation artifacts."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.config import load_application_config
from app.models import JobArtifact
from app.services.automation_errors import AutomationError, automation_error


_STORAGE_KEY = re.compile(r"^[0-9a-f]{32}$")


class ArtifactConfigurationError(ValueError):
    """Raised when the trusted artifact-store configuration is unsafe."""


class AutomationArtifactStore:
    """Store files beneath one private, manager-owned directory."""

    def __init__(self, root: Path, *, max_size_bytes: int) -> None:
        self.root = Path(root).expanduser()
        if not self.root.is_absolute():
            raise ArtifactConfigurationError("artifact root must be absolute")
        if max_size_bytes <= 0:
            raise ArtifactConfigurationError(
                "artifact maximum size must be greater than zero"
            )
        self.max_size_bytes = max_size_bytes

    @classmethod
    def from_application_config(cls) -> "AutomationArtifactStore":
        config = load_application_config()
        return cls(
            config.artifact_root,
            max_size_bytes=config.artifact_max_size_bytes,
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
        storage_key = uuid.uuid4().hex
        temporary_name = f".incoming-{uuid.uuid4().hex}"
        directory_fd = self._open_root()
        finalized = False
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(temporary_name, flags, 0o600, dir_fd=directory_fd)
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
            expires_at=expires_at,
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
