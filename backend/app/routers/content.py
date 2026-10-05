"""Reusable content-library upload and metadata API."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import (
    ContentAsset, ContentAssetTag, ContentAssetVersion, ContentDelivery, ContentVariant,
)
from app.services.content_jobs import THUMBNAIL_PROFILE_FINGERPRINT
from app.schemas.content import (
    ContentAssetDetail,
    ContentAssetList,
    ContentAssetPatch,
    ContentAssetRead,
    ContentVersionRead,
    ContentDeliveryCreate,
    ContentDeliveryCreateRead,
    ContentDeliveryList,
    ContentDeliveryRead,
)
from app.services.content_assets import ContentAssetError, ContentAssetService
from app.services.content_delivery import ContentDeliveryError, ContentDeliveryService
from app.services.content_storage import ContentStorageError, ContentStorageService
from app.services.content_validation import ContentValidationError


router = APIRouter(prefix="/content", tags=["content"])
delivery_router = APIRouter(prefix="/content-deliveries", tags=["content"])
DatabaseSession = Annotated[Session, Depends(get_db)]
ContentId = Annotated[int, Path(gt=0)]


def _service() -> ContentAssetService:
    return ContentAssetService(ContentStorageService.from_application_config())


def _version_read(version: ContentAssetVersion) -> ContentVersionRead:
    return ContentVersionRead(
        id=version.id,
        version_number=version.version_number,
        original_filename=version.original_filename,
        detected_mime_type=version.detected_mime_type,
        canonical_extension=version.canonical_extension,
        processing_status=version.processing_status,
        size_bytes=version.blob.size_bytes,
        sha256=version.blob.sha256,
        width=version.width,
        height=version.height,
        duration_ms=version.duration_ms,
        codec=version.codec,
        container=version.container,
        frame_rate_numerator=version.frame_rate_numerator,
        frame_rate_denominator=version.frame_rate_denominator,
        audio_present=version.audio_present,
        bitrate=version.bitrate,
        sample_rate=version.sample_rate,
        channels=version.channels,
        orientation=version.orientation,
        metadata=version.metadata_json or {},
        created_at=version.created_at,
        processed_at=version.processed_at,
        error_code=version.error_code,
        error_message=version.error_message,
    )


def _asset_read(asset: ContentAsset, *, detail: bool = False):
    current = next(
        (version for version in asset.versions if version.id == asset.current_version_id),
        None,
    )
    deliveries = sorted(asset.deliveries, key=lambda item: (item.created_at, item.id), reverse=True)
    latest = deliveries[0] if deliveries else None
    last_success = next((item for item in deliveries if item.status == "succeeded"), None)
    values = dict(
        id=asset.id,
        asset_type=asset.asset_type,
        display_name=asset.display_name,
        notes=asset.notes,
        source=asset.source,
        status=asset.status,
        tags=sorted(tag.tag for tag in asset.tags),
        current_version=_version_read(current) if current is not None else None,
        thumbnail_available=bool(
            current is not None and any(
                variant.variant_kind == "thumbnail"
                and variant.profile_fingerprint == THUMBNAIL_PROFILE_FINGERPRINT
                and variant.status == "ready" and variant.blob_id is not None
                for variant in current.variants
            )
        ),
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        archived_at=asset.archived_at,
        deleted_at=asset.deleted_at,
        total_deliveries=len(deliveries),
        latest_delivery_status=latest.status if latest else None,
        last_successful_delivery_at=last_success.completed_at if last_success else None,
    )
    if detail:
        return ContentAssetDetail(
            **values,
            versions=[_version_read(version) for version in asset.versions],
        )
    return ContentAssetRead(**values)


def _raise_content_error(error: Exception) -> None:
    if isinstance(error, ContentValidationError):
        code, message, status_code = error.code, error.safe_message, 422
    elif isinstance(error, ContentStorageError):
        code, message = error.code, error.safe_message
        status_code = {
            "CONTENT_UPLOAD_TOO_LARGE": 413,
            "CONTENT_STORAGE_FULL": 507,
            "EMPTY_CONTENT": 422,
            "CONTENT_STORAGE_BUSY": 409,
        }.get(code, 503)
    elif isinstance(error, ContentAssetError):
        code, message = error.code, error.safe_message
        status_code = {
            "CONTENT_NOT_FOUND": 404,
            "CONTENT_DELETED": 409,
            "CONTENT_IN_USE": 409,
            "CONTENT_WRITE_CONFLICT": 409,
        }.get(code, 422)
    elif isinstance(error, ContentDeliveryError):
        code, message = error.code, error.safe_message
        status_code = {
            "CONTENT_NOT_FOUND": 404,
            "CONTENT_DELIVERY_NOT_FOUND": 404,
            "RUNTIME_NOT_FOUND": 404,
            "CONTENT_DELETED": 409,
            "CONTENT_NOT_READY": 409,
            "CONTENT_VERSION_NOT_READY": 409,
            "CONTENT_DELIVERY_DUPLICATE": 409,
        }.get(code, 422)
    else:  # pragma: no cover - caller contracts constrain this helper
        raise error
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    ) from error


@router.post("", response_model=ContentAssetDetail, status_code=status.HTTP_202_ACCEPTED)
def upload_content(
    session: DatabaseSession,
    file: Annotated[UploadFile, File()],
    display_name: Annotated[str, Form(min_length=1, max_length=255)],
    notes: Annotated[str | None, Form(max_length=4000)] = None,
    tags: Annotated[list[str] | None, Form()] = None,
) -> ContentAssetDetail:
    try:
        asset = _service().create_upload(
            session,
            stream=file.file,
            original_filename=file.filename or "",
            declared_mime_type=file.content_type,
            display_name=display_name,
            notes=notes,
            tags=tags or (),
        )
    except (ContentValidationError, ContentStorageError, ContentAssetError) as error:
        _raise_content_error(error)
    return _asset_read(asset, detail=True)


@router.get("", response_model=ContentAssetList)
def list_content(
    session: DatabaseSession,
    query: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    asset_type: Annotated[Literal["video", "image", "audio", "other"] | None, Query()] = None,
    asset_status: Annotated[
        Literal["processing", "ready", "invalid", "archived", "deleted"] | None,
        Query(alias="status"),
    ] = None,
    tag: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    source: Annotated[
        Literal["upload", "promoted_artifact", "generated", "imported"] | None,
        Query(),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ContentAssetList:
    filters = []
    if asset_status is None:
        filters.append(ContentAsset.status.notin_(["archived", "deleted"]))
    else:
        filters.append(ContentAsset.status == asset_status)
    if asset_type is not None:
        filters.append(ContentAsset.asset_type == asset_type)
    if source is not None:
        filters.append(ContentAsset.source == source)
    if query is not None:
        needle = f"%{query.strip().lower()}%"
        filters.append(
            or_(
                func.lower(ContentAsset.display_name).like(needle),
                func.lower(func.coalesce(ContentAsset.notes, "")).like(needle),
            )
        )
    statement = select(ContentAsset).where(*filters)
    if tag is not None:
        try:
            normalized_tag = ContentAssetService.normalize_tags([tag])[0]
        except (ContentValidationError, IndexError) as error:
            if isinstance(error, ContentValidationError):
                _raise_content_error(error)
            raise HTTPException(status_code=422, detail="Content tag is invalid") from error
        statement = statement.join(ContentAssetTag).where(ContentAssetTag.tag == normalized_tag)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    assets = list(
        session.scalars(
            statement.options(
                selectinload(ContentAsset.tags),
                selectinload(ContentAsset.versions).selectinload(ContentAssetVersion.blob),
                selectinload(ContentAsset.versions).selectinload(ContentAssetVersion.variants),
                selectinload(ContentAsset.deliveries),
            )
            .order_by(ContentAsset.created_at.desc(), ContentAsset.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return ContentAssetList(
        items=[_asset_read(asset) for asset in assets],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{content_id}", response_model=ContentAssetDetail)
def get_content(content_id: ContentId, session: DatabaseSession) -> ContentAssetDetail:
    try:
        asset = _service().get(session, content_id)
    except ContentAssetError as error:
        _raise_content_error(error)
    return _asset_read(asset, detail=True)


@router.post(
    "/{content_id}/deliver",
    response_model=ContentDeliveryCreateRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def deliver_content(
    content_id: ContentId,
    payload: ContentDeliveryCreate,
    session: DatabaseSession,
) -> ContentDeliveryCreateRead:
    try:
        delivery, created = ContentDeliveryService().create(
            session,
            content_asset_id=content_id,
            runtime_id=payload.runtime_id,
            version_id=payload.version_id,
            filename=payload.filename,
            import_media=payload.import_media,
            allow_repeat=payload.allow_repeat,
            idempotency_key=payload.idempotency_key,
        )
    except ContentDeliveryError as error:
        _raise_content_error(error)
    assert delivery.job is not None
    return ContentDeliveryCreateRead(
        delivery=ContentDeliveryRead.model_validate(delivery),
        job_status=delivery.job.status,
        created=created,
    )


@router.get("/{content_id}/deliveries", response_model=ContentDeliveryList)
def list_content_deliveries(
    content_id: ContentId,
    session: DatabaseSession,
    delivery_status: Annotated[
        Literal["pending", "delivering", "succeeded", "failed", "cancelled"] | None,
        Query(alias="status"),
    ] = None,
    runtime_id: Annotated[int | None, Query(gt=0)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ContentDeliveryList:
    if session.get(ContentAsset, content_id) is None:
        raise HTTPException(status_code=404, detail="Content not found")
    filters = [ContentDelivery.content_asset_id == content_id]
    if delivery_status is not None:
        filters.append(ContentDelivery.status == delivery_status)
    if runtime_id is not None:
        filters.append(ContentDelivery.runtime_id_snapshot == runtime_id)
    total = session.scalar(select(func.count()).select_from(ContentDelivery).where(*filters)) or 0
    items = list(session.scalars(
        select(ContentDelivery).where(*filters)
        .order_by(ContentDelivery.created_at.desc(), ContentDelivery.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all())
    return ContentDeliveryList(
        items=[ContentDeliveryRead.model_validate(item) for item in items],
        total=total, page=page, page_size=page_size,
    )


@delivery_router.get("/{delivery_id}", response_model=ContentDeliveryRead)
def get_content_delivery(
    delivery_id: Annotated[int, Path(gt=0)], session: DatabaseSession
) -> ContentDeliveryRead:
    try:
        delivery = ContentDeliveryService.get(session, delivery_id)
    except ContentDeliveryError as error:
        _raise_content_error(error)
    return ContentDeliveryRead.model_validate(delivery)


@router.patch("/{content_id}", response_model=ContentAssetDetail)
def patch_content(
    content_id: ContentId,
    payload: ContentAssetPatch,
    session: DatabaseSession,
) -> ContentAssetDetail:
    service = _service()
    try:
        asset = service.get(session, content_id)
        asset = service.update_metadata(
            session,
            asset,
            display_name=payload.display_name,
            display_name_set="display_name" in payload.model_fields_set,
            notes=payload.notes,
            notes_set="notes" in payload.model_fields_set,
            tags=payload.tags,
            archived=payload.archived,
        )
    except (ContentValidationError, ContentStorageError, ContentAssetError) as error:
        _raise_content_error(error)
    return _asset_read(asset, detail=True)


@router.delete("/{content_id}", response_model=ContentAssetDetail)
def delete_content(content_id: ContentId, session: DatabaseSession) -> ContentAssetDetail:
    service = _service()
    try:
        asset = service.soft_delete(session, service.get(session, content_id))
    except (ContentStorageError, ContentAssetError) as error:
        _raise_content_error(error)
    return _asset_read(asset, detail=True)


@router.get("/{content_id}/versions", response_model=list[ContentVersionRead])
def list_content_versions(
    content_id: ContentId, session: DatabaseSession
) -> list[ContentVersionRead]:
    try:
        asset = _service().get(session, content_id)
    except ContentAssetError as error:
        _raise_content_error(error)
    return [_version_read(version) for version in asset.versions]


@router.post(
    "/{content_id}/versions",
    response_model=ContentAssetDetail,
    status_code=status.HTTP_202_ACCEPTED,
)
def upload_content_version(
    content_id: ContentId,
    session: DatabaseSession,
    file: Annotated[UploadFile, File()],
) -> ContentAssetDetail:
    service = _service()
    try:
        asset = service.get(session, content_id)
        asset = service.create_replacement(
            session,
            asset=asset,
            stream=file.file,
            original_filename=file.filename or "",
            declared_mime_type=file.content_type,
        )
    except (ContentValidationError, ContentStorageError, ContentAssetError) as error:
        _raise_content_error(error)
    return _asset_read(asset, detail=True)


@router.get("/{content_id}/download")
def download_content(content_id: ContentId, session: DatabaseSession) -> FileResponse:
    service = _service()
    try:
        asset = service.get(session, content_id)
        if asset.status == "deleted":
            raise HTTPException(
                status_code=410,
                detail={"code": "CONTENT_DELETED", "message": "Content was deleted"},
            )
        version = next(
            (item for item in asset.versions if item.id == asset.current_version_id),
            None,
        )
        if version is None or version.processing_status != "ready" or version.blob.status != "active":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "CONTENT_NOT_READY",
                    "message": "Content has no usable current version",
                },
            )
        path = service.storage.path_for(version.blob)
    except (ContentStorageError, ContentAssetError) as error:
        _raise_content_error(error)
    return FileResponse(
        path,
        media_type=version.detected_mime_type,
        filename=version.original_filename,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/{content_id}/thumbnail")
def download_content_thumbnail(
    content_id: ContentId, session: DatabaseSession
) -> FileResponse:
    try:
        asset = _service().get(session, content_id)
        if asset.status == "deleted":
            raise HTTPException(
                status_code=410,
                detail={"code": "CONTENT_DELETED", "message": "Content was deleted"},
            )
        version = next(
            (item for item in asset.versions if item.id == asset.current_version_id), None
        )
        variant = next(
            (
                item for item in (version.variants if version is not None else [])
                if item.variant_kind == "thumbnail"
                and item.profile_fingerprint == THUMBNAIL_PROFILE_FINGERPRINT
                and item.status == "ready" and item.blob is not None
            ),
            None,
        )
        if variant is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "CONTENT_THUMBNAIL_UNAVAILABLE",
                    "message": "Content thumbnail is unavailable",
                },
            )
        path = _service().storage.path_for(variant.blob)
    except (ContentStorageError, ContentAssetError) as error:
        _raise_content_error(error)
    return FileResponse(
        path,
        media_type="image/jpeg",
        filename=f"content-{content_id}-thumbnail.jpg",
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300"},
    )
