"""Transactional ManagedApp admission, metadata, and activation service."""

from __future__ import annotations

import re
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    ContentAsset, ContentAssetVersion, ManagedApp, ManagedAppEvent, ManagedAppVersion,
    RuntimeAppInstallation,
)
from app.models.timestamps import utc_now
from app.services.runtime_apps import _event as runtime_app_event
from app.services.apk_admission import ApkAdmissionError, validate_apk_archive
from app.services.content_storage import ContentStorageError, ContentStorageService
from app.services.content_validation import DetectedContent, ContentValidationError, normalize_content_filename
from app.services.managed_app_jobs import enqueue_app_inspection


_KEY = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_PACKAGE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$")
APK_CONTENT = DetectedContent(
    "other", "application/vnd.android.package-archive", ".apk", frozenset({".apk"})
)


class ManagedAppError(RuntimeError):
    def __init__(self, code: str, safe_message: str) -> None:
        self.code = code
        self.safe_message = safe_message
        super().__init__(safe_message)


class ManagedAppService:
    def __init__(
        self,
        storage: ContentStorageService,
        *,
        zip_max_entries: int,
        zip_max_expanded_bytes: int,
        zip_max_compression_ratio: int,
    ) -> None:
        self.storage = storage
        self.zip_max_entries = zip_max_entries
        self.zip_max_expanded_bytes = zip_max_expanded_bytes
        self.zip_max_compression_ratio = zip_max_compression_ratio

    @staticmethod
    def create(
        session: Session, *, key: str, display_name: str,
        android_package_name: str, install_policy: str,
    ) -> tuple[ManagedApp, bool]:
        safe_key = key.strip().lower()
        safe_name = display_name.strip()
        safe_package = android_package_name.strip()
        if not _KEY.fullmatch(safe_key):
            raise ManagedAppError("MANAGED_APP_KEY_INVALID", "Managed app key is invalid")
        if not safe_name or len(safe_name) > 255:
            raise ManagedAppError("MANAGED_APP_NAME_INVALID", "Managed app name is invalid")
        if not _PACKAGE.fullmatch(safe_package):
            raise ManagedAppError("ANDROID_PACKAGE_INVALID", "Android package name is invalid")
        existing = session.scalar(select(ManagedApp).where(ManagedApp.key == safe_key))
        if existing is not None:
            if (
                existing.display_name == safe_name
                and existing.android_package_name == safe_package
                and existing.install_policy == install_policy
            ):
                return existing, False
            raise ManagedAppError("MANAGED_APP_CONFLICT", "Managed app key already exists")
        if session.scalar(select(ManagedApp).where(ManagedApp.android_package_name == safe_package)):
            raise ManagedAppError("MANAGED_APP_CONFLICT", "Android package is already managed")
        app = ManagedApp(
            key=safe_key, display_name=safe_name, android_package_name=safe_package,
            status="active", install_policy=install_policy,
        )
        session.add(app)
        session.flush()
        session.add(ManagedAppEvent(
            managed_app_id=app.id, event_type="app_created",
            metadata_json={"key": safe_key, "install_policy": install_policy},
        ))
        session.commit()
        session.refresh(app)
        return app, True

    @staticmethod
    def get(session: Session, app_id: int) -> ManagedApp:
        app = session.scalar(
            select(ManagedApp).where(ManagedApp.id == app_id)
            .options(selectinload(ManagedApp.versions))
        )
        if app is None:
            raise ManagedAppError("MANAGED_APP_NOT_FOUND", "Managed app was not found")
        return app

    @staticmethod
    def update(
        session: Session, app: ManagedApp, *, display_name: str | None,
        status: str | None, install_policy: str | None,
    ) -> ManagedApp:
        if display_name is not None:
            name = display_name.strip()
            if not name or len(name) > 255:
                raise ManagedAppError("MANAGED_APP_NAME_INVALID", "Managed app name is invalid")
            app.display_name = name
        if status is not None:
            app.status = status
        if install_policy is not None:
            app.install_policy = install_policy
        session.add(ManagedAppEvent(
            managed_app_id=app.id, event_type="app_updated",
            metadata_json={
                "display_name_changed": display_name is not None,
                "status": status,
                "install_policy": install_policy,
            },
        ))
        session.commit()
        session.refresh(app)
        return app

    def upload_version(
        self,
        session: Session,
        *,
        app: ManagedApp,
        stream: BinaryIO,
        original_filename: str,
        declared_mime_type: str | None,
        display_name: str | None,
    ) -> tuple[ManagedAppVersion, bool]:
        if app.status == "archived":
            raise ManagedAppError("MANAGED_APP_ARCHIVED", "Archived apps cannot accept versions")
        staged = self.storage.stage_stream(stream)
        installed_key: str | None = None
        try:
            safe_filename = normalize_content_filename(original_filename)
            extension = Path(safe_filename).suffix.lower()
            if extension and extension != ".apk":
                raise ApkAdmissionError("APK_TYPE_MISMATCH", "Package filename must use the APK extension")
            declared = (declared_mime_type or "application/octet-stream").split(";", 1)[0].strip().lower()
            if declared not in {"", "application/octet-stream", APK_CONTENT.mime_type, "application/zip"}:
                raise ApkAdmissionError("APK_TYPE_MISMATCH", "Declared content type is not an APK")
            with self.storage.open_staged(staged) as package_stream:
                validate_apk_archive(
                    package_stream,
                    max_entries=self.zip_max_entries,
                    max_expanded_bytes=self.zip_max_expanded_bytes,
                    max_compression_ratio=self.zip_max_compression_ratio,
                )
            existing = session.scalar(select(ManagedAppVersion).where(
                ManagedAppVersion.managed_app_id == app.id,
                ManagedAppVersion.sha256 == staged.sha256,
            ))
            if existing is not None:
                return existing, False
            with self.storage.maintenance_lock():
                materialized = self.storage.materialize_blob(session, staged, APK_CONTENT)
                installed_key = materialized.installed_storage_key
                asset = ContentAsset(
                    asset_type="other",
                    display_name=(display_name or safe_filename)[:255],
                    notes=None,
                    source="upload",
                    purpose="managed_app_package",
                    status="processing",
                )
                session.add(asset)
                session.flush()
                content_version = ContentAssetVersion(
                    content_asset_id=asset.id,
                    version_number=1,
                    blob_id=materialized.blob.id,
                    original_filename=safe_filename,
                    detected_mime_type=APK_CONTENT.mime_type,
                    canonical_extension=".apk",
                    processing_status="processing",
                )
                session.add(content_version)
                session.flush()
                version = ManagedAppVersion(
                    managed_app_id=app.id,
                    content_asset_id=asset.id,
                    content_asset_version_id=content_version.id,
                    sha256=staged.sha256,
                    status="uploaded",
                    inspector_name="aapt2+apksigner",
                )
                session.add(version)
                session.flush()
                session.add(ManagedAppEvent(
                    managed_app_id=app.id,
                    managed_app_version_id=version.id,
                    event_type="version_uploaded",
                    metadata_json={
                        "size_bytes": staged.size_bytes,
                        "sha256": staged.sha256,
                        "deduplicated": not materialized.created,
                    },
                ))
                job = enqueue_app_inspection(session, version)
                session.add(ManagedAppEvent(
                    managed_app_id=app.id,
                    managed_app_version_id=version.id,
                    job_id=job.id,
                    event_type="inspection_queued",
                    metadata_json={"job_id": job.id},
                ))
                session.commit()
                installed_key = None
            session.refresh(version)
            return version, True
        except (ApkAdmissionError, ContentStorageError, ContentValidationError, ManagedAppError):
            session.rollback()
            if installed_key is not None:
                self.storage.remove_installed(installed_key)
            raise
        except IntegrityError as error:
            session.rollback()
            if installed_key is not None:
                self.storage.remove_installed(installed_key)
            existing = session.scalar(select(ManagedAppVersion).where(
                ManagedAppVersion.managed_app_id == app.id,
                ManagedAppVersion.sha256 == staged.sha256,
            ))
            if existing is not None:
                return existing, False
            raise ManagedAppError("MANAGED_APP_VERSION_CONFLICT", "Managed app version upload conflicted") from error
        finally:
            self.storage.discard_staged(staged)

    @staticmethod
    def is_installable(app: ManagedApp, version: ManagedAppVersion) -> bool:
        if version.managed_app_id != app.id or version.status != "ready":
            return False
        if version.inspection_level == "verified":
            return (
                version.discovered_package_name == app.android_package_name
                and version.version_code is not None
            )
        return version.inspection_level == "basic" and version.basic_approved_at is not None

    @staticmethod
    def approve_basic(
        session: Session, app: ManagedApp, version_id: int
    ) -> ManagedAppVersion:
        version = session.get(ManagedAppVersion, version_id)
        if version is None or version.managed_app_id != app.id:
            raise ManagedAppError(
                "MANAGED_APP_VERSION_NOT_FOUND", "Managed app version was not found"
            )
        if version.status in {"invalid", "retired"}:
            raise ManagedAppError(
                "MANAGED_APP_VERSION_NOT_READY",
                "Invalid or retired managed app versions cannot be approved",
            )
        if version.inspection_level == "verified":
            return version
        if version.basic_approved_at is not None:
            return version

        # Creation of a ManagedAppVersion is possible only after bounded APK
        # archive admission succeeds. Revalidate its immutable ownership links;
        # the content bytes themselves are verified again immediately pre-install.
        content_version = session.get(
            ContentAssetVersion, version.content_asset_version_id
        )
        asset = session.get(ContentAsset, version.content_asset_id)
        if (
            asset is None
            or content_version is None
            or asset.purpose != "managed_app_package"
            or content_version.content_asset_id != asset.id
        ):
            raise ManagedAppError(
                "MANAGED_APP_VERSION_NOT_READY", "Managed app package admission is invalid"
            )
        now = utc_now()
        version.inspection_level = "basic"
        version.basic_approved_at = now
        version.status = "ready"
        version.error_code = None
        version.error_message = None
        content_version.processing_status = "ready"
        content_version.processed_at = now
        content_version.error_code = None
        content_version.error_message = None
        asset.current_version_id = content_version.id
        asset.status = "ready"
        session.add(ManagedAppEvent(
            managed_app_id=app.id,
            managed_app_version_id=version.id,
            event_type="version_basic_approved",
            metadata_json={"inspection_level": "basic", "sha256": version.sha256},
        ))
        session.commit()
        session.refresh(version)
        return version

    @staticmethod
    def activate(session: Session, app: ManagedApp, version_id: int) -> ManagedApp:
        version = session.get(ManagedAppVersion, version_id)
        if version is None or version.managed_app_id != app.id:
            raise ManagedAppError("MANAGED_APP_VERSION_NOT_FOUND", "Managed app version was not found")
        if not ManagedAppService.is_installable(app, version):
            raise ManagedAppError("MANAGED_APP_VERSION_NOT_READY", "Managed app version is not ready")
        if app.current_version_id == version.id:
            return app
        app.current_version_id = version.id
        installations = list(session.scalars(select(RuntimeAppInstallation).where(
            RuntimeAppInstallation.managed_app_id == app.id,
            RuntimeAppInstallation.runtime_id.is_not(None),
        )).all())
        for installation in installations:
            if installation.desired_managed_app_version_id == version.id:
                continue
            installation.desired_managed_app_version_id = version.id
            installation.status = "outdated"
            installation.error_code = None
            installation.error_message = None
            session.add(runtime_app_event(installation, "marked_outdated"))
        session.add(ManagedAppEvent(
            managed_app_id=app.id, managed_app_version_id=version.id,
            event_type="version_activated", metadata_json={"version_id": version.id},
        ))
        session.commit()
        session.refresh(app)
        return app

    @staticmethod
    def retire(session: Session, app: ManagedApp, version_id: int) -> ManagedAppVersion:
        version = session.get(ManagedAppVersion, version_id)
        if version is None or version.managed_app_id != app.id:
            raise ManagedAppError("MANAGED_APP_VERSION_NOT_FOUND", "Managed app version was not found")
        if app.current_version_id == version.id:
            raise ManagedAppError("MANAGED_APP_VERSION_ACTIVE", "Activate another version before retiring the current version")
        if version.status == "inspecting":
            raise ManagedAppError("MANAGED_APP_VERSION_BUSY", "Inspecting versions cannot be retired")
        if version.status == "retired":
            return version
        version.status = "retired"
        session.add(ManagedAppEvent(
            managed_app_id=app.id, managed_app_version_id=version.id,
            event_type="version_retired", metadata_json={"version_id": version.id},
        ))
        session.commit()
        session.refresh(version)
        return version
