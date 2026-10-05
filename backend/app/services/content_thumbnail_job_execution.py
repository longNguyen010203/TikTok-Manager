"""Lease-fenced backend boundary for internal thumbnail Jobs."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import load_application_config
from app.models import ContentAssetVersion, Job, JobStatus
from app.models.timestamps import utc_now
from app.services.content_jobs import ContentThumbnailResult, validate_content_thumbnail_payload
from app.services.content_operation_lock import ContentVersionOperationGuard
from app.services.content_storage import ContentStorageService
from app.services.content_thumbnail import ContentThumbnailError, ContentThumbnailService
from app.services.job_lifecycle import JobClaimOwnershipError, validate_job_claim
from app.services.job_logs import append_job_log


class ContentThumbnailJobExecutionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def execute(self, job: Job, claim_token: str, attempt: int) -> dict[str, Any]:
        validate_job_claim(job, claim_token, attempt)
        if job.job_type != "content.thumbnail" or job.runtime_id is not None:
            raise ContentThumbnailError(
                "CONTENT_THUMBNAIL_FAILED", "Thumbnail Job is invalid", retryable=False
            )
        payload = validate_content_thumbnail_payload(job.payload)
        version = self.session.get(ContentAssetVersion, payload["content_asset_version_id"])
        if (
            version is None or version.content_asset_id != payload["content_asset_id"]
            or version.thumbnail_job_id != job.id
        ):
            raise ContentThumbnailError(
                "CONTENT_THUMBNAIL_NOT_FOUND", "Thumbnail request was not found",
                retryable=False,
            )
        self._check_cancelled(job, claim_token, attempt)
        job.execution_started_at = job.execution_started_at or utc_now()
        job.execution_stage = "thumbnail_processing"
        append_job_log(
            self.session, job, level="info", event_type="content_thumbnail_started",
            message="Content thumbnail generation started",
            metadata={"content_asset_id": version.content_asset_id, "content_asset_version_id": version.id},
        )
        self.session.commit()

        def cancelled() -> bool:
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
        service = ContentThumbnailService(
            self.session,
            storage=ContentStorageService(
                config.content_root,
                max_upload_bytes=config.content_max_upload_bytes,
                max_total_bytes=config.content_max_total_bytes,
            ),
            guard=ContentVersionOperationGuard(config.content_inspection_lock_directory),
            ffmpeg_path=config.content_ffmpeg_path,
            timeout_seconds=config.content_thumbnail_timeout_seconds,
            cancellation_hook=cancelled,
        )
        try:
            result = service.generate(
                payload["content_asset_id"], payload["content_asset_version_id"],
                payload["content_variant_id"],
            )
            self._check_cancelled(job, claim_token, attempt)
            validated = ContentThumbnailResult.model_validate(result).model_dump(mode="json")
            job.execution_stage = "thumbnail_ready"
            append_job_log(
                self.session, job, level="info", event_type="content_thumbnail_ready",
                message="Content thumbnail generation completed",
                metadata={"content_variant_id": payload["content_variant_id"]},
            )
            self.session.commit()
            return validated
        except ContentThumbnailError as error:
            service.mark_invalid(payload["content_variant_id"], error)
            job.execution_stage = "thumbnail_failed"
            append_job_log(
                self.session, job, level="warning" if error.retryable else "error",
                event_type="content_thumbnail_failed", message="Content thumbnail generation failed",
                metadata={"error_code": error.code, "retryable": error.retryable},
            )
            self.session.commit()
            raise

    def _check_cancelled(self, job: Job, claim_token: str, attempt: int) -> None:
        self.session.expire(job)
        try:
            validate_job_claim(job, claim_token, attempt)
        except JobClaimOwnershipError as error:
            raise ContentThumbnailError(
                "CONTENT_PROCESSING_CANCELLED", "Thumbnail generation was cancelled",
                retryable=True,
            ) from error
        if job.status == JobStatus.CANCELLING.value:
            raise ContentThumbnailError(
                "CONTENT_PROCESSING_CANCELLED", "Thumbnail generation was cancelled",
                retryable=True,
            )
