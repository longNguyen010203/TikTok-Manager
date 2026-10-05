"""Cross-process serialization for one Workflow's transitions."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.services.runtime_operation_lock import (
    RuntimeOperationGuard,
    RuntimeOperationLockBusy,
    RuntimeOperationLockError,
)


class WorkflowOperationLockError(RuntimeOperationLockError):
    pass


class WorkflowOperationLockBusy(WorkflowOperationLockError):
    pass


class WorkflowOperationGuard:
    """Secure host-flock guard with one independent lock per Workflow."""

    def __init__(self, lock_directory: Path, *, poll_interval: float = 0.05) -> None:
        self._guard = RuntimeOperationGuard(lock_directory, poll_interval=poll_interval)
        self.lock_directory = Path(lock_directory)

    @contextmanager
    def acquire_workflow(
        self, workflow_id: int, *, blocking: bool = True, timeout: float | None = None
    ) -> Iterator[None]:
        if isinstance(workflow_id, bool) or not isinstance(workflow_id, int) or workflow_id <= 0:
            raise ValueError("workflow_id must be a positive integer")
        try:
            with self._guard.acquire_named(
                f"workflow-{workflow_id}", blocking=blocking, timeout=timeout
            ):
                yield
        except RuntimeOperationLockBusy as error:
            raise WorkflowOperationLockBusy("Workflow operation is already in progress") from error
        except RuntimeOperationLockError as error:
            raise WorkflowOperationLockError("Workflow lock is unsafe or unavailable") from error

    def is_workflow_busy(self, workflow_id: int) -> bool:
        try:
            with self.acquire_workflow(workflow_id, blocking=False):
                return False
        except WorkflowOperationLockBusy:
            return True
