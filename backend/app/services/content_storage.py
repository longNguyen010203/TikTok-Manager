"""Private streaming storage for reusable, deduplicated content blobs."""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
import stat
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO, Iterator

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import load_application_config
from app.models import ContentAssetVersion, ContentBlob, ContentVariant
from app.models.timestamps import utc_now
from app.services.content_validation import DetectedContent


_STORAGE_KEY = re.compile(r"^[0-9a-f]{32}$")
_STAGING_KEY = re.compile(r"^\.upload-[0-9a-f]{32}$")


class ContentStorageError(RuntimeError):
    def __init__(self, code: str, safe_message: str) -> None:
        self.code = code
        self.safe_message = safe_message
        super().__init__(safe_message)


class ContentMaintenanceBusy(ContentStorageError):
    def __init__(self) -> None:
        super().__init__("CONTENT_STORAGE_BUSY", "Content storage is busy")


@dataclass(frozen=True)
class StagedContent:
    name: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class BlobMaterialization:
    blob: ContentBlob
    created: bool
    installed_storage_key: str | None


@dataclass(frozen=True)
class ContentReconciliationResult:
    removed_staging_files: int
    missing_blobs: int
    orphaned_rows: int
    uncertain_files: tuple[str, ...]


class ContentStorageService:
    """Manage only generated files below one private content root."""

    def __init__(self, root: Path, *, max_upload_bytes: int, max_total_bytes: int) -> None:
        self.root = Path(root).expanduser()
        self.blobs = self.root / "blobs"
        self.staging = self.root / "staging"
        if not self.root.is_absolute():
            raise ContentStorageError("CONTENT_STORAGE_UNSAFE", "Content root must be absolute")
        if max_upload_bytes <= 0 or max_total_bytes < max_upload_bytes:
            raise ContentStorageError("CONTENT_STORAGE_INVALID", "Content storage limits are invalid")
        self.max_upload_bytes = max_upload_bytes
        self.max_total_bytes = max_total_bytes

    @classmethod
    def from_application_config(cls) -> "ContentStorageService":
        config = load_application_config()
        return cls(
            config.content_root,
            max_upload_bytes=config.content_max_upload_bytes,
            max_total_bytes=config.content_max_total_bytes,
        )

    def stage_stream(self, stream: BinaryIO) -> StagedContent:
        """Stream a bounded upload to a private file while hashing it."""
        self.prepare()
        name = f".upload-{uuid.uuid4().hex}"
        staging_fd = self._open_directory(self.staging)
        descriptor: int | None = None
        size = 0
        digest = hashlib.sha256()
        try:
            descriptor = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=staging_fd,
            )
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                if not isinstance(chunk, bytes):
                    raise ContentStorageError("INVALID_CONTENT_UPLOAD", "Content upload is invalid")
                size += len(chunk)
                if size > self.max_upload_bytes:
                    raise ContentStorageError(
                        "CONTENT_UPLOAD_TOO_LARGE", "Content exceeds the configured upload limit"
                    )
                digest.update(chunk)
                view = memoryview(chunk)
                while view:
                    written = os.write(descriptor, view)
                    view = view[written:]
            if size == 0:
                raise ContentStorageError("EMPTY_CONTENT", "Content file must not be empty")
            os.fsync(descriptor)
            os.fsync(staging_fd)
            return StagedContent(name=name, sha256=digest.hexdigest(), size_bytes=size)
        except Exception:
            try:
                os.unlink(name, dir_fd=staging_fd)
            except FileNotFoundError:
                pass
            raise
        finally:
            if descriptor is not None:
                os.close(descriptor)
            os.close(staging_fd)

    def read_header(self, staged: StagedContent, maximum: int = 65536) -> bytes:
        descriptor = self._open_staged(staged)
        try:
            return os.read(descriptor, maximum)
        finally:
            os.close(descriptor)

    @contextmanager
    def maintenance_lock(self, *, wait: bool = True) -> Iterator[None]:
        self.prepare()
        root_fd = self._open_directory(self.root)
        descriptor: int | None = None
        try:
            descriptor = os.open(
                ".maintenance.lock",
                os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=root_fd,
            )
            operation = fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB)
            try:
                fcntl.flock(descriptor, operation)
            except BlockingIOError as error:
                raise ContentMaintenanceBusy() from error
            self._validate_private_regular_file(descriptor)
            yield
        finally:
            if descriptor is not None:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                finally:
                    os.close(descriptor)
            os.close(root_fd)

    def materialize_blob(
        self, session: Session, staged: StagedContent, detected: DetectedContent
    ) -> BlobMaterialization:
        """Reuse a digest or atomically install one new physical blob.

        The caller must hold ``maintenance_lock`` through its database commit.
        """
        existing = session.scalar(select(ContentBlob).where(ContentBlob.sha256 == staged.sha256))
        if existing is not None:
            if existing.status != "active":
                raise ContentStorageError(
                    "CONTENT_BLOB_UNAVAILABLE", "Existing content blob is unavailable"
                )
            self.path_for(existing)
            self.discard_staged(staged)
            return BlobMaterialization(existing, False, None)

        active_bytes = int(
            session.scalar(
                select(func.coalesce(func.sum(ContentBlob.size_bytes), 0)).where(
                    ContentBlob.status.in_(["active", "orphaned"])
                )
            )
            or 0
        )
        if active_bytes + staged.size_bytes > self.max_total_bytes:
            raise ContentStorageError(
                "CONTENT_STORAGE_FULL", "Content storage quota is full"
            )

        storage_key = uuid.uuid4().hex
        staging_fd = self._open_directory(self.staging)
        blobs_fd = self._open_directory(self.blobs)
        try:
            os.rename(
                staged.name,
                storage_key,
                src_dir_fd=staging_fd,
                dst_dir_fd=blobs_fd,
            )
            os.fsync(blobs_fd)
        except OSError as error:
            raise ContentStorageError(
                "CONTENT_STORAGE_UNAVAILABLE", "Content could not be stored"
            ) from error
        finally:
            os.close(staging_fd)
            os.close(blobs_fd)

        blob = ContentBlob(
            storage_key=storage_key,
            sha256=staged.sha256,
            size_bytes=staged.size_bytes,
            detected_mime_type=detected.mime_type,
            status="active",
            verified_at=utc_now(),
        )
        session.add(blob)
        try:
            session.flush()
        except Exception:
            # The rename and SQLite transaction cannot be atomic. This key was
            # generated by this operation and is therefore safe to compensate.
            self.remove_installed(storage_key)
            raise
        return BlobMaterialization(blob, True, storage_key)

    def path_for(self, blob: ContentBlob) -> Path:
        if not _STORAGE_KEY.fullmatch(blob.storage_key):
            raise ContentStorageError("CONTENT_STORAGE_UNSAFE", "Content blob identity is invalid")
        self.prepare()
        blobs_fd = self._open_directory(self.blobs)
        try:
            descriptor = os.open(
                blob.storage_key,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=blobs_fd,
            )
            try:
                info = os.fstat(descriptor)
                self._validate_private_regular_info(info)
                if info.st_size != blob.size_bytes:
                    raise ContentStorageError(
                        "CONTENT_BLOB_INVALID", "Content blob failed integrity validation"
                    )
            finally:
                os.close(descriptor)
        except FileNotFoundError as error:
            raise ContentStorageError("CONTENT_BLOB_MISSING", "Content blob is unavailable") from error
        except OSError as error:
            raise ContentStorageError("CONTENT_STORAGE_UNSAFE", "Content blob is unsafe") from error
        finally:
            os.close(blobs_fd)
        return self.blobs / blob.storage_key

    def verify_blob(self, blob: ContentBlob) -> Path:
        """Verify exact managed bytes against immutable size and digest metadata."""
        path = self.path_for(blob)
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        digest = hashlib.sha256()
        size = 0
        try:
            self._validate_private_regular_file(descriptor)
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                digest.update(chunk)
        finally:
            os.close(descriptor)
        if size != blob.size_bytes or digest.hexdigest() != blob.sha256:
            raise ContentStorageError(
                "CONTENT_BLOB_INVALID", "Content blob failed integrity validation"
            )
        return path

    def discard_staged(self, staged: StagedContent) -> None:
        if not _STAGING_KEY.fullmatch(staged.name):
            raise ContentStorageError("CONTENT_STORAGE_UNSAFE", "Staging identity is invalid")
        staging_fd = self._open_directory(self.staging)
        try:
            try:
                os.unlink(staged.name, dir_fd=staging_fd)
            except FileNotFoundError:
                pass
        finally:
            os.close(staging_fd)

    def remove_installed(self, storage_key: str) -> None:
        """Compensate only a newly installed, generated blob after DB failure."""
        if not _STORAGE_KEY.fullmatch(storage_key):
            raise ContentStorageError("CONTENT_STORAGE_UNSAFE", "Content blob identity is invalid")
        blobs_fd = self._open_directory(self.blobs)
        try:
            try:
                info = os.stat(storage_key, dir_fd=blobs_fd, follow_symlinks=False)
                self._validate_private_regular_info(info)
                os.unlink(storage_key, dir_fd=blobs_fd)
                os.fsync(blobs_fd)
            except FileNotFoundError:
                pass
        finally:
            os.close(blobs_fd)

    def reconcile(
        self,
        session: Session,
        *,
        now: datetime | None = None,
        staging_age: timedelta = timedelta(hours=24),
    ) -> ContentReconciliationResult:
        """Repair proven metadata state and report, but never delete, uncertain blobs."""
        current = now or datetime.now(timezone.utc)
        removed = missing = orphaned = 0
        uncertain: list[str] = []
        with self.maintenance_lock():
            for entry in self.staging.iterdir():
                try:
                    info = entry.lstat()
                except FileNotFoundError:
                    continue
                age = current.timestamp() - info.st_mtime
                if (
                    _STAGING_KEY.fullmatch(entry.name)
                    and stat.S_ISREG(info.st_mode)
                    and not stat.S_ISLNK(info.st_mode)
                    and info.st_uid == os.getuid()
                    and stat.S_IMODE(info.st_mode) & 0o077 == 0
                    and age >= staging_age.total_seconds()
                ):
                    entry.unlink()
                    removed += 1
                else:
                    uncertain.append(f"staging:{entry.name}")

            rows = list(session.scalars(select(ContentBlob)))
            known = {row.storage_key for row in rows}
            referenced = set(
                session.scalars(select(ContentAssetVersion.blob_id)).all()
            ) | set(
                value for value in session.scalars(select(ContentVariant.blob_id)).all()
                if value is not None
            )
            for blob in rows:
                path = self.blobs / blob.storage_key
                try:
                    info = path.lstat()
                except FileNotFoundError:
                    if blob.status in {"active", "orphaned"}:
                        blob.status = "missing"
                        blob.verified_at = current
                        missing += 1
                    continue
                if (
                    stat.S_ISLNK(info.st_mode)
                    or not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) & 0o077
                    or info.st_size != blob.size_bytes
                ):
                    uncertain.append(f"blob:{blob.storage_key}")
                elif blob.status == "active" and blob.id not in referenced:
                    blob.status = "orphaned"
                    orphaned += 1
            for entry in self.blobs.iterdir():
                if entry.name not in known:
                    uncertain.append(f"blob:{entry.name}")
            session.commit()
        return ContentReconciliationResult(removed, missing, orphaned, tuple(sorted(uncertain)))

    def prepare(self) -> None:
        self._reject_symlink_components(self.root)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._validate_private_directory(self.root)
        for directory in (self.blobs, self.staging):
            directory.mkdir(mode=0o700, exist_ok=True)
            self._validate_private_directory(directory)

    def _open_staged(self, staged: StagedContent) -> int:
        if not _STAGING_KEY.fullmatch(staged.name):
            raise ContentStorageError("CONTENT_STORAGE_UNSAFE", "Staging identity is invalid")
        staging_fd = self._open_directory(self.staging)
        try:
            descriptor = os.open(
                staged.name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=staging_fd,
            )
            self._validate_private_regular_file(descriptor)
            if os.fstat(descriptor).st_size != staged.size_bytes:
                os.close(descriptor)
                raise ContentStorageError("CONTENT_STORAGE_UNSAFE", "Staged content changed")
            return descriptor
        finally:
            os.close(staging_fd)

    @staticmethod
    def _reject_symlink_components(path: Path) -> None:
        current = path
        while True:
            try:
                if stat.S_ISLNK(current.lstat().st_mode):
                    raise ContentStorageError(
                        "CONTENT_STORAGE_UNSAFE", "Content root cannot traverse a symlink"
                    )
            except FileNotFoundError:
                pass
            if current.parent == current:
                return
            current = current.parent

    @staticmethod
    def _validate_private_directory(path: Path) -> None:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise ContentStorageError("CONTENT_STORAGE_UNSAFE", "Content directory is unsafe")
        if stat.S_IMODE(info.st_mode) & 0o077:
            os.chmod(path, 0o700)

    @staticmethod
    def _validate_private_regular_info(info: os.stat_result) -> None:
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077
        ):
            raise ContentStorageError("CONTENT_STORAGE_UNSAFE", "Content file is unsafe")

    def _validate_private_regular_file(self, descriptor: int) -> None:
        self._validate_private_regular_info(os.fstat(descriptor))

    @staticmethod
    def _open_directory(path: Path) -> int:
        try:
            return os.open(
                path,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            )
        except OSError as error:
            raise ContentStorageError("CONTENT_STORAGE_UNSAFE", "Content directory is unsafe") from error
