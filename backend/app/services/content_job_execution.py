"""Lease-fenced backend boundary for internal content inspection Jobs."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import load_application_config
from app.models import ContentAssetVersion, Job, JobStatus
from app.models.timestamps import utc_now
from app.services.content_inspection import ContentInspectionService, ContentProcessingError
from app.services.content_jobs import ContentInspectResult, validate_content_job_payload
from app.services.content_operation_lock import ContentVersionOperationGuard
from app.services.content_storage import ContentStorageService
from app.services.job_lifecycle import JobClaimOwnershipError, validate_job_claim
from app.services.job_logs import append_job_log
from app.services.media_probe import FfprobeInspector


class ContentJobExecutionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def execute(self, job: Job, claim_token: str, attempt: int) -> dict[str, Any]:
        validate_job_claim(job, claim_token, attempt)
        if job.job_type != "content.inspect" or job.runtime_id is not None:
            raise ContentProcessingError(
                "CONTENT_PROCESSING_FAILED", "Content inspection Job is invalid", retryable=False
            )
        payload = validate_content_job_payload(job.payload)
        version = self.session.get(
            ContentAssetVersion, payload["content_asset_version_id"]
        )
        if (
            version is None
            or version.content_asset_id != payload["content_asset_id"]
            or version.inspection_job_id != job.id
        ):
            raise ContentProcessingError(
                "CONTENT_VERSION_NOT_FOUND", "Content version was not found", retryable=False
            )
        self._check_cancelled(job, claim_token, attempt)
        job.execution_started_at = job.execution_started_at or utc_now()
        job.execution_stage = "content_processing"
        append_job_log(
            self.session,
            job,
            level="info",
            event_type="content_processing_started",
            message="Content inspection started",
            metadata={
                "content_asset_id": payload["content_asset_id"],
                "content_asset_version_id": payload["content_asset_version_id"],
            },
        )
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
        service = ContentInspectionService(
            self.session,
            storage=ContentStorageService(
                config.content_root,
                max_upload_bytes=config.content_max_upload_bytes,
                max_total_bytes=config.content_max_total_bytes,
            ),
            guard=ContentVersionOperationGuard(config.content_inspection_lock_directory),
            ffprobe=FfprobeInspector(
                config.content_ffprobe_path,
                timeout_seconds=config.content_ffprobe_timeout_seconds,
                max_output_bytes=config.content_ffprobe_max_output_bytes,
                cancellation_hook=cancellation_hook,
            ),
            max_image_dimension=config.content_max_image_dimension,
            max_image_pixels=config.content_max_image_pixels,
            max_image_frames=config.content_max_image_frames,
            cancellation_hook=cancellation_hook,
        )
        try:
            result = service.inspect(
                payload["content_asset_id"], payload["content_asset_version_id"]
            )
            self._check_cancelled(job, claim_token, attempt)
            validated = ContentInspectResult.model_validate(result).model_dump(mode="json")
            job.execution_stage = "content_inspected"
            append_job_log(
                self.session,
                job,
                level="info",
                event_type="content_inspected",
                message="Content inspection completed",
                metadata={"processing_status": validated["processing_status"]},
            )
            self.session.commit()
            return validated
        except ContentProcessingError as error:
            job.execution_stage = "content_inspection_failed"
            append_job_log(
                self.session,
                job,
                level="warning" if error.retryable else "error",
                event_type="content_inspection_failed",
                message="Content inspection failed",
                metadata={"error_code": error.code, "retryable": error.retryable},
            )
            self.session.commit()
            raise

    def _check_cancelled(self, job: Job, claim_token: str, attempt: int) -> None:
        self.session.expire(job)
        try:
            validate_job_claim(job, claim_token, attempt)
        except JobClaimOwnershipError as error:
            raise ContentProcessingError(
                "CONTENT_PROCESSING_CANCELLED",
                "Content inspection was cancelled",
                retryable=True,
            ) from error
        if job.status == JobStatus.CANCELLING.value:
            raise ContentProcessingError(
                "CONTENT_PROCESSING_CANCELLED",
                "Content inspection was cancelled",
                retryable=True,
            )
