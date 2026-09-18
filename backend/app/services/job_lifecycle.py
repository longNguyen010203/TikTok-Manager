"""Job claiming and lifecycle transition services."""

from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.models import Job, JobStatus
from app.models.timestamps import utc_now
from app.services.job_logs import append_job_log


class InvalidJobTransitionError(ValueError):
    """Raised when a job cannot move from its current status to a target status."""

    def __init__(self, current_status: str, target_status: JobStatus) -> None:
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Cannot transition job from {current_status} to {target_status.value}"
        )


class JobRetryLimitError(ValueError):
    """Raised when a failed job has no remaining execution attempts."""

    def __init__(self, attempt_count: int, max_attempts: int) -> None:
        self.attempt_count = attempt_count
        self.max_attempts = max_attempts
        super().__init__(
            f"Job has reached maximum attempts ({attempt_count}/{max_attempts})"
        )


def claim_next_job(session: Session, now: datetime | None = None) -> Job | None:
    """Claim the oldest pending job that is due for execution."""
    claimed_at = now or utc_now()
    eligibility = or_(
        Job.scheduled_at.is_(None), Job.scheduled_at <= claimed_at
    )

    while True:
        job = session.scalar(
            select(Job)
            .where(
                Job.status == JobStatus.PENDING.value,
                eligibility,
            )
            .order_by(Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None

        claim_result = session.execute(
            update(Job)
            .where(
                Job.id == job.id,
                Job.status == JobStatus.PENDING.value,
                eligibility,
            )
            .values(
                status=JobStatus.RUNNING.value,
                started_at=claimed_at,
                attempt_count=Job.attempt_count + 1,
            )
            .execution_options(synchronize_session=False)
        )
        if claim_result.rowcount == 1:
            session.refresh(job)
            append_job_log(
                session,
                job,
                level="info",
                message="Job claimed",
                metadata={"attempt_count": job.attempt_count},
            )
            session.commit()
            session.refresh(job)
            return job

        session.rollback()


def mark_job_succeeded(
    session: Session, job: Job, result: object | None = None
) -> Job:
    """Complete a running job successfully."""
    _require_status(job, JobStatus.SUCCEEDED, {JobStatus.RUNNING})
    job.status = JobStatus.SUCCEEDED.value
    job.result = result
    job.completed_at = utc_now()
    append_job_log(session, job, level="info", message="Job succeeded")
    session.commit()
    session.refresh(job)
    return job


def mark_job_failed(
    session: Session, job: Job, error_message: str | None = None
) -> Job:
    """Complete a running job unsuccessfully."""
    _require_status(job, JobStatus.FAILED, {JobStatus.RUNNING})
    job.status = JobStatus.FAILED.value
    job.error_message = error_message
    job.completed_at = utc_now()
    append_job_log(
        session,
        job,
        level="error",
        message="Job failed",
        metadata={"error_message": error_message},
    )
    session.commit()
    session.refresh(job)
    return job


def cancel_job(session: Session, job: Job) -> Job:
    """Cancel a pending, running, or retrying job."""
    _require_status(
        job,
        JobStatus.CANCELLED,
        {JobStatus.PENDING, JobStatus.RUNNING, JobStatus.RETRYING},
    )
    job.status = JobStatus.CANCELLED.value
    job.completed_at = utc_now()
    append_job_log(session, job, level="info", message="Job cancelled")
    session.commit()
    session.refresh(job)
    return job


def retry_failed_job(
    session: Session, job: Job, scheduled_at: datetime | None = None
) -> Job:
    """Requeue a failed job without consuming another attempt until claimed."""
    _require_status(job, JobStatus.RETRYING, {JobStatus.FAILED})
    if job.attempt_count >= job.max_attempts:
        raise JobRetryLimitError(job.attempt_count, job.max_attempts)

    job.status = JobStatus.RETRYING.value
    session.flush()

    job.status = JobStatus.PENDING.value
    job.scheduled_at = scheduled_at
    job.started_at = None
    job.completed_at = None
    job.result = None
    job.error_message = None
    append_job_log(
        session,
        job,
        level="info",
        message="Job retry scheduled",
        metadata={
            "scheduled_at": scheduled_at.isoformat()
            if scheduled_at is not None
            else None,
            "attempt_count": job.attempt_count,
        },
    )
    session.commit()
    session.refresh(job)
    return job


def _require_status(
    job: Job, target_status: JobStatus, allowed_statuses: set[JobStatus]
) -> None:
    if job.status not in {status.value for status in allowed_statuses}:
        raise InvalidJobTransitionError(job.status, target_status)
