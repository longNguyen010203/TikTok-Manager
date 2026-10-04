"""Lease-fenced execution boundary for exact-Runtime content delivery Jobs."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import load_application_config
from app.models import ContentAssetVersion, ContentDelivery, Job, JobStatus
from app.models.timestamps import utc_now
from app.services.adb_executor import AdbExecutor
from app.services.android_automation import AndroidAutomationService, ManagedFileSource
from app.services.automation_artifacts import AutomationArtifactStore
from app.services.automation_errors import AutomationError
from app.services.content_delivery import ContentDeliveryError, ContentDeliveryService
from app.services.content_jobs import validate_content_delivery_payload
from app.services.content_storage import ContentStorageError, ContentStorageService
from app.services.device_screen import ScreenProcessManager
from app.services.job_lifecycle import JobClaimOwnershipError, validate_job_claim
from app.services.job_logs import append_job_log
from app.services.redroid_runtime import RedroidRuntimeAdapter
from app.services.runtime_operation_lock import RuntimeOperationGuard


class ContentDeliveryJobExecutionService:
    def __init__(self, session: Session, *, screen_manager: ScreenProcessManager) -> None:
        self.session = session
        self.screen_manager = screen_manager

    def execute(self, job: Job, claim_token: str, attempt: int) -> dict[str, Any]:
        validate_job_claim(job, claim_token, attempt)
        if job.job_type != "content.deliver" or job.runtime_id is None:
            raise ContentDeliveryError(
                "CONTENT_DELIVERY_NOT_FOUND", "Content delivery Job is invalid"
            )
        payload = validate_content_delivery_payload(job.payload)
        delivery = self.session.get(ContentDelivery, payload["content_delivery_id"])
        if (
            delivery is None
            or delivery.job_id != job.id
            or delivery.runtime_id != job.runtime_id
            or delivery.runtime_id_snapshot != job.runtime_id
        ):
            raise ContentDeliveryError(
                "CONTENT_DELIVERY_NOT_FOUND", "Content delivery was not found"
            )
        if delivery.status == "succeeded":
            return self._result(delivery)
        if delivery.status == "cancelled":
            raise ContentDeliveryError(
                "CONTENT_DELIVERY_CANCELLED", "Content delivery was cancelled"
            )
        self._check_cancelled(job, claim_token, attempt)
        version = self.session.get(ContentAssetVersion, delivery.content_asset_version_id)
        if version is None or version.content_asset_id != delivery.content_asset_id:
            raise ContentDeliveryError(
                "CONTENT_VERSION_NOT_FOUND", "Pinned content version was not found"
            )
        if version.processing_status != "ready" or version.blob.status != "active":
            raise ContentDeliveryError(
                "CONTENT_VERSION_NOT_READY", "Pinned content version is not ready"
            )
        config = load_application_config()
        storage = ContentStorageService(
            config.content_root,
            max_upload_bytes=config.content_max_upload_bytes,
            max_total_bytes=config.content_max_total_bytes,
        )
        try:
            local_path = storage.verify_blob(version.blob)
        except ContentStorageError as error:
            code = "CONTENT_BLOB_MISSING" if error.code == "CONTENT_BLOB_MISSING" else "CONTENT_BLOB_INVALID"
            raise ContentDeliveryError(code, error.safe_message) from error

        delivery.status = "delivering"
        delivery.started_at = delivery.started_at or utc_now()
        delivery.error_code = None
        delivery.error_message = None
        job.execution_started_at = job.execution_started_at or utc_now()
        job.execution_stage = "content_delivery"
        ContentDeliveryService.record_event(self.session, delivery, "delivery_started")
        append_job_log(
            self.session, job, level="info", event_type="content_delivery_started",
            message="Content delivery started",
            metadata={"content_delivery_id": delivery.id, "content_asset_version_id": version.id},
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

        service = AndroidAutomationService(
            self.session,
            adb=AdbExecutor(default_timeout=120, cancellation_hook=cancellation_hook),
            runtime_adapter=RedroidRuntimeAdapter(),
            guard=RuntimeOperationGuard(config.bridge_lock_directory),
            artifacts=AutomationArtifactStore.from_application_config(),
            screen_inspector=self.screen_manager,
            readiness_timeout=30,
            lock_timeout=0,
        )
        source = ManagedFileSource(
            path=local_path,
            size_bytes=version.blob.size_bytes,
            sha256=version.blob.sha256,
            mime_type=version.detected_mime_type,
        )
        try:
            result = service.deliver_managed_file(
                job.runtime_id,
                source,
                filename=delivery.remote_filename,
                import_media=delivery.import_media,
            )
            self._check_cancelled(job, claim_token, attempt)
            delivery.status = "succeeded"
            delivery.media_uri = result["media_uri"]
            delivery.delivered_sha256 = version.blob.sha256
            delivery.completed_at = utc_now()
            delivery.error_code = None
            delivery.error_message = None
            job.execution_stage = "content_delivered"
            ContentDeliveryService.record_event(self.session, delivery, "delivered")
            append_job_log(
                self.session, job, level="info", event_type="content_delivered",
                message="Content delivery completed",
                metadata={"content_delivery_id": delivery.id, "media_imported": delivery.import_media},
            )
            self.session.commit()
            return self._result(delivery)
        except AutomationError as error:
            self.session.expire(delivery)
            cancelled = error.code == "AUTOMATION_CANCELLED"
            delivery.status = "cancelled" if cancelled else ("pending" if error.retryable else "failed")
            delivery.completed_at = utc_now() if cancelled or not error.retryable else None
            delivery.error_code = (
                "CONTENT_DELIVERY_UNCERTAIN" if cancelled else error.code
            )
            delivery.error_message = (
                "Content delivery was cancelled after execution began"
                if cancelled else error.safe_message
            )
            ContentDeliveryService.record_event(
                self.session,
                delivery,
                "delivery_cancelled" if cancelled else "delivery_failed",
                error_code=delivery.error_code,
            )
            self.session.commit()
            if cancelled:
                raise ContentDeliveryError(
                    "CONTENT_DELIVERY_CANCELLED", "Content delivery was cancelled", retryable=True
                ) from error
            raise
        except ContentDeliveryError as error:
            self.session.expire(delivery)
            if error.code == "CONTENT_DELIVERY_CANCELLED":
                delivery.status = "cancelled"
                delivery.completed_at = utc_now()
                delivery.error_code = "CONTENT_DELIVERY_UNCERTAIN"
                delivery.error_message = "Content delivery was cancelled after execution began"
                ContentDeliveryService.record_event(
                    self.session, delivery, "delivery_cancelled",
                    error_code=delivery.error_code,
                )
                self.session.commit()
            raise

    def _check_cancelled(self, job: Job, claim_token: str, attempt: int) -> None:
        self.session.expire(job)
        try:
            validate_job_claim(job, claim_token, attempt)
        except JobClaimOwnershipError as error:
            raise ContentDeliveryError(
                "CONTENT_DELIVERY_CANCELLED", "Content delivery claim is no longer valid",
                retryable=True,
            ) from error
        if job.status == JobStatus.CANCELLING.value:
            raise ContentDeliveryError(
                "CONTENT_DELIVERY_CANCELLED", "Content delivery was cancelled", retryable=True
            )

    @staticmethod
    def _result(delivery: ContentDelivery) -> dict[str, Any]:
        return {
            "content_delivery_id": delivery.id,
            "content_asset_id": delivery.content_asset_id,
            "content_asset_version_id": delivery.content_asset_version_id,
            "runtime_id": delivery.runtime_id_snapshot,
            "status": delivery.status,
            "remote_filename": delivery.remote_filename,
            "remote_path": delivery.remote_path,
            "media_uri": delivery.media_uri,
            "sha256": delivery.delivered_sha256,
        }
