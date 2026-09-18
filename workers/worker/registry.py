"""Job handler registration and dispatch."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

JobHandler = Callable[[Any], Any]


class UnknownJobTypeError(LookupError):
    """Raised when no handler is registered for a job type."""

    def __init__(self, job_type: object) -> None:
        super().__init__(f"no handler registered for job type {job_type!r}")
        self.job_type = job_type


class HandlerRegistry:
    """Map job types to their executable handler functions."""

    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}

    def register(self, job_type: str, handler: JobHandler) -> None:
        """Register one handler for a non-empty job type."""
        if not job_type:
            raise ValueError("job type must not be empty")
        if job_type in self._handlers:
            raise ValueError(f"handler already registered for job type {job_type!r}")
        self._handlers[job_type] = handler

    def get(self, job_type: object) -> JobHandler:
        """Return a registered handler or raise UnknownJobTypeError."""
        if not isinstance(job_type, str):
            raise UnknownJobTypeError(job_type)
        try:
            return self._handlers[job_type]
        except KeyError as error:
            raise UnknownJobTypeError(job_type) from error

    def dispatch(self, job_type: object, payload: Any) -> Any:
        """Invoke the matching handler with a job payload."""
        return self.get(job_type)(payload)
