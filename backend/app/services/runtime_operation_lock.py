"""Cross-process serialization for host-local Runtime mutations."""

from __future__ import annotations

import fcntl
import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class RuntimeOperationLockError(RuntimeError):
    """Base error for an unsafe or unavailable Runtime operation lock."""


class RuntimeOperationLockBusy(RuntimeOperationLockError):
    """Raised when another process currently owns a Runtime operation lock."""


class RuntimeOperationGuard:
    """Serialize operations for one Runtime using secure host ``flock`` files.

    The lock is intentionally host-local. The interface can later be backed by
    PostgreSQL advisory locks without changing its callers.
    """

    def __init__(self, lock_directory: Path, *, poll_interval: float = 0.05) -> None:
        self.lock_directory = Path(lock_directory)
        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than zero")
        self.poll_interval = poll_interval

    @contextmanager
    def acquire_runtime(
        self,
        runtime_id: int,
        *,
        blocking: bool = True,
        timeout: float | None = None,
    ) -> Iterator[None]:
        """Acquire one Runtime lock, optionally waiting for a bounded period."""
        runtime_id = self._validate_runtime_id(runtime_id)
        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be greater than or equal to zero")
        if not blocking and timeout not in {None, 0}:
            raise ValueError("nonblocking lock acquisition cannot have a timeout")
        with self._acquire(
            f"runtime-{runtime_id}.lock",
            blocking=blocking,
            timeout=timeout,
        ):
            yield

    @contextmanager
    def acquire_named(
        self,
        name: str,
        *,
        blocking: bool = True,
        timeout: float | None = None,
    ) -> Iterator[None]:
        """Acquire a trusted internal lock name used by resource allocators."""
        if not name or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-." for character in name):
            raise ValueError("lock name is invalid")
        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be greater than or equal to zero")
        if not blocking and timeout not in {None, 0}:
            raise ValueError("nonblocking lock acquisition cannot have a timeout")
        with self._acquire(f"{name}.lock", blocking=blocking, timeout=timeout):
            yield

    def is_runtime_busy(self, runtime_id: int) -> bool:
        """Return whether a Runtime is locked without disturbing its owner."""
        try:
            with self.acquire_runtime(runtime_id, blocking=False):
                return False
        except RuntimeOperationLockBusy:
            return True

    @contextmanager
    def _acquire(
        self, filename: str, *, blocking: bool, timeout: float | None
    ) -> Iterator[None]:
        self._prepare_directory()
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            directory_fd = os.open(self.lock_directory, directory_flags)
        except OSError as error:
            raise RuntimeOperationLockError(
                "Runtime lock directory is unsafe or unavailable"
            ) from error
        try:
            flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
            try:
                lock_fd = os.open(filename, flags, 0o600, dir_fd=directory_fd)
            except OSError as error:
                raise RuntimeOperationLockError(
                    "Runtime operation lock is unsafe or unavailable"
                ) from error
            try:
                self._validate_lock_file(lock_fd)
                self._flock(lock_fd, blocking=blocking, timeout=timeout)
                try:
                    yield
                finally:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)
        finally:
            os.close(directory_fd)

    def _flock(
        self, descriptor: int, *, blocking: bool, timeout: float | None
    ) -> None:
        if blocking and timeout is None:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            return

        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except BlockingIOError as error:
                if not blocking or deadline is None or time.monotonic() >= deadline:
                    raise RuntimeOperationLockBusy(
                        "Runtime operation is already in progress"
                    ) from error
                time.sleep(min(self.poll_interval, max(0, deadline - time.monotonic())))

    def _prepare_directory(self) -> None:
        try:
            self.lock_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            info = self.lock_directory.lstat()
        except OSError as error:
            raise RuntimeOperationLockError(
                "Runtime lock directory is unavailable"
            ) from error
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise RuntimeOperationLockError(
                "Runtime lock directory must be a real directory"
            )
        if info.st_uid != os.getuid():
            raise RuntimeOperationLockError(
                "Runtime lock directory has the wrong owner"
            )
        if stat.S_IMODE(info.st_mode) & 0o077:
            try:
                os.chmod(self.lock_directory, 0o700)
            except OSError as error:
                raise RuntimeOperationLockError(
                    "Runtime lock directory permissions are unsafe"
                ) from error

    @staticmethod
    def _validate_lock_file(descriptor: int) -> None:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeOperationLockError("Runtime operation lock file is unsafe")
        if stat.S_IMODE(info.st_mode) & 0o077:
            try:
                os.fchmod(descriptor, 0o600)
            except OSError as error:
                raise RuntimeOperationLockError(
                    "Runtime operation lock permissions are unsafe"
                ) from error

    @staticmethod
    def _validate_runtime_id(runtime_id: int) -> int:
        if isinstance(runtime_id, bool) or not isinstance(runtime_id, int) or runtime_id <= 0:
            raise ValueError("runtime_id must be a positive integer")
        return runtime_id
