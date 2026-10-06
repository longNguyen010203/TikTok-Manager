"""Durable creation, idempotency, and state transitions for content delivery."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    ContentAsset,
    ContentAssetVersion,
    ContentDelivery,
    ContentEvent,
    Job,
    JobStatus,
    Runtime,
)
from app.models.timestamps import utc_now
from app.services.automation_artifacts import AutomationArtifactStore


REMOTE_ROOT = PurePosixPath("/sdcard/Download/TikTokManager")
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ContentDeliveryError(RuntimeError):
    def __init__(self, code: str, safe_message: str, *, retryable: bool = False) -> None:
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable
        super().__init__(safe_message)


class ContentDeliveryService:
    def create(
        self,
        session: Session,
        *,
        content_asset_id: int,
        runtime_id: int,
        version_id: int | None,
        filename: str | None,
        import_media: bool,
        allow_repeat: bool,
        idempotency_key: str | None,
        commit: bool = True,
    ) -> tuple[ContentDelivery, bool]:
        asset = session.scalar(
            select(ContentAsset)
            .where(ContentAsset.id == content_asset_id)
            .options(
                selectinload(ContentAsset.versions).selectinload(ContentAssetVersion.blob)
            )
        )
        if asset is None:
            raise ContentDeliveryError("CONTENT_NOT_FOUND", "Content was not found")
        if asset.purpose != "library":
            raise ContentDeliveryError(
                "CONTENT_PURPOSE_INVALID", "Managed application packages cannot be delivered as media"
            )
        if asset.status == "deleted":
            raise ContentDeliveryError("CONTENT_DELETED", "Content was deleted")
        chosen_id = version_id if version_id is not None else asset.current_version_id
        if chosen_id is None:
            raise ContentDeliveryError("CONTENT_NOT_READY", "Content has no ready version")
        version = next((item for item in asset.versions if item.id == chosen_id), None)
        if version is None:
            raise ContentDeliveryError("CONTENT_VERSION_NOT_FOUND", "Content version was not found")
        if version.processing_status != "ready" or version.blob.status != "active":
            raise ContentDeliveryError(
                "CONTENT_VERSION_NOT_READY", "Content version is not ready"
            )
        runtime = session.get(Runtime, runtime_id)
        if (
            runtime is None
            or runtime.runtime_type != "redroid"
            or not runtime.adb_serial
            or not runtime.docker_container_name
        ):
            raise ContentDeliveryError("RUNTIME_NOT_FOUND", "Runtime was not found")
        key = self._validate_idempotency_key(idempotency_key)
        if key is not None:
            existing = session.scalar(
                select(ContentDelivery).where(
                    ContentDelivery.content_asset_version_id == version.id,
                    ContentDelivery.runtime_id_snapshot == runtime.id,
                    ContentDelivery.idempotency_key == key,
                )
            )
            if existing is not None:
                if existing.import_media != import_media:
                    raise ContentDeliveryError(
                        "CONTENT_DELIVERY_DUPLICATE",
                        "Idempotency key was already used with different options",
                    )
                return existing, False
        if not allow_repeat and key is None:
            existing = session.scalar(
                select(ContentDelivery)
                .where(
                    ContentDelivery.content_asset_version_id == version.id,
                    ContentDelivery.runtime_id_snapshot == runtime.id,
                    ContentDelivery.import_media == import_media,
                    ContentDelivery.status.in_(["pending", "delivering", "succeeded"]),
                )
                .order_by(ContentDelivery.created_at.desc(), ContentDelivery.id.desc())
            )
            if existing is not None:
                return existing, False

        delivery = ContentDelivery(
            content_asset_id=asset.id,
            content_asset_version_id=version.id,
            runtime_id=runtime.id,
            runtime_id_snapshot=runtime.id,
            idempotency_key=key,
            status="pending",
            import_media=import_media,
            remote_filename="pending",
            remote_path=str(REMOTE_ROOT / "pending"),
        )
        session.add(delivery)
        session.flush()
        delivery.remote_filename = self._remote_filename(
            delivery.id, filename, version.canonical_extension
        )
        delivery.remote_path = str(REMOTE_ROOT / delivery.remote_filename)
        job = Job(
            job_type="content.deliver",
            status=JobStatus.PENDING.value,
            runtime_id=runtime.id,
            account_id=None,
            payload={"content_delivery_id": delivery.id},
            max_attempts=3,
            execution_stage="queued",
        )
        session.add(job)
        session.flush()
        delivery.job_id = job.id
        event_type = "delivery_repeated" if allow_repeat else "delivery_requested"
        session.add(ContentEvent(
            content_asset_id=asset.id,
            content_asset_version_id=version.id,
            event_type=event_type,
            metadata_json={
                "delivery_id": delivery.id,
                "job_id": job.id,
                "runtime_id": runtime.id,
            },
        ))
        if not commit:
            return delivery, True
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            if key is not None:
                existing = session.scalar(select(ContentDelivery).where(
                    ContentDelivery.content_asset_version_id == version.id,
                    ContentDelivery.runtime_id_snapshot == runtime.id,
                    ContentDelivery.idempotency_key == key,
                ))
                if existing is not None and existing.import_media == import_media:
                    return existing, False
            raise ContentDeliveryError(
                "CONTENT_DELIVERY_DUPLICATE", "Content delivery already exists"
            ) from error
        session.refresh(delivery)
        return delivery, True

    @staticmethod
    def get(session: Session, delivery_id: int) -> ContentDelivery:
        delivery = session.get(ContentDelivery, delivery_id)
        if delivery is None:
            raise ContentDeliveryError(
                "CONTENT_DELIVERY_NOT_FOUND", "Content delivery was not found"
            )
        return delivery

    @staticmethod
    def record_event(
        session: Session,
        delivery: ContentDelivery,
        event_type: str,
        *,
        error_code: str | None = None,
    ) -> None:
        metadata: dict[str, object] = {
            "delivery_id": delivery.id,
            "job_id": delivery.job_id,
            "runtime_id": delivery.runtime_id_snapshot,
        }
        if error_code:
            metadata["error_code"] = error_code
        session.add(ContentEvent(
            content_asset_id=delivery.content_asset_id,
            content_asset_version_id=delivery.content_asset_version_id,
            event_type=event_type,
            metadata_json=metadata,
        ))

    @staticmethod
    def mark_cancelled_for_job(session: Session, job: Job) -> None:
        if job.job_type != "content.deliver":
            return
        delivery = session.scalar(select(ContentDelivery).where(ContentDelivery.job_id == job.id))
        if delivery is None or delivery.status in {"succeeded", "cancelled"}:
            return
        delivery.status = "cancelled"
        delivery.completed_at = utc_now()
        delivery.error_code = "CONTENT_DELIVERY_CANCELLED"
        delivery.error_message = "Content delivery was cancelled"
        ContentDeliveryService.record_event(
            session, delivery, "delivery_cancelled", error_code=delivery.error_code
        )

    @staticmethod
    def sync_failed_job(session: Session, job: Job) -> None:
        if job.job_type != "content.deliver":
            return
        delivery = session.scalar(select(ContentDelivery).where(ContentDelivery.job_id == job.id))
        if delivery is None or delivery.status in {"succeeded", "cancelled"}:
            return
        if job.status == JobStatus.PENDING.value:
            delivery.status = "pending"
            delivery.completed_at = None
        elif job.status == JobStatus.FAILED.value:
            delivery.status = "failed"
            delivery.completed_at = utc_now()
        delivery.error_code = job.error_code
        delivery.error_message = job.error_message

    @staticmethod
    def _validate_idempotency_key(value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not _IDEMPOTENCY_KEY.fullmatch(value):
            raise ContentDeliveryError(
                "INVALID_CONTENT_DELIVERY", "Idempotency key is invalid"
            )
        return value

    @staticmethod
    def _remote_filename(delivery_id: int, requested: str | None, extension: str) -> str:
        canonical_extension = extension.lstrip(".")
        if not canonical_extension or not canonical_extension.isalnum():
            raise ContentDeliveryError(
                "CONTENT_REMOTE_FILENAME_INVALID", "Remote filename is invalid"
            )
        try:
            safe = AutomationArtifactStore.normalize_filename(
                requested or f"content-{delivery_id}.{canonical_extension}"
            )
        except Exception as error:
            raise ContentDeliveryError(
                "CONTENT_REMOTE_FILENAME_INVALID", "Remote filename is invalid"
            ) from error
        stem = PurePosixPath(safe).stem[:180] or "content"
        # The inspected canonical extension is authoritative, not caller input.
        return f"{stem}-d{delivery_id}.{canonical_extension}"
