"""Internal managed-package inspection Job definition and recovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, JobStatus, ManagedAppVersion
from app.services.content_operation_lock import ContentOperationLockBusy, ContentVersionOperationGuard


class AppInspectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    managed_app_version_id: int = Field(gt=0)


class AppInspectResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    managed_app_id: int = Field(gt=0)
    managed_app_version_id: int = Field(gt=0)
    status: Literal["ready", "invalid"]
    package_name: str | None = None
    version_name: str | None = None
    version_code: int | None = None
    min_sdk: int | None = None
    target_sdk: int | None = None
    signer_fingerprint: str | None = None
    inspection_level: Literal["basic", "verified"]
    error_code: str | None = None
    error_message: str | None = None


class RuntimeAppJobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runtime_app_installation_id: int = Field(gt=0)


class RuntimeAppJobResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    installation_id: int = Field(gt=0)
    app_id: int = Field(gt=0)
    desired_version_id: int = Field(gt=0)
    observed_package: str | None = None
    observed_version_name: str | None = None
    observed_version_code: int | None = Field(default=None, ge=0)
    status: Literal["installed", "removed"]
    changed: bool = False
    inspection_level: Literal["basic", "verified"]
    package_verification: Literal["post_install", "pre_and_post_install"]


@dataclass(frozen=True)
class ManagedAppJobDefinition:
    job_type: str
    retryable_codes: frozenset[str]
    idempotency: Literal["safe"] = "safe"

    @property
    def allows_post_dispatch_retry(self) -> bool:
        return True


APP_INSPECT_DEFINITION = ManagedAppJobDefinition(
    job_type="app.inspect",
    retryable_codes=frozenset({
        "APK_INSPECTOR_UNAVAILABLE", "APK_INSPECTION_TIMEOUT",
        "APK_INSPECTION_FAILED", "APP_INSPECTION_BUSY",
        "APP_INSPECTION_CANCELLED", "CONTENT_BLOB_MISSING",
    }),
)
APP_INSTALL_DEFINITION = ManagedAppJobDefinition(
    job_type="app.install",
    retryable_codes=frozenset({
        "RUNTIME_BUSY", "DEVICE_NOT_READY", "ADB_UNAVAILABLE",
        "APP_INSTALL_FAILED", "APP_VERIFY_FAILED", "APP_OPERATION_CANCELLED",
    }),
)
APP_VERIFY_DEFINITION = ManagedAppJobDefinition(
    job_type="app.verify",
    retryable_codes=frozenset({
        "RUNTIME_BUSY", "DEVICE_NOT_READY", "ADB_UNAVAILABLE",
        "APP_VERIFY_FAILED", "APP_OPERATION_CANCELLED",
    }),
)
_DEFINITIONS = {
    definition.job_type: definition
    for definition in (APP_INSPECT_DEFINITION, APP_INSTALL_DEFINITION, APP_VERIFY_DEFINITION)
}


class ManagedAppJobValidationError(ValueError):
    pass


def is_managed_app_job_type(job_type: object) -> bool:
    return isinstance(job_type, str) and job_type in _DEFINITIONS


def get_managed_app_job_definition(job_type: str):
    return _DEFINITIONS.get(job_type)


def validate_app_inspect_payload(payload: Any) -> dict[str, int]:
    try:
        return AppInspectPayload.model_validate(payload).model_dump()
    except ValidationError as error:
        raise ManagedAppJobValidationError("Invalid app inspection payload") from error


def validate_runtime_app_job_payload(payload: Any) -> dict[str, int]:
    try:
        return RuntimeAppJobPayload.model_validate(payload).model_dump()
    except ValidationError as error:
        raise ManagedAppJobValidationError("Invalid Runtime app payload") from error


def enqueue_app_inspection(session: Session, version: ManagedAppVersion) -> Job:
    if version.id is None:
        raise ManagedAppJobValidationError("Managed app version must be persisted")
    if version.inspection_job_id is not None:
        existing = session.get(Job, version.inspection_job_id)
        if existing is not None and existing.status in {
            JobStatus.PENDING.value, JobStatus.RUNNING.value, JobStatus.CANCELLING.value,
        }:
            return existing
    job = Job(
        job_type="app.inspect",
        status=JobStatus.PENDING.value,
        runtime_id=None,
        account_id=None,
        payload={"managed_app_version_id": version.id},
        max_attempts=3,
        execution_stage="queued",
    )
    session.add(job)
    session.flush()
    version.inspection_job_id = job.id
    version.status = "inspecting"
    return job


def reconcile_app_inspections(
    session: Session, guard: ContentVersionOperationGuard
) -> int:
    scheduled = 0
    versions = list(session.scalars(select(ManagedAppVersion).where(
        ManagedAppVersion.status.in_(["uploaded", "inspecting"])
    )).all())
    for version in versions:
        try:
            with guard.acquire(version.content_asset_version_id, blocking=False):
                session.refresh(version)
                if version.status not in {"uploaded", "inspecting"}:
                    continue
                job = session.get(Job, version.inspection_job_id) if version.inspection_job_id else None
                if job is not None and job.status in {
                    JobStatus.PENDING.value, JobStatus.RUNNING.value, JobStatus.CANCELLING.value,
                }:
                    continue
                if job is not None and job.status == JobStatus.FAILED.value and not job.error_retryable:
                    continue
                # A terminal retryable or unexpectedly succeeded Job with no
                # authoritative version transition is recoverable: create one
                # new fenced Job and retain the old Job as history.
                version.inspection_job_id = None
                enqueue_app_inspection(session, version)
                session.add(_event(version, "inspection_queued", {"job_id": version.inspection_job_id}))
                session.commit()
                scheduled += 1
        except ContentOperationLockBusy:
            session.rollback()
    return scheduled


def _event(version: ManagedAppVersion, event_type: str, metadata: dict):
    from app.models import ManagedAppEvent
    return ManagedAppEvent(
        managed_app_id=version.managed_app_id,
        managed_app_version_id=version.id,
        job_id=version.inspection_job_id,
        event_type=event_type,
        metadata_json=metadata,
    )
