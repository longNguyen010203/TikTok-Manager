"""Replaceable host flock guard for Runtime network mutations."""

from __future__ import annotations

import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class NetworkOperationLockError(RuntimeError):
    """Base operation lock error."""


class NetworkOperationLockBusy(NetworkOperationLockError):
    """Raised when another process owns the requested lock."""


class RuntimeNetworkOperationGuard:
    """Serialize host-local operations using no-follow lock files.

    The interface is intentionally small so PostgreSQL advisory locking can
    replace this implementation without changing RuntimeNetworkService.
    """

    def __init__(self, lock_directory: Path) -> None:
        self.lock_directory = lock_directory

    @contextmanager
    def acquire_runtime(self, runtime_id: int, *, blocking: bool = True) -> Iterator[None]:
        if runtime_id <= 0:
            raise ValueError("runtime_id must be positive")
        with self._acquire(f"runtime-{runtime_id}.lock", blocking=blocking):
            yield

    @contextmanager
    def acquire_allocation(self, *, blocking: bool = True) -> Iterator[None]:
        with self._acquire("bridge-port-allocation.lock", blocking=blocking):
            yield

    @contextmanager
    def _acquire(self, filename: str, *, blocking: bool) -> Iterator[None]:
        self._prepare_directory()
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            directory_fd = os.open(self.lock_directory, directory_flags)
        except OSError as error:
            raise NetworkOperationLockError("network lock directory is unsafe or unavailable") from error
        try:
            flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
            try:
                lock_fd = os.open(filename, flags, 0o600, dir_fd=directory_fd)
            except OSError as error:
                raise NetworkOperationLockError("network operation lock is unsafe or unavailable") from error
            try:
                operation = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
                try:
                    fcntl.flock(lock_fd, operation)
                except BlockingIOError as error:
                    raise NetworkOperationLockBusy("Runtime network operation is already in progress") from error
                try:
                    yield
                finally:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)
        finally:
            os.close(directory_fd)

    def _prepare_directory(self) -> None:
        try:
            self.lock_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            info = self.lock_directory.lstat()
        except OSError as error:
            raise NetworkOperationLockError("network lock directory is unavailable") from error
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise NetworkOperationLockError("network lock directory must be a real directory")

