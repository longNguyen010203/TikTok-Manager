"""Helpers for appending persistent Job logs."""

from typing import Any

from sqlalchemy.orm import Session

from app.models import Job, JobLog


def append_job_log(
    session: Session,
    job: Job,
    level: str,
    message: str,
    metadata: Any | None = None,
) -> JobLog:
    """Append a Job log without committing the surrounding transaction."""
    log = JobLog(
        job=job,
        level=level,
        message=message,
        log_metadata=metadata,
    )
    session.add(log)
    return log
