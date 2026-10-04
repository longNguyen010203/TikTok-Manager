"""Authoritative image/media inspection and atomic ContentAsset transitions."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ContentAsset, ContentAssetVersion, ContentEvent
from app.models.timestamps import utc_now
from app.services.content_operation_lock import (
    ContentOperationLockBusy,
    ContentOperationLockError,
    ContentVersionOperationGuard,
)
from app.services.content_storage import ContentStorageError, ContentStorageService
from app.services.media_probe import FfprobeInspector, MediaProbeError, ProbedMedia


class ContentProcessingError(RuntimeError):
    def __init__(self, code: str, safe_message: str, *, retryable: bool) -> None:
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable
        super().__init__(safe_message)


@dataclass(frozen=True)
class ImageMetadata:
    width: int
    height: int
    format: str
    orientation: int | None
    animated: bool
    frame_count: int


CancellationHook = Callable[[], bool]


class ContentInspectionService:
    def __init__(
        self,
        session: Session,
        *,
        storage: ContentStorageService,
        guard: ContentVersionOperationGuard,
        ffprobe: FfprobeInspector,
        max_image_dimension: int,
        max_image_pixels: int,
        max_image_frames: int,
        cancellation_hook: CancellationHook | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.guard = guard
        self.ffprobe = ffprobe
        self.max_image_dimension = max_image_dimension
        self.max_image_pixels = max_image_pixels
        self.max_image_frames = max_image_frames
        self.cancellation_hook = cancellation_hook

    def inspect(self, asset_id: int, version_id: int) -> dict[str, Any]:
        try:
            with self.guard.acquire(version_id, blocking=False):
                try:
                    version = self._load(asset_id, version_id)
                    if version.processing_status in {"ready", "invalid"}:
                        return self.result(version)
                    self._cancel()
                    self._event_once(version, "processing_started")
                    self.session.commit()
                    try:
                        path = self.storage.verify_blob(version.blob)
                    except ContentStorageError as error:
                        raise ContentProcessingError(
                            "CONTENT_BLOB_MISSING",
                            "Content blob is unavailable",
                            retryable=True,
                        ) from error
                    self._cancel()
                    try:
                        if version.asset.asset_type == "image":
                            inspected: ImageMetadata | ProbedMedia = self._inspect_image(
                                path, version.detected_mime_type
                            )
                        else:
                            inspected = self.ffprobe.probe(path, version.detected_mime_type)
                    except MediaProbeError as error:
                        raise ContentProcessingError(
                            error.code, error.safe_message, retryable=error.retryable
                        ) from error
                    self._cancel()
                    self._mark_ready(version, inspected)
                    return self.result(version)
                except ContentProcessingError as error:
                    if (
                        not error.retryable
                        and error.code != "CONTENT_PROCESSING_CANCELLED"
                        and "version" in locals()
                        and version.processing_status == "processing"
                    ):
                        self._mark_invalid(version, error)
                    raise
        except ContentOperationLockBusy as error:
            raise ContentProcessingError(
                "CONTENT_PROCESSING_BUSY",
                "Content version is already processing",
                retryable=True,
            ) from error
        except ContentOperationLockError as error:
            raise ContentProcessingError(
                "CONTENT_PROCESSING_FAILED",
                "Content inspection lock is unavailable",
                retryable=True,
            ) from error

    def _load(self, asset_id: int, version_id: int) -> ContentAssetVersion:
        version = self.session.scalar(
            select(ContentAssetVersion)
            .where(
                ContentAssetVersion.id == version_id,
                ContentAssetVersion.content_asset_id == asset_id,
            )
            .options(
                selectinload(ContentAssetVersion.asset).selectinload(ContentAsset.versions),
                selectinload(ContentAssetVersion.blob),
            )
        )
        if version is None:
            raise ContentProcessingError(
                "CONTENT_VERSION_NOT_FOUND", "Content version was not found", retryable=False
            )
        if version.blob.status != "active":
            raise ContentProcessingError(
                "CONTENT_BLOB_MISSING", "Content blob is unavailable", retryable=True
            )
        return version

    def _inspect_image(self, path: Path, expected_mime: str) -> ImageMetadata:
        expected_format = {
            "image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"
        }.get(expected_mime)
        if expected_format is None:
            raise ContentProcessingError(
                "CONTENT_MEDIA_UNSUPPORTED", "Image format is unsupported", retryable=False
            )
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as image:
                    width, height = image.size
                    image_format = image.format
                    frame_count = int(getattr(image, "n_frames", 1))
                    animated = bool(getattr(image, "is_animated", False))
                    image.verify()
                if (
                    width <= 0 or height <= 0
                    or width > self.max_image_dimension
                    or height > self.max_image_dimension
                    or width * height > self.max_image_pixels
                ):
                    raise ContentProcessingError(
                        "CONTENT_IMAGE_TOO_LARGE", "Image dimensions exceed safe limits", retryable=False
                    )
                if not 1 <= frame_count <= self.max_image_frames:
                    raise ContentProcessingError(
                        "CONTENT_IMAGE_TOO_LARGE", "Image frame count exceeds safe limits", retryable=False
                    )
                if image_format != expected_format:
                    raise ContentProcessingError(
                        "CONTENT_IMAGE_INVALID", "Image format does not match admission", retryable=False
                    )
                with Image.open(path) as image:
                    orientation_value = image.getexif().get(274)
                    orientation = int(orientation_value) if orientation_value is not None else None
                    for frame in range(frame_count):
                        self._cancel()
                        image.seek(frame)
                        image.load()
        except ContentProcessingError:
            raise
        except (UnidentifiedImageError, OSError, RuntimeError, SyntaxError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
            raise ContentProcessingError(
                "CONTENT_IMAGE_INVALID", "Image could not be decoded", retryable=False
            ) from error
        return ImageMetadata(width, height, expected_format, orientation, animated, frame_count)

    def _mark_ready(
        self, version: ContentAssetVersion, inspected: ImageMetadata | ProbedMedia
    ) -> None:
        if isinstance(inspected, ImageMetadata):
            version.width = inspected.width
            version.height = inspected.height
            version.orientation = inspected.orientation
            version.metadata_json = {
                "format": inspected.format,
                "animated": inspected.animated,
                "frame_count": inspected.frame_count,
            }
        else:
            version.width = inspected.width
            version.height = inspected.height
            version.duration_ms = inspected.duration_ms
            version.codec = inspected.codec
            version.container = inspected.container
            version.frame_rate_numerator = inspected.frame_rate_numerator
            version.frame_rate_denominator = inspected.frame_rate_denominator
            version.audio_present = inspected.audio_present
            version.bitrate = inspected.bitrate
            version.sample_rate = inspected.sample_rate
            version.channels = inspected.channels
            version.orientation = inspected.orientation
            version.metadata_json = inspected.metadata
        version.processing_status = "ready"
        version.processed_at = utc_now()
        version.error_code = None
        version.error_message = None
        asset = version.asset
        current = next(
            (candidate for candidate in asset.versions if candidate.id == asset.current_version_id),
            None,
        )
        if current is None or version.version_number > current.version_number:
            asset.current_version_id = version.id
        if asset.status not in {"archived", "deleted"}:
            asset.status = "ready"
        self._event_once(version, "ready")
        self.session.commit()

    def _mark_invalid(
        self, version: ContentAssetVersion, error: ContentProcessingError
    ) -> None:
        version.processing_status = "invalid"
        version.processed_at = utc_now()
        version.error_code = error.code
        version.error_message = error.safe_message[:500]
        asset = version.asset
        current = next(
            (
                candidate for candidate in asset.versions
                if candidate.id == asset.current_version_id
                and candidate.processing_status == "ready"
            ),
            None,
        )
        if asset.status not in {"archived", "deleted"}:
            asset.status = "ready" if current is not None else "invalid"
        self._event_once(
            version, "invalid", {"error_code": error.code}
        )
        self.session.commit()

    def _event_once(
        self,
        version: ContentAssetVersion,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        exists = self.session.scalar(
            select(ContentEvent.id).where(
                ContentEvent.content_asset_version_id == version.id,
                ContentEvent.event_type == event_type,
            )
        )
        if exists is None:
            self.session.add(
                ContentEvent(
                    content_asset_id=version.content_asset_id,
                    content_asset_version_id=version.id,
                    event_type=event_type,
                    metadata_json=metadata,
                )
            )

    def _cancel(self) -> None:
        if self.cancellation_hook is not None and self.cancellation_hook():
            raise ContentProcessingError(
                "CONTENT_PROCESSING_CANCELLED",
                "Content inspection was cancelled",
                retryable=True,
            )

    @staticmethod
    def result(version: ContentAssetVersion) -> dict[str, Any]:
        return {
            "content_asset_id": version.content_asset_id,
            "content_asset_version_id": version.id,
            "processing_status": version.processing_status,
            "width": version.width,
            "height": version.height,
            "duration_ms": version.duration_ms,
            "codec": version.codec,
            "container": version.container,
            "metadata": version.metadata_json or {},
            "error_code": version.error_code,
            "error_message": version.error_message,
        }
