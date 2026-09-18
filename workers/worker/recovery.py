"""Process-local state for lifecycle reports awaiting recovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

LifecycleAction = Literal["succeed", "fail"]


@dataclass(frozen=True)
class PendingLifecycleReport:
    """A lifecycle report that could not be confirmed by the backend."""

    job: dict[str, Any]
    action: LifecycleAction
    value: Any

    @property
    def job_id(self) -> int:
        return self.job["id"]


class LifecycleRecoveryStore:
    """Keep at most one pending lifecycle report for each job."""

    def __init__(self) -> None:
        self._pending: dict[int, PendingLifecycleReport] = {}

    def add(self, report: PendingLifecycleReport) -> bool:
        """Store a report unless that job already has pending recovery state."""
        if report.job_id in self._pending:
            return False
        self._pending[report.job_id] = report
        return True

    def next(self) -> PendingLifecycleReport | None:
        """Return the oldest pending report, if one exists."""
        return next(iter(self._pending.values()), None)

    def complete(self, job_id: int) -> None:
        """Remove a report after the backend accepts it."""
        self._pending.pop(job_id, None)

    def __len__(self) -> int:
        return len(self._pending)
