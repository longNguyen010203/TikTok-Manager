"""Job CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, Job, JobArtifact, JobLog, JobStatus, Runtime
from app.schemas.job import (
    JobCreate,
    JobCancelAcknowledgement,
    JobClaimRead,
    JobClaimRequest,
    JobExecuteRead,
    JobFailed,
    JobList,
    JobLogRead,
    JobRead,
    JobRetry,
    JobSucceeded,
    JobHeartbeatRead,
    JobUpdate,
)
from app.services.automation_errors import AutomationError
from app.services.device_job_execution import DeviceJobExecutionService
from app.services.device_jobs import (
    DeviceJobValidationError,
    is_device_job_type,
    validate_device_job_payload,
)
from app.services.job_lifecycle import (
    InvalidJobTransitionError,
    JobClaimOwnershipError,
    JobRetryLimitError,
    acknowledge_job_cancellation,
    cancel_job as cancel_job_service,
    claim_next_job,
    heartbeat_job,
    mark_job_failed,
    mark_job_succeeded,
    retry_failed_job,
)
from app.routers.devices import screen_process_manager

router = APIRouter(prefix="/jobs", tags=["jobs"])
DatabaseSession = Annotated[Session, Depends(get_db)]
JobId = Annotated[int, Path(gt=0)]
ClaimToken = Annotated[str, Header(alias="X-Job-Claim-Token", min_length=32, max_length=256)]
ClaimAttempt = Annotated[int, Header(alias="X-Job-Attempt", gt=0)]


def _get_job_or_404(job_id: int, session: Session) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _get_job_for_update_or_404(job_id: int, session: Session) -> Job:
    job = session.scalar(
        select(Job).where(Job.id == job_id).with_for_update()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _raise_invalid_transition(error: InvalidJobTransitionError) -> None:
    raise HTTPException(status_code=409, detail=str(error)) from error


def _raise_retry_limit(error: JobRetryLimitError) -> None:
    raise HTTPException(status_code=409, detail=str(error)) from error


def _validate_account_id(account_id: int | None, session: Session) -> None:
    if account_id is not None and session.get(Account, account_id) is None:
        raise HTTPException(status_code=404, detail="Account not found")


def _validate_runtime_id(runtime_id: int | None, session: Session) -> None:
    if runtime_id is not None and session.get(Runtime, runtime_id) is None:
        raise HTTPException(status_code=404, detail="Runtime not found")


def _validate_device_job(job_type: str, runtime_id: int | None, account_id: int | None, payload: object, session: Session) -> dict:
    if runtime_id is None:
        raise HTTPException(status_code=422, detail="device Jobs require runtime_id")
    runtime = session.get(Runtime, runtime_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Runtime not found")
    if runtime.runtime_type != "redroid" or not runtime.adb_serial or not runtime.docker_container_name:
        raise HTTPException(status_code=422, detail="Runtime is not a valid Redroid automation target")
    if account_id is not None:
        account = session.get(Account, account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        if account.runtime_id is not None and account.runtime_id != runtime_id:
            raise HTTPException(status_code=422, detail="Account Runtime assignment does not match runtime_id")
    try:
        return validate_device_job_payload(job_type, payload)
    except DeviceJobValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _raise_claim(error: JobClaimOwnershipError) -> None:
    raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("", response_model=JobList)
def list_jobs(
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    job_status: Annotated[JobStatus | None, Query(alias="status")] = None,
    job_type: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    account_id: Annotated[int | None, Query(gt=0)] = None,
    runtime_id: Annotated[int | None, Query(gt=0)] = None,
) -> JobList:
    """List jobs using page-based pagination and exact-match filters."""
    filters = []
    if job_status is not None:
        filters.append(Job.status == job_status.value)
    if job_type is not None:
        filters.append(Job.job_type == job_type)
    if account_id is not None:
        filters.append(Job.account_id == account_id)
    if runtime_id is not None:
        filters.append(Job.runtime_id == runtime_id)

    total = session.scalar(select(func.count()).select_from(Job).where(*filters))
    jobs = session.scalars(
        select(Job)
        .where(*filters)
        .order_by(Job.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return JobList(items=list(jobs), total=total or 0, page=page, page_size=page_size)


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: JobId, session: DatabaseSession) -> Job:
    """Return one job by ID."""
    return _get_job_or_404(job_id, session)


@router.get("/{job_id}/logs", response_model=list[JobLogRead])
def list_job_logs(job_id: JobId, session: DatabaseSession) -> list[JobLog]:
    """Return a Job's persistent logs in creation order."""
    _get_job_or_404(job_id, session)
    return list(
        session.scalars(
            select(JobLog)
            .where(JobLog.job_id == job_id)
            .order_by(JobLog.id)
        ).all()
    )


@router.post(
    "/claim",
    response_model=JobClaimRead,
    responses={204: {"description": "No eligible job is available"}},
)
def claim_job(session: DatabaseSession, payload: JobClaimRequest | None = None) -> JobClaimRead | Response:
    """Claim the next pending job that is ready to run."""
    claimed = claim_next_job(session, claimed_by=(payload or JobClaimRequest()).claimed_by)
    if claimed is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    data = JobRead.model_validate(claimed.job).model_dump()
    return JobClaimRead(**data, claim_token=claimed.claim_token, claimed_by=claimed.job.claimed_by, lease_expires_at=claimed.job.lease_expires_at)


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, session: DatabaseSession) -> Job:
    """Create a job with optional Account and Runtime targets."""
    _validate_account_id(payload.account_id, session)
    _validate_runtime_id(payload.runtime_id, session)
    data = payload.model_dump()
    if is_device_job_type(payload.job_type):
        if payload.status != JobStatus.PENDING or payload.attempt_count != 0 or payload.result is not None or payload.error_message is not None:
            raise HTTPException(status_code=422, detail="device Job lifecycle fields cannot be supplied")
        data["payload"] = _validate_device_job(payload.job_type, payload.runtime_id, payload.account_id, payload.payload, session)
    job = Job(**data)
    session.add(job)
    session.flush()
    if is_device_job_type(job.job_type) and job.job_type in {"device.push_file", "device.import_media"}:
        artifact = session.get(JobArtifact, job.payload["artifact_id"])
        if artifact is None or artifact.cleanup_status != "active" or artifact.job_id is not None:
            session.rollback()
            raise HTTPException(status_code=422, detail="Managed artifact is unavailable")
        artifact.job_id = job.id
    session.commit()
    session.refresh(job)
    return job


@router.patch("/{job_id}", response_model=JobRead)
def update_job(job_id: JobId, payload: JobUpdate, session: DatabaseSession) -> Job:
    """Update fields supplied for a job."""
    job = _get_job_or_404(job_id, session)
    update_data = payload.model_dump(exclude_unset=True)
    if is_device_job_type(job.job_type) and job.attempt_count > 0 and any(field in update_data for field in {"job_type", "runtime_id", "account_id", "payload"}):
        raise HTTPException(status_code=409, detail="Claimed device Job targets and payload are immutable")
    if "status" in update_data and update_data["status"] != job.status:
        raise HTTPException(
            status_code=409,
            detail="Job status changes require a lifecycle action",
        )
    if "account_id" in update_data:
        _validate_account_id(update_data["account_id"], session)
    if "runtime_id" in update_data:
        _validate_runtime_id(update_data["runtime_id"], session)
    candidate_type = update_data.get("job_type", job.job_type)
    if is_device_job_type(candidate_type):
        candidate_runtime = update_data.get("runtime_id", job.runtime_id)
        candidate_account = update_data.get("account_id", job.account_id)
        candidate_payload = update_data.get("payload", job.payload)
        update_data["payload"] = _validate_device_job(candidate_type, candidate_runtime, candidate_account, candidate_payload, session)
    for field, value in update_data.items():
        setattr(job, field, value)

    session.commit()
    session.refresh(job)
    return job


@router.post("/{job_id}/succeed", response_model=JobRead)
def succeed_job(
    job_id: JobId, payload: JobSucceeded, session: DatabaseSession,
    claim_token: ClaimToken, attempt: ClaimAttempt,
) -> Job:
    """Mark a running job as succeeded."""
    job = _get_job_for_update_or_404(job_id, session)
    try:
        return mark_job_succeeded(session, job, claim_token, attempt, payload.result)
    except InvalidJobTransitionError as error:
        _raise_invalid_transition(error)
    except JobClaimOwnershipError as error:
        _raise_claim(error)


@router.post("/{job_id}/fail", response_model=JobRead)
def fail_job(job_id: JobId, payload: JobFailed, session: DatabaseSession, claim_token: ClaimToken, attempt: ClaimAttempt) -> Job:
    """Mark a running job as failed."""
    job = _get_job_for_update_or_404(job_id, session)
    try:
        return mark_job_failed(session, job, claim_token, attempt, error_message=payload.error_message, error_code=payload.error_code, retryable=payload.retryable)
    except InvalidJobTransitionError as error:
        _raise_invalid_transition(error)
    except JobClaimOwnershipError as error:
        _raise_claim(error)


@router.post("/{job_id}/heartbeat", response_model=JobHeartbeatRead)
def heartbeat(job_id: JobId, session: DatabaseSession, claim_token: ClaimToken, attempt: ClaimAttempt) -> JobHeartbeatRead:
    job = _get_job_for_update_or_404(job_id, session)
    try:
        job = heartbeat_job(session, job, claim_token, attempt)
    except JobClaimOwnershipError as error:
        _raise_claim(error)
    return JobHeartbeatRead(job_id=job.id, attempt=job.attempt_count, status=job.status, lease_expires_at=job.lease_expires_at, cancellation_requested=job.status == JobStatus.CANCELLING.value)


@router.post("/{job_id}/execute", response_model=JobExecuteRead)
def execute_job(job_id: JobId, session: DatabaseSession, claim_token: ClaimToken, attempt: ClaimAttempt) -> JobExecuteRead:
    job = _get_job_for_update_or_404(job_id, session)
    try:
        result = DeviceJobExecutionService(session, screen_manager=screen_process_manager).execute(job, claim_token, attempt)
        return JobExecuteRead(result=result)
    except JobClaimOwnershipError as error:
        _raise_claim(error)
    except DeviceJobValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except AutomationError as error:
        code = 409 if error.code in {"RUNTIME_BUSY", "RUNTIME_STOPPED", "RUNTIME_DEPROVISIONING", "RUNTIME_SCREEN_ACTIVE", "AUTOMATION_CANCELLED"} else 502
        raise HTTPException(status_code=code, detail={"code": error.code, "message": error.safe_message, "retryable": error.retryable}) from error


@router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_job(job_id: JobId, session: DatabaseSession) -> Job:
    """Cancel a pending, running, or retrying job."""
    job = _get_job_for_update_or_404(job_id, session)
    try:
        return cancel_job_service(session, job)
    except InvalidJobTransitionError as error:
        _raise_invalid_transition(error)


@router.post("/{job_id}/cancel/acknowledge", response_model=JobRead)
def acknowledge_cancel(job_id: JobId, _payload: JobCancelAcknowledgement, session: DatabaseSession, claim_token: ClaimToken, attempt: ClaimAttempt) -> Job:
    job = _get_job_for_update_or_404(job_id, session)
    try:
        return acknowledge_job_cancellation(session, job, claim_token, attempt)
    except InvalidJobTransitionError as error:
        _raise_invalid_transition(error)
    except JobClaimOwnershipError as error:
        _raise_claim(error)


@router.post("/{job_id}/retry", response_model=JobRead)
def retry_job(
    job_id: JobId,
    session: DatabaseSession,
    payload: JobRetry | None = None,
) -> Job:
    """Requeue a failed job when another attempt is available."""
    job = _get_job_for_update_or_404(job_id, session)
    try:
        return retry_failed_job(
            session, job, payload.scheduled_at if payload is not None else None
        )
    except InvalidJobTransitionError as error:
        _raise_invalid_transition(error)
    except JobRetryLimitError as error:
        _raise_retry_limit(error)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: JobId, session: DatabaseSession) -> Response:
    """Delete a job."""
    job = _get_job_or_404(job_id, session)
    session.delete(job)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
    JobClaimOwnershipError,
    acknowledge_job_cancellation,
    heartbeat_job,
