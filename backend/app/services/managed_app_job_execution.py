"""Lease-fenced backend execution boundary for internal app.inspect Jobs."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import load_application_config
from app.models import Job, JobStatus, ManagedAppEvent, ManagedAppVersion
from app.models.timestamps import utc_now
from app.services.apk_inspection import ApkInspectionError, ApkToolInspector
from app.services.content_operation_lock import ContentVersionOperationGuard
from app.services.content_storage import ContentStorageService
from app.services.job_lifecycle import JobClaimOwnershipError, validate_job_claim
from app.services.job_logs import append_job_log
from app.services.managed_app_inspection import ManagedAppInspectionService
from app.services.managed_app_jobs import AppInspectResult, validate_app_inspect_payload


class ManagedAppJobExecutionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def execute(self, job: Job, claim_token: str, attempt: int) -> dict[str, Any]:
        validate_job_claim(job, claim_token, attempt)
        if job.job_type != "app.inspect" or job.runtime_id is not None:
            raise ApkInspectionError("APK_INSPECTION_FAILED", "App inspection Job is invalid", retryable=False)
        payload = validate_app_inspect_payload(job.payload)
        version = self.session.get(ManagedAppVersion, payload["managed_app_version_id"])
        if version is None or version.inspection_job_id != job.id:
            raise ApkInspectionError("MANAGED_APP_VERSION_NOT_FOUND", "Managed app version was not found", retryable=False)
        self._check_cancelled(job, claim_token, attempt)
        job.execution_started_at = job.execution_started_at or utc_now()
        job.execution_stage = "app_inspection"
        append_job_log(
            self.session, job, level="info", event_type="app_inspection_started",
            message="Managed app inspection started",
            metadata={"managed_app_version_id": version.id},
        )
        if not self.session.query(ManagedAppEvent).filter_by(
            managed_app_version_id=version.id, event_type="inspection_started"
        ).first():
            self.session.add(ManagedAppEvent(
                managed_app_id=version.managed_app_id,
                managed_app_version_id=version.id,
                job_id=job.id,
                event_type="inspection_started",
                metadata_json={"job_id": job.id},
            ))
        self.session.commit()

        def cancellation_hook() -> bool:
            with Session(bind=self.session.get_bind()) as check_session:
                current = check_session.get(Job, job.id)
                if current is None or current.status == JobStatus.CANCELLING.value:
                    return True
                try:
                    validate_job_claim(current, claim_token, attempt)
                except JobClaimOwnershipError:
                    return True
                return False

        config = load_application_config()
        service = ManagedAppInspectionService(
            self.session,
            storage=ContentStorageService(
                config.content_root,
                max_upload_bytes=config.managed_app_max_apk_bytes,
                max_total_bytes=config.content_max_total_bytes,
            ),
            guard=ContentVersionOperationGuard(config.content_inspection_lock_directory),
            inspector=ApkToolInspector(
                config.managed_app_aapt2_path,
                config.managed_app_apksigner_path,
                timeout_seconds=config.managed_app_inspection_timeout_seconds,
                max_stdout_bytes=config.managed_app_max_stdout_bytes,
                max_stderr_bytes=config.managed_app_max_stderr_bytes,
                cancellation_hook=cancellation_hook,
            ),
            cancellation_hook=cancellation_hook,
        )
        try:
            result = service.inspect(version.id)
            self._check_cancelled(job, claim_token, attempt)
            validated = AppInspectResult.model_validate(result).model_dump(mode="json")
            job.execution_stage = "app_inspected"
            append_job_log(
                self.session, job, level="info", event_type="app_inspected",
                message="Managed app inspection completed",
                metadata={"status": validated["status"]},
            )
            self.session.commit()
            return validated
        except ApkInspectionError as error:
            job.execution_stage = "app_inspection_failed"
            append_job_log(
                self.session, job, level="warning" if error.retryable else "error",
                event_type="app_inspection_failed", message="Managed app inspection failed",
                metadata={"error_code": error.code, "retryable": error.retryable},
            )
            self.session.commit()
            raise

    def _check_cancelled(self, job: Job, claim_token: str, attempt: int) -> None:
        self.session.expire(job)
        try:
            validate_job_claim(job, claim_token, attempt)
        except JobClaimOwnershipError as error:
            raise ApkInspectionError("APP_INSPECTION_CANCELLED", "App inspection was cancelled", retryable=True) from error
        if job.status == JobStatus.CANCELLING.value:
            raise ApkInspectionError("APP_INSPECTION_CANCELLED", "App inspection was cancelled", retryable=True)

