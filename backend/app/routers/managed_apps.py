"""Operator APIs for managed Android app definitions and immutable APK versions."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import load_application_config
from app.database import get_db
from app.models import ManagedApp, ManagedAppVersion
from app.schemas.managed_app import (
    ManagedAppCreate, ManagedAppDetail, ManagedAppList, ManagedAppPatch,
    ManagedAppRead, ManagedAppVersionList, ManagedAppVersionRead,
    ManagedAppVersionUploadRead,
)
from app.services.apk_admission import ApkAdmissionError
from app.services.content_storage import ContentStorageError, ContentStorageService
from app.services.content_validation import ContentValidationError
from app.services.managed_apps import ManagedAppError, ManagedAppService


router = APIRouter(prefix="/managed-apps", tags=["managed-apps"])
DatabaseSession = Annotated[Session, Depends(get_db)]
AppId = Annotated[int, Path(gt=0)]
VersionId = Annotated[int, Path(gt=0)]


def _service() -> ManagedAppService:
    config = load_application_config()
    return ManagedAppService(
        ContentStorageService(
            config.content_root,
            max_upload_bytes=config.managed_app_max_apk_bytes,
            max_total_bytes=config.content_max_total_bytes,
        ),
        zip_max_entries=config.managed_app_zip_max_entries,
        zip_max_expanded_bytes=config.managed_app_zip_max_expanded_bytes,
        zip_max_compression_ratio=config.managed_app_zip_max_compression_ratio,
    )


def _version_read(version: ManagedAppVersion) -> ManagedAppVersionRead:
    return ManagedAppVersionRead(
        id=version.id,
        managed_app_id=version.managed_app_id,
        version_name=version.version_name,
        version_code=version.version_code,
        sha256=version.sha256,
        discovered_package_name=version.discovered_package_name,
        min_sdk=version.min_sdk,
        target_sdk=version.target_sdk,
        signer_fingerprint=version.signer_fingerprint,
        inspection_level=version.inspection_level,
        package_verification=(
            "pre_and_post_install"
            if version.inspection_level == "verified"
            else "post_install"
        ),
        basic_approved=version.basic_approved_at is not None,
        basic_approved_at=version.basic_approved_at,
        status=version.status,
        inspection_job_id=version.inspection_job_id,
        inspector_name=version.inspector_name,
        inspector_version=version.inspector_version,
        validated_at=version.validated_at,
        error_code=version.error_code,
        error_message=version.error_message,
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


def _app_read(app: ManagedApp, *, detail: bool = False):
    values = dict(
        id=app.id,
        key=app.key,
        display_name=app.display_name,
        android_package_name=app.android_package_name,
        status=app.status,
        install_policy=app.install_policy,
        current_version_id=app.current_version_id,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )
    if detail:
        return ManagedAppDetail(
            **values,
            versions=[_version_read(item) for item in sorted(app.versions, key=lambda row: row.id, reverse=True)],
        )
    return ManagedAppRead(**values)


def _raise(error: Exception) -> None:
    if isinstance(error, ManagedAppError):
        status_code = {
            "MANAGED_APP_NOT_FOUND": 404,
            "MANAGED_APP_VERSION_NOT_FOUND": 404,
            "MANAGED_APP_CONFLICT": 409,
            "MANAGED_APP_VERSION_CONFLICT": 409,
            "MANAGED_APP_ARCHIVED": 409,
            "MANAGED_APP_VERSION_NOT_READY": 409,
            "MANAGED_APP_VERSION_ACTIVE": 409,
            "MANAGED_APP_VERSION_BUSY": 409,
        }.get(error.code, 422)
        code, message = error.code, error.safe_message
    elif isinstance(error, ApkAdmissionError):
        status_code, code, message = 422, error.code, error.safe_message
    elif isinstance(error, ContentValidationError):
        status_code, code, message = 422, error.code, error.safe_message
    elif isinstance(error, ContentStorageError):
        status_code = {"CONTENT_UPLOAD_TOO_LARGE": 413, "CONTENT_STORAGE_FULL": 507}.get(error.code, 503)
        code, message = error.code, error.safe_message
    else:  # pragma: no cover
        raise error
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message}) from error


@router.get("", response_model=ManagedAppList)
def list_managed_apps(
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ManagedAppList:
    total = session.scalar(select(func.count()).select_from(ManagedApp)) or 0
    items = list(session.scalars(
        select(ManagedApp).order_by(ManagedApp.created_at.desc(), ManagedApp.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all())
    return ManagedAppList(items=[_app_read(item) for item in items], total=total, page=page, page_size=page_size)


@router.post("", response_model=ManagedAppDetail, status_code=status.HTTP_201_CREATED)
def create_managed_app(payload: ManagedAppCreate, session: DatabaseSession) -> ManagedAppDetail:
    try:
        app, _created = ManagedAppService.create(
            session,
            key=payload.key,
            display_name=payload.display_name,
            android_package_name=payload.android_package_name,
            install_policy=payload.install_policy,
        )
        return _app_read(ManagedAppService.get(session, app.id), detail=True)
    except ManagedAppError as error:
        _raise(error)


@router.get("/{app_id}", response_model=ManagedAppDetail)
def get_managed_app(app_id: AppId, session: DatabaseSession) -> ManagedAppDetail:
    try:
        return _app_read(ManagedAppService.get(session, app_id), detail=True)
    except ManagedAppError as error:
        _raise(error)


@router.patch("/{app_id}", response_model=ManagedAppDetail)
def patch_managed_app(app_id: AppId, payload: ManagedAppPatch, session: DatabaseSession) -> ManagedAppDetail:
    try:
        app = ManagedAppService.get(session, app_id)
        ManagedAppService.update(
            session, app,
            display_name=payload.display_name if "display_name" in payload.model_fields_set else None,
            status=payload.status if "status" in payload.model_fields_set else None,
            install_policy=payload.install_policy if "install_policy" in payload.model_fields_set else None,
        )
        return _app_read(ManagedAppService.get(session, app_id), detail=True)
    except ManagedAppError as error:
        _raise(error)


@router.post("/{app_id}/versions", response_model=ManagedAppVersionUploadRead, status_code=status.HTTP_202_ACCEPTED)
def upload_managed_app_version(
    app_id: AppId,
    session: DatabaseSession,
    file: Annotated[UploadFile, File()],
    display_name: Annotated[str | None, Form(min_length=1, max_length=255)] = None,
) -> ManagedAppVersionUploadRead:
    try:
        app = ManagedAppService.get(session, app_id)
        version, created = _service().upload_version(
            session,
            app=app,
            stream=file.file,
            original_filename=file.filename or "",
            declared_mime_type=file.content_type,
            display_name=display_name,
        )
        return ManagedAppVersionUploadRead(version=_version_read(version), created=created)
    except (ManagedAppError, ApkAdmissionError, ContentStorageError, ContentValidationError) as error:
        _raise(error)


@router.get("/{app_id}/versions", response_model=ManagedAppVersionList)
def list_managed_app_versions(
    app_id: AppId,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ManagedAppVersionList:
    try:
        ManagedAppService.get(session, app_id)
    except ManagedAppError as error:
        _raise(error)
    filters = [ManagedAppVersion.managed_app_id == app_id]
    total = session.scalar(select(func.count()).select_from(ManagedAppVersion).where(*filters)) or 0
    items = list(session.scalars(
        select(ManagedAppVersion).where(*filters)
        .order_by(ManagedAppVersion.created_at.desc(), ManagedAppVersion.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all())
    return ManagedAppVersionList(items=[_version_read(item) for item in items], total=total, page=page, page_size=page_size)


@router.get("/{app_id}/versions/{version_id}", response_model=ManagedAppVersionRead)
def get_managed_app_version(app_id: AppId, version_id: VersionId, session: DatabaseSession) -> ManagedAppVersionRead:
    version = session.get(ManagedAppVersion, version_id)
    if version is None or version.managed_app_id != app_id:
        _raise(ManagedAppError("MANAGED_APP_VERSION_NOT_FOUND", "Managed app version was not found"))
    return _version_read(version)


@router.post("/{app_id}/versions/{version_id}/activate", response_model=ManagedAppDetail)
def activate_managed_app_version(app_id: AppId, version_id: VersionId, session: DatabaseSession) -> ManagedAppDetail:
    try:
        app = ManagedAppService.get(session, app_id)
        ManagedAppService.activate(session, app, version_id)
        return _app_read(ManagedAppService.get(session, app_id), detail=True)
    except ManagedAppError as error:
        _raise(error)


@router.post("/{app_id}/versions/{version_id}/approve-basic", response_model=ManagedAppVersionRead)
def approve_basic_managed_app_version(
    app_id: AppId, version_id: VersionId, session: DatabaseSession
) -> ManagedAppVersionRead:
    try:
        app = ManagedAppService.get(session, app_id)
        return _version_read(ManagedAppService.approve_basic(session, app, version_id))
    except ManagedAppError as error:
        _raise(error)


@router.post("/{app_id}/versions/{version_id}/retire", response_model=ManagedAppVersionRead)
def retire_managed_app_version(app_id: AppId, version_id: VersionId, session: DatabaseSession) -> ManagedAppVersionRead:
    try:
        app = ManagedAppService.get(session, app_id)
        return _version_read(ManagedAppService.retire(session, app, version_id))
    except ManagedAppError as error:
        _raise(error)
