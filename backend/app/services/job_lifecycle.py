"""Durable job claims, leases, retries, and cancellation transitions."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.models import Job, JobStatus
from app.models.timestamps import utc_now
from app.services.device_jobs import get_device_job_definition
from app.services.job_logs import append_job_log

DEFAULT_LEASE_DURATION = timedelta(seconds=60)
DEFAULT_RETRY_DELAY = timedelta(seconds=5)


@dataclass(frozen=True)
class ClaimedJob:
    job: Job
    claim_token: str


class InvalidJobTransitionError(ValueError):
    def __init__(self, current_status: str, target_status: JobStatus) -> None:
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(f"Cannot transition job from {current_status} to {target_status.value}")


class JobRetryLimitError(ValueError):
    def __init__(self, attempt_count: int, max_attempts: int) -> None:
        self.attempt_count = attempt_count
        self.max_attempts = max_attempts
        super().__init__(f"Job has reached maximum attempts ({attempt_count}/{max_attempts})")


class JobClaimOwnershipError(ValueError):
    """The supplied worker claim is stale, invalid, or expired."""


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _clear_claim(job: Job) -> None:
    job.claim_token_hash = None
    job.claimed_by = None
    job.claimed_at = None
    job.heartbeat_at = None
    job.lease_expires_at = None


def validate_job_claim(job: Job, claim_token: str, attempt: int, *, now: datetime | None = None, require_live_lease: bool = True) -> None:
    current = now or utc_now()
    if (not claim_token or job.claim_token_hash is None or
            not hmac.compare_digest(job.claim_token_hash, _token_hash(claim_token)) or
            job.attempt_count != attempt or
            job.status not in {JobStatus.RUNNING.value, JobStatus.CANCELLING.value}):
        raise JobClaimOwnershipError("Job claim is stale or invalid")
    if require_live_lease and (job.lease_expires_at is None or _aware(job.lease_expires_at) <= _aware(current)):
        raise JobClaimOwnershipError("Job claim lease has expired")


def recover_expired_jobs(session: Session, *, now: datetime | None = None, retry_delay: timedelta = DEFAULT_RETRY_DELAY) -> int:
    current = now or utc_now()
    jobs = list(session.scalars(select(Job).where(
        Job.status.in_([JobStatus.RUNNING.value, JobStatus.CANCELLING.value]),
        Job.lease_expires_at.is_not(None), Job.lease_expires_at <= current,
    )).all())
    for job in jobs:
        append_job_log(session, job, level="warning", event_type="worker_lease_expired", message="Worker lease expired")
        definition = get_device_job_definition(job.job_type, required=False)
        safe_to_retry = job.execution_started_at is None or (definition is not None and definition.idempotency == "safe")
        if job.status == JobStatus.CANCELLING.value:
            job.status = JobStatus.CANCELLED.value
            job.completed_at = current
            append_job_log(session, job, level="info", event_type="automation_cancelled", message="Job cancellation completed after lease expiry")
        elif safe_to_retry and job.attempt_count < job.max_attempts:
            job.status = JobStatus.PENDING.value
            job.scheduled_at = current + retry_delay
            job.started_at = None
            job.execution_started_at = None
            job.execution_stage = "retry_scheduled"
            append_job_log(session, job, level="info", event_type="retry_scheduled", message="Job retry scheduled", metadata={"attempt_count": job.attempt_count})
        else:
            job.status = JobStatus.FAILED.value
            job.error_code = "WORKER_LEASE_EXPIRED"
            job.error_message = "Worker lease expired after execution may have started"
            job.error_retryable = False
            job.completed_at = current
        _clear_claim(job)
    if jobs:
        session.commit()
    return len(jobs)


def claim_next_job(session: Session, now: datetime | None = None, *, claimed_by: str = "legacy-worker", lease_duration: timedelta = DEFAULT_LEASE_DURATION) -> ClaimedJob | None:
    claimed_at = now or utc_now()
    recover_expired_jobs(session, now=claimed_at)
    eligibility = or_(Job.scheduled_at.is_(None), Job.scheduled_at <= claimed_at)
    while True:
        job = session.scalar(select(Job).where(Job.status == JobStatus.PENDING.value, eligibility).order_by(Job.id).limit(1).with_for_update(skip_locked=True))
        if job is None:
            return None
        token = secrets.token_urlsafe(32)
        result = session.execute(update(Job).where(Job.id == job.id, Job.status == JobStatus.PENDING.value, eligibility).values(
            status=JobStatus.RUNNING.value, started_at=claimed_at, attempt_count=Job.attempt_count + 1,
            claim_token_hash=_token_hash(token), claimed_by=claimed_by, claimed_at=claimed_at,
            heartbeat_at=claimed_at, lease_expires_at=claimed_at + lease_duration,
            execution_stage="claimed", cancellation_requested_at=None,
            error_code=None, error_message=None, error_retryable=None,
        ).execution_options(synchronize_session=False))
        if result.rowcount == 1:
            session.refresh(job)
            append_job_log(session, job, level="info", event_type="job_claimed", message="Job claimed", metadata={"attempt_count": job.attempt_count, "claimed_by": claimed_by})
            session.commit(); session.refresh(job)
            return ClaimedJob(job, token)
        session.rollback()


def heartbeat_job(session: Session, job: Job, claim_token: str, attempt: int, *, now: datetime | None = None, lease_duration: timedelta = DEFAULT_LEASE_DURATION) -> Job:
    current = now or utc_now()
    validate_job_claim(job, claim_token, attempt, now=current)
    job.heartbeat_at = current
    job.lease_expires_at = current + lease_duration
    append_job_log(session, job, level="debug", event_type="worker_heartbeat", message="Worker lease renewed")
    session.commit(); session.refresh(job)
    return job


def mark_job_succeeded(session: Session, job: Job, claim_token: str, attempt: int, result: object | None = None) -> Job:
    validate_job_claim(job, claim_token, attempt)
    if job.status == JobStatus.CANCELLING.value:
        raise InvalidJobTransitionError(job.status, JobStatus.SUCCEEDED)
    job.status = JobStatus.SUCCEEDED.value
    job.result = result
    job.completed_at = utc_now()
    job.execution_stage = "completed"
    _clear_claim(job)
    append_job_log(session, job, level="info", event_type="action_completed", message="Job succeeded")
    session.commit(); session.refresh(job)
    return job


def mark_job_failed(session: Session, job: Job, claim_token: str, attempt: int, *, error_message: str | None = None, error_code: str | None = None, retryable: bool = False) -> Job:
    validate_job_claim(job, claim_token, attempt)
    definition = get_device_job_definition(job.job_type, required=False)
    policy_allows = definition is None or error_code in definition.retryable_codes
    should_retry = retryable and policy_allows and job.attempt_count < job.max_attempts
    job.error_code = error_code or "JOB_EXECUTION_FAILED"
    job.error_message = error_message or "Job execution failed"
    job.error_retryable = retryable
    append_job_log(session, job, level="error", event_type="action_failed", message="Job action failed", metadata={"error_code": job.error_code, "retryable": retryable})
    if should_retry:
        job.status = JobStatus.PENDING.value
        job.scheduled_at = utc_now() + DEFAULT_RETRY_DELAY
        job.started_at = None
        job.execution_started_at = None
        job.execution_stage = "retry_scheduled"
        append_job_log(session, job, level="info", event_type="retry_scheduled", message="Job retry scheduled", metadata={"attempt_count": job.attempt_count})
    else:
        job.status = JobStatus.FAILED.value
        job.completed_at = utc_now()
        job.execution_stage = "failed"
    _clear_claim(job)
    session.commit(); session.refresh(job)
    return job


def cancel_job(session: Session, job: Job) -> Job:
    _require_status(job, JobStatus.CANCELLED, {JobStatus.PENDING, JobStatus.RUNNING, JobStatus.RETRYING, JobStatus.CANCELLING})
    if job.status in {JobStatus.RUNNING.value, JobStatus.CANCELLING.value}:
        job.status = JobStatus.CANCELLING.value
        job.cancellation_requested_at = job.cancellation_requested_at or utc_now()
        job.execution_stage = "cancellation_requested"
        append_job_log(session, job, level="info", event_type="cancellation_requested", message="Job cancellation requested")
    else:
        job.status = JobStatus.CANCELLED.value
        job.completed_at = utc_now()
        job.execution_stage = "cancelled"
        append_job_log(session, job, level="info", event_type="automation_cancelled", message="Job cancelled")
    session.commit(); session.refresh(job)
    return job


def acknowledge_job_cancellation(session: Session, job: Job, claim_token: str, attempt: int) -> Job:
    validate_job_claim(job, claim_token, attempt)
    if job.status != JobStatus.CANCELLING.value:
        raise InvalidJobTransitionError(job.status, JobStatus.CANCELLED)
    job.status = JobStatus.CANCELLED.value
    job.completed_at = utc_now()
    job.execution_stage = "cancelled"
    _clear_claim(job)
    append_job_log(session, job, level="info", event_type="automation_cancelled", message="Worker acknowledged cancellation")
    session.commit(); session.refresh(job)
    return job


def retry_failed_job(session: Session, job: Job, scheduled_at: datetime | None = None) -> Job:
    _require_status(job, JobStatus.RETRYING, {JobStatus.FAILED})
    if job.attempt_count >= job.max_attempts:
        raise JobRetryLimitError(job.attempt_count, job.max_attempts)
    job.status = JobStatus.PENDING.value
    job.scheduled_at = scheduled_at
    job.started_at = None
    job.completed_at = None
    job.result = None
    job.error_message = None
    job.error_code = None
    job.error_retryable = None
    job.execution_started_at = None
    job.execution_stage = "retry_scheduled"
    _clear_claim(job)
    append_job_log(session, job, level="info", event_type="retry_scheduled", message="Job retry scheduled", metadata={"attempt_count": job.attempt_count})
    session.commit(); session.refresh(job)
    return job


def _require_status(job: Job, target_status: JobStatus, allowed_statuses: set[JobStatus]) -> None:
    if job.status not in {status.value for status in allowed_statuses}:
        raise InvalidJobTransitionError(job.status, target_status)
