"""Backward-compatible names for the shared Runtime operation guard."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from app.services.runtime_operation_lock import (
    RuntimeOperationGuard,
    RuntimeOperationLockBusy,
    RuntimeOperationLockError,
)

NetworkOperationLockError = RuntimeOperationLockError
NetworkOperationLockBusy = RuntimeOperationLockBusy


class RuntimeNetworkOperationGuard(RuntimeOperationGuard):
    """Compatibility wrapper retained for existing network service callers."""

    @contextmanager
    def acquire_allocation(self, *, blocking: bool = True) -> Iterator[None]:
        with self.acquire_named("bridge-port-allocation", blocking=blocking):
            yield
