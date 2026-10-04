"""Secure cross-process locks for authoritative content-version processing."""

from __future__ import annotations

import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class ContentOperationLockError(RuntimeError):
    pass


class ContentOperationLockBusy(ContentOperationLockError):
    pass


class ContentVersionOperationGuard:
    def __init__(self, lock_directory: Path) -> None:
        self.lock_directory = Path(lock_directory)

    @contextmanager
    def acquire(self, version_id: int, *, blocking: bool = False) -> Iterator[None]:
        if isinstance(version_id, bool) or not isinstance(version_id, int) or version_id <= 0:
            raise ValueError("version_id must be a positive integer")
        self._prepare()
        directory_fd = os.open(
            self.lock_directory,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        descriptor: int | None = None
        try:
            descriptor = os.open(
                f"content-version-{version_id}.lock",
                os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=directory_fd,
            )
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise ContentOperationLockError("Content inspection lock is unsafe")
            if stat.S_IMODE(info.st_mode) & 0o077:
                os.fchmod(descriptor, 0o600)
            try:
                fcntl.flock(
                    descriptor,
                    fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB),
                )
            except BlockingIOError as error:
                raise ContentOperationLockBusy("Content version is already processing") from error
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        except OSError as error:
            raise ContentOperationLockError("Content inspection lock is unavailable") from error
        finally:
            if descriptor is not None:
                os.close(descriptor)
            os.close(directory_fd)

    def _prepare(self) -> None:
        current = self.lock_directory
        while True:
            try:
                if stat.S_ISLNK(current.lstat().st_mode):
                    raise ContentOperationLockError(
                        "Content inspection lock directory is unsafe"
                    )
            except FileNotFoundError:
                pass
            if current.parent == current:
                break
            current = current.parent
        self.lock_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.lock_directory.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ContentOperationLockError("Content inspection lock directory is unsafe")
        if info.st_uid != os.getuid():
            raise ContentOperationLockError("Content inspection lock directory has wrong owner")
        if stat.S_IMODE(info.st_mode) & 0o077:
            os.chmod(self.lock_directory, 0o700)
