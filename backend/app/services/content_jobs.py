"""Internal content inspection Job definition, enqueue, and recovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentAssetVersion, ContentEvent, Job, JobStatus
from app.services.content_operation_lock import (
    ContentOperationLockBusy,
    ContentVersionOperationGuard,
)


class ContentInspectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_asset_id: int = Field(gt=0)
    content_asset_version_id: int = Field(gt=0)


class ContentInspectResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_asset_id: int = Field(gt=0)
    content_asset_version_id: int = Field(gt=0)
    processing_status: Literal["processing", "ready", "invalid"]
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None
    codec: str | None = None
    container: str | None = None
    metadata: dict[str, Any]
    error_code: str | None = None
    error_message: str | None = None


class ContentDeliverPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_delivery_id: int = Field(gt=0)


@dataclass(frozen=True)
class ContentJobDefinition:
    job_type: str
    retryable_codes: frozenset[str]
    idempotency: Literal["safe"] = "safe"

    @property
    def allows_post_dispatch_retry(self) -> bool:
        return True


CONTENT_INSPECT_DEFINITION = ContentJobDefinition(
    job_type="content.inspect",
    retryable_codes=frozenset({
        "CONTENT_FFPROBE_UNAVAILABLE", "CONTENT_FFPROBE_TIMEOUT",
        "CONTENT_PROCESSING_FAILED", "CONTENT_PROCESSING_BUSY",
        "CONTENT_BLOB_MISSING", "CONTENT_PROCESSING_CANCELLED",
    }),
)
CONTENT_DELIVER_DEFINITION = ContentJobDefinition(
    job_type="content.deliver",
    retryable_codes=frozenset({
        "RUNTIME_BUSY", "ADB_UNAVAILABLE", "DEVICE_NOT_READY",
        "ADB_COMMAND_FAILED", "AUTOMATION_TIMEOUT", "FILE_TRANSFER_FAILED",
        "MEDIA_IMPORT_FAILED", "CONTENT_DELIVERY_CANCELLED",
        "CONTENT_DELIVERY_UNCERTAIN",
    }),
)
CONTENT_JOB_DEFINITIONS = {
    definition.job_type: definition
    for definition in (CONTENT_INSPECT_DEFINITION, CONTENT_DELIVER_DEFINITION)
}


class ContentJobValidationError(ValueError):
    pass


def is_content_job_type(job_type: object) -> bool:
    return isinstance(job_type, str) and job_type in CONTENT_JOB_DEFINITIONS


def get_content_job_definition(job_type: str) -> ContentJobDefinition | None:
    return CONTENT_JOB_DEFINITIONS.get(job_type)


def validate_content_job_payload(payload: Any) -> dict[str, int]:
    try:
        return ContentInspectPayload.model_validate(payload).model_dump()
    except ValidationError as error:
        raise ContentJobValidationError("Invalid content inspection payload") from error


def validate_content_delivery_payload(payload: Any) -> dict[str, int]:
    try:
        return ContentDeliverPayload.model_validate(payload).model_dump()
    except ValidationError as error:
        raise ContentJobValidationError("Invalid content delivery payload") from error


def enqueue_content_inspection(
    session: Session,
    version: ContentAssetVersion,
    *,
    scheduled_at=None,
) -> Job:
    if version.id is None or version.content_asset_id is None:
        raise ContentJobValidationError("Content version must be persisted before inspection")
    if version.inspection_job_id is not None:
        existing = session.get(Job, version.inspection_job_id)
        if existing is not None and existing.status in {
            JobStatus.PENDING.value,
            JobStatus.RUNNING.value,
            JobStatus.CANCELLING.value,
        }:
            return existing
    job = Job(
        job_type="content.inspect",
        status=JobStatus.PENDING.value,
        runtime_id=None,
        account_id=None,
        payload={
            "content_asset_id": version.content_asset_id,
            "content_asset_version_id": version.id,
        },
        max_attempts=3,
        scheduled_at=scheduled_at,
        execution_stage="queued",
    )
    session.add(job)
    session.flush()
    version.inspection_job_id = job.id
    session.add(
        ContentEvent(
            content_asset_id=version.content_asset_id,
            content_asset_version_id=version.id,
            event_type="processing_queued",
            metadata_json={"job_id": job.id},
        )
    )
    return job


def reconcile_content_inspections(
    session: Session, guard: ContentVersionOperationGuard
) -> int:
    """Reschedule only processing versions lacking a viable inspection Job."""
    version_ids = list(
        session.scalars(
            select(ContentAssetVersion.id).where(
                ContentAssetVersion.processing_status == "processing"
            )
        ).all()
    )
    scheduled = 0
    for version_id in version_ids:
        try:
            with guard.acquire(version_id, blocking=False):
                version = session.get(ContentAssetVersion, version_id)
                if version is None or version.processing_status != "processing":
                    continue
                job = session.get(Job, version.inspection_job_id) if version.inspection_job_id else None
                if job is not None and job.status in {
                    JobStatus.PENDING.value,
                    JobStatus.RUNNING.value,
                    JobStatus.CANCELLING.value,
                }:
                    continue
                if job is not None and job.status == JobStatus.FAILED.value and not job.error_retryable:
                    continue
                version.inspection_job_id = None
                enqueue_content_inspection(session, version)
                session.commit()
                scheduled += 1
        except ContentOperationLockBusy:
            session.rollback()
            continue
    return scheduled
