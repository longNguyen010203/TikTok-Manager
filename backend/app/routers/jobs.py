"""Job CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, Job, JobLog, JobStatus, Runtime
from app.schemas.job import (
    JobCreate,
    JobFailed,
    JobList,
    JobLogRead,
    JobRead,
    JobRetry,
    JobSucceeded,
    JobUpdate,
)
from app.services.job_lifecycle import (
    InvalidJobTransitionError,
    JobRetryLimitError,
    cancel_job as cancel_job_service,
    claim_next_job,
    mark_job_failed,
    mark_job_succeeded,
    retry_failed_job,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])
DatabaseSession = Annotated[Session, Depends(get_db)]
JobId = Annotated[int, Path(gt=0)]


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
    response_model=JobRead,
    responses={204: {"description": "No eligible job is available"}},
)
def claim_job(session: DatabaseSession) -> Job | Response:
    """Claim the next pending job that is ready to run."""
    job = claim_next_job(session)
    if job is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return job


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, session: DatabaseSession) -> Job:
    """Create a job with optional Account and Runtime targets."""
    _validate_account_id(payload.account_id, session)
    _validate_runtime_id(payload.runtime_id, session)
    job = Job(**payload.model_dump())
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.patch("/{job_id}", response_model=JobRead)
def update_job(job_id: JobId, payload: JobUpdate, session: DatabaseSession) -> Job:
    """Update fields supplied for a job."""
    job = _get_job_or_404(job_id, session)
    update_data = payload.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] != job.status:
        raise HTTPException(
            status_code=409,
            detail="Job status changes require a lifecycle action",
        )
    if "account_id" in update_data:
        _validate_account_id(update_data["account_id"], session)
    if "runtime_id" in update_data:
        _validate_runtime_id(update_data["runtime_id"], session)
    for field, value in update_data.items():
        setattr(job, field, value)

    session.commit()
    session.refresh(job)
    return job


@router.post("/{job_id}/succeed", response_model=JobRead)
def succeed_job(
    job_id: JobId, payload: JobSucceeded, session: DatabaseSession
) -> Job:
    """Mark a running job as succeeded."""
    job = _get_job_for_update_or_404(job_id, session)
    try:
        return mark_job_succeeded(session, job, payload.result)
    except InvalidJobTransitionError as error:
        _raise_invalid_transition(error)


@router.post("/{job_id}/fail", response_model=JobRead)
def fail_job(job_id: JobId, payload: JobFailed, session: DatabaseSession) -> Job:
    """Mark a running job as failed."""
    job = _get_job_for_update_or_404(job_id, session)
    try:
        return mark_job_failed(session, job, payload.error_message)
    except InvalidJobTransitionError as error:
        _raise_invalid_transition(error)


@router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_job(job_id: JobId, session: DatabaseSession) -> Job:
    """Cancel a pending, running, or retrying job."""
    job = _get_job_for_update_or_404(job_id, session)
    try:
        return cancel_job_service(session, job)
    except InvalidJobTransitionError as error:
        _raise_invalid_transition(error)


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
