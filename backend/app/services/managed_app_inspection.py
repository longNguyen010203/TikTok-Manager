"""Authoritative state transitions for one immutable managed APK version."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ContentAsset, ContentAssetVersion, ManagedApp, ManagedAppEvent, ManagedAppVersion
from app.models.timestamps import utc_now
from app.services.apk_inspection import ApkInspectionError, ApkToolInspector
from app.services.content_operation_lock import ContentOperationLockBusy, ContentOperationLockError, ContentVersionOperationGuard
from app.services.content_storage import ContentStorageError, ContentStorageService


class ManagedAppInspectionService:
    def __init__(
        self, session: Session, *, storage: ContentStorageService,
        guard: ContentVersionOperationGuard, inspector: ApkToolInspector,
        cancellation_hook=None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.guard = guard
        self.inspector = inspector
        self.cancellation_hook = cancellation_hook

    def inspect(self, version_id: int) -> dict[str, Any]:
        version = self._load(version_id)
        try:
            with self.guard.acquire(version.content_asset_version_id, blocking=False):
                self.session.refresh(version)
                if version.status in {"ready", "invalid", "retired"}:
                    return self.result(version)
                self._cancel()
                self._event_once(version, "inspection_started", {"job_id": version.inspection_job_id})
                self.session.commit()
                try:
                    path = self.storage.verify_blob(version.content_asset_version.blob)
                    inspected = self.inspector.inspect(path)
                    self._cancel()
                    if inspected.package_name != version.managed_app.android_package_name:
                        raise ApkInspectionError("APK_PACKAGE_MISMATCH", "APK package does not match the managed app", retryable=False)
                    expected_signer = self._expected_signer(version)
                    if expected_signer is not None and inspected.signer_fingerprint != expected_signer:
                        raise ApkInspectionError("APK_SIGNER_MISMATCH", "APK signer does not match existing ready versions", retryable=False)
                    version.version_name = inspected.version_name
                    version.version_code = inspected.version_code
                    version.discovered_package_name = inspected.package_name
                    version.min_sdk = inspected.min_sdk
                    version.target_sdk = inspected.target_sdk
                    version.signer_fingerprint = inspected.signer_fingerprint
                    version.signer_metadata = {"fingerprints": list(inspected.signer_fingerprints)}
                    version.inspector_version = inspected.inspector_version
                    version.inspection_level = "verified"
                    version.status = "ready"
                    version.validated_at = utc_now()
                    version.error_code = version.error_message = None
                    content_version = version.content_asset_version
                    content_version.processing_status = "ready"
                    content_version.processed_at = utc_now()
                    content_version.error_code = content_version.error_message = None
                    version.content_asset.current_version_id = content_version.id
                    version.content_asset.status = "ready"
                    self._event_once(version, "version_ready", {
                        "package_name": inspected.package_name,
                        "version_code": inspected.version_code,
                    })
                    self.session.commit()
                    return self.result(version)
                except ContentStorageError as error:
                    raise ApkInspectionError("CONTENT_BLOB_MISSING", "Managed APK blob is unavailable", retryable=True) from error
                except ApkInspectionError as error:
                    if not error.retryable and error.code != "APP_INSPECTION_CANCELLED":
                        self._mark_invalid(version, error)
                    raise
        except ContentOperationLockBusy as error:
            raise ApkInspectionError("APP_INSPECTION_BUSY", "Managed app version is already inspecting", retryable=True) from error
        except ContentOperationLockError as error:
            raise ApkInspectionError("APK_INSPECTION_FAILED", "Managed app inspection lock is unavailable", retryable=True) from error

    def _load(self, version_id: int) -> ManagedAppVersion:
        version = self.session.scalar(
            select(ManagedAppVersion).where(ManagedAppVersion.id == version_id).options(
                selectinload(ManagedAppVersion.managed_app).selectinload(ManagedApp.versions),
                selectinload(ManagedAppVersion.content_asset),
                selectinload(ManagedAppVersion.content_asset_version).selectinload(ContentAssetVersion.blob),
            )
        )
        if (
            version is None
            or version.content_asset.id != version.content_asset_id
            or version.content_asset.purpose != "managed_app_package"
            or version.content_asset_version.content_asset_id != version.content_asset_id
            or version.sha256 != version.content_asset_version.blob.sha256
        ):
            raise ApkInspectionError("MANAGED_APP_VERSION_NOT_FOUND", "Managed app version was not found", retryable=False)
        return version

    def _expected_signer(self, version: ManagedAppVersion) -> str | None:
        current = self.session.get(ManagedAppVersion, version.managed_app.current_version_id) if version.managed_app.current_version_id else None
        if current is not None and current.status == "ready":
            return current.signer_fingerprint
        candidate = self.session.scalar(
            select(ManagedAppVersion).where(
                ManagedAppVersion.managed_app_id == version.managed_app_id,
                ManagedAppVersion.id != version.id,
                ManagedAppVersion.status == "ready",
                ManagedAppVersion.signer_fingerprint.is_not(None),
            ).order_by(ManagedAppVersion.id)
        )
        return candidate.signer_fingerprint if candidate else None

    def _mark_invalid(self, version: ManagedAppVersion, error: ApkInspectionError) -> None:
        version.status = "invalid"
        version.error_code = error.code
        version.error_message = error.safe_message
        version.validated_at = utc_now()
        version.content_asset_version.processing_status = "invalid"
        version.content_asset_version.error_code = error.code
        version.content_asset_version.error_message = error.safe_message
        version.content_asset_version.processed_at = utc_now()
        version.content_asset.status = "invalid"
        self._event_once(version, "version_invalid", {"error_code": error.code})
        self.session.commit()

    def _event_once(self, version: ManagedAppVersion, event_type: str, metadata: dict[str, Any]) -> None:
        existing = self.session.scalar(select(ManagedAppEvent.id).where(
            ManagedAppEvent.managed_app_version_id == version.id,
            ManagedAppEvent.event_type == event_type,
        ))
        if existing is None:
            self.session.add(ManagedAppEvent(
                managed_app_id=version.managed_app_id,
                managed_app_version_id=version.id,
                job_id=version.inspection_job_id,
                event_type=event_type,
                metadata_json=metadata,
            ))

    def _cancel(self) -> None:
        if self.cancellation_hook is not None and self.cancellation_hook():
            raise ApkInspectionError("APP_INSPECTION_CANCELLED", "App inspection was cancelled", retryable=True)

    @staticmethod
    def result(version: ManagedAppVersion) -> dict[str, Any]:
        return {
            "managed_app_id": version.managed_app_id,
            "managed_app_version_id": version.id,
            "status": version.status,
            "package_name": version.discovered_package_name,
            "version_name": version.version_name,
            "version_code": version.version_code,
            "min_sdk": version.min_sdk,
            "target_sdk": version.target_sdk,
            "signer_fingerprint": version.signer_fingerprint,
            "inspection_level": version.inspection_level,
            "error_code": version.error_code,
            "error_message": version.error_message,
        }
