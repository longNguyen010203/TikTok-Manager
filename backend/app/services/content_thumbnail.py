"""Safe, idempotent thumbnail generation for ready visual content."""

from __future__ import annotations

import io
import os
import selectors
import signal
import stat
import subprocess
import time
import warnings
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ContentAssetVersion, ContentEvent, ContentVariant
from app.models.timestamps import utc_now
from app.services.content_jobs import THUMBNAIL_PROFILE_FINGERPRINT
from app.services.content_operation_lock import (
    ContentOperationLockBusy,
    ContentOperationLockError,
    ContentVersionOperationGuard,
)
from app.services.content_storage import ContentStorageError, ContentStorageService
from app.services.content_validation import DetectedContent


class ContentThumbnailError(RuntimeError):
    def __init__(self, code: str, safe_message: str, *, retryable: bool) -> None:
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable
        super().__init__(safe_message)


class ContentThumbnailService:
    MAX_DIMENSION = 480
    JPEG_QUALITY = 82
    MAX_OUTPUT_BYTES = 16 * 1024 * 1024

    def __init__(
        self, session: Session, *, storage: ContentStorageService,
        guard: ContentVersionOperationGuard, ffmpeg_path: Path,
        timeout_seconds: float = 30,
        cancellation_hook: Callable[[], bool] | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.guard = guard
        self.ffmpeg_path = Path(ffmpeg_path)
        self.timeout_seconds = timeout_seconds
        self.cancellation_hook = cancellation_hook

    def generate(self, asset_id: int, version_id: int, variant_id: int) -> dict[str, Any]:
        try:
            with self.guard.acquire(version_id, blocking=False):
                version = self.session.scalar(
                    select(ContentAssetVersion)
                    .where(
                        ContentAssetVersion.id == version_id,
                        ContentAssetVersion.content_asset_id == asset_id,
                    )
                    .options(
                        selectinload(ContentAssetVersion.asset),
                        selectinload(ContentAssetVersion.blob),
                    )
                )
                variant = self.session.get(ContentVariant, variant_id)
                if (
                    version is None or variant is None
                    or variant.source_version_id != version_id
                    or variant.variant_kind != "thumbnail"
                    or variant.profile_fingerprint != THUMBNAIL_PROFILE_FINGERPRINT
                ):
                    raise ContentThumbnailError(
                        "CONTENT_THUMBNAIL_NOT_FOUND", "Thumbnail request was not found",
                        retryable=False,
                    )
                if variant.status == "ready":
                    return self.result(version, variant)
                if version.processing_status != "ready" or version.asset.asset_type not in {"image", "video"}:
                    raise ContentThumbnailError(
                        "CONTENT_VERSION_NOT_READY", "Content version is not ready for a thumbnail",
                        retryable=False,
                    )
                self._cancel()
                try:
                    source = self.storage.verify_blob(version.blob)
                except ContentStorageError as error:
                    raise ContentThumbnailError(
                        error.code, error.safe_message, retryable=True
                    ) from error
                if version.asset.asset_type == "image":
                    payload, width, height = self._image_thumbnail(source)
                else:
                    payload = self._video_thumbnail(source)
                    width, height = self._jpeg_dimensions(payload)
                self._cancel()
                staged = self.storage.stage_stream(io.BytesIO(payload))
                installed_key: str | None = None
                try:
                    with self.storage.maintenance_lock():
                        materialized = self.storage.materialize_blob(
                            self.session,
                            staged,
                            DetectedContent(
                                "image", "image/jpeg", ".jpg", frozenset({".jpg", ".jpeg"})
                            ),
                        )
                        installed_key = materialized.installed_storage_key
                        variant.blob_id = materialized.blob.id
                        variant.detected_mime_type = "image/jpeg"
                        variant.canonical_extension = ".jpg"
                        variant.status = "ready"
                        variant.metadata_json = {
                            "width": width, "height": height,
                            "max_dimension": self.MAX_DIMENSION,
                            "quality": self.JPEG_QUALITY,
                        }
                        variant.error_code = variant.error_message = None
                        variant.processed_at = utc_now()
                        self._event_once(version, variant, "thumbnail_ready")
                        self.session.commit()
                except Exception:
                    self.session.rollback()
                    if installed_key is not None:
                        self.storage.remove_installed(installed_key)
                    else:
                        self.storage.discard_staged(staged)
                    raise
                return self.result(version, variant)
        except ContentThumbnailError:
            raise
        except ContentOperationLockBusy as error:
            raise ContentThumbnailError(
                "CONTENT_THUMBNAIL_BUSY", "Thumbnail generation is already running",
                retryable=True,
            ) from error
        except (ContentOperationLockError, ContentStorageError) as error:
            raise ContentThumbnailError(
                "CONTENT_THUMBNAIL_FAILED", "Thumbnail generation failed", retryable=True
            ) from error
        except Exception as error:
            raise ContentThumbnailError(
                "CONTENT_THUMBNAIL_FAILED", "Thumbnail generation failed", retryable=False
            ) from error

    def mark_invalid(self, variant_id: int, error: ContentThumbnailError) -> None:
        variant = self.session.get(ContentVariant, variant_id)
        if variant is None or variant.status == "ready" or error.retryable:
            return
        variant.status = "invalid"
        variant.error_code = error.code
        variant.error_message = error.safe_message[:500]
        variant.processed_at = utc_now()
        version = self.session.get(ContentAssetVersion, variant.source_version_id)
        if version is not None:
            self._event_once(version, variant, "thumbnail_failed", {"error_code": error.code})
        self.session.commit()

    def _image_thumbnail(self, path: Path) -> tuple[bytes, int, int]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as source:
                    source.seek(0)
                    image = ImageOps.exif_transpose(source).convert("RGB")
                    image.thumbnail(
                        (self.MAX_DIMENSION, self.MAX_DIMENSION), Image.Resampling.LANCZOS
                    )
                    output = io.BytesIO()
                    image.save(output, format="JPEG", quality=self.JPEG_QUALITY, optimize=True)
                    return output.getvalue(), image.width, image.height
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
            raise ContentThumbnailError(
                "CONTENT_THUMBNAIL_INVALID", "Image thumbnail could not be generated",
                retryable=False,
            ) from error

    def _video_thumbnail(self, source: Path) -> bytes:
        self._validate_ffmpeg()
        command = [
            str(self.ffmpeg_path), "-v", "error", "-nostdin",
            "-protocol_whitelist", "file", "-i", str(source),
            "-frames:v", "1", "-vf",
            f"thumbnail,scale={self.MAX_DIMENSION}:{self.MAX_DIMENSION}:force_original_aspect_ratio=decrease",
            "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "4", "pipe:1",
        ]
        return self._run_ffmpeg(command)

    def _run_ffmpeg(self, command: list[str]) -> bytes:
        process = subprocess.Popen(
            command, shell=False, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        )
        deadline = time.monotonic() + self.timeout_seconds
        selector = selectors.DefaultSelector()
        assert process.stdout is not None and process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        try:
            while selector.get_map():
                if self.cancellation_hook is not None and self.cancellation_hook():
                    self._terminate(process)
                    raise ContentThumbnailError(
                        "CONTENT_PROCESSING_CANCELLED", "Thumbnail generation was cancelled",
                        retryable=True,
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._terminate(process)
                    raise ContentThumbnailError(
                        "CONTENT_FFMPEG_TIMEOUT", "Thumbnail generation timed out", retryable=True
                    )
                for key, _ in selector.select(timeout=min(0.1, remaining)):
                    chunk = os.read(key.fileobj.fileno(), 65_536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    buffers[key.data].extend(chunk)
                    limit = self.MAX_OUTPUT_BYTES if key.data == "stdout" else 1024 * 1024
                    if len(buffers[key.data]) > limit:
                        self._terminate(process)
                        raise ContentThumbnailError(
                            "CONTENT_THUMBNAIL_INVALID", "Thumbnail output exceeded safe limits",
                            retryable=False,
                        )
            process.wait(timeout=max(0.1, deadline - time.monotonic()))
            if process.returncode != 0 or not buffers["stdout"]:
                raise ContentThumbnailError(
                    "CONTENT_THUMBNAIL_INVALID", "Video thumbnail could not be generated",
                    retryable=False,
                )
            return bytes(buffers["stdout"])
        finally:
            selector.close()
            if process.poll() is None:
                self._terminate(process)

    def _validate_ffmpeg(self) -> None:
        if not self.ffmpeg_path.is_absolute():
            self._ffmpeg_unavailable()
        try:
            info = self.ffmpeg_path.lstat()
        except OSError:
            self._ffmpeg_unavailable()
        if (
            stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
            or info.st_uid not in {0, os.getuid()} or info.st_mode & 0o022
            or not info.st_mode & 0o111
        ):
            self._ffmpeg_unavailable()

    @staticmethod
    def _ffmpeg_unavailable() -> None:
        raise ContentThumbnailError(
            "CONTENT_FFMPEG_UNAVAILABLE", "Thumbnail tool is unavailable", retryable=True
        )

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
        except ProcessLookupError:
            pass

    @staticmethod
    def _jpeg_dimensions(payload: bytes) -> tuple[int, int]:
        try:
            with Image.open(io.BytesIO(payload)) as image:
                image.verify()
            with Image.open(io.BytesIO(payload)) as image:
                if image.format != "JPEG" or image.width <= 0 or image.height <= 0:
                    raise ValueError
                return image.width, image.height
        except (OSError, ValueError, UnidentifiedImageError) as error:
            raise ContentThumbnailError(
                "CONTENT_THUMBNAIL_INVALID", "Thumbnail output is invalid", retryable=False
            ) from error

    def _cancel(self) -> None:
        if self.cancellation_hook is not None and self.cancellation_hook():
            raise ContentThumbnailError(
                "CONTENT_PROCESSING_CANCELLED", "Thumbnail generation was cancelled",
                retryable=True,
            )

    def _event_once(
        self, version: ContentAssetVersion, variant: ContentVariant,
        event_type: str, metadata: dict[str, Any] | None = None,
    ) -> None:
        exists = self.session.scalar(select(ContentEvent.id).where(
            ContentEvent.content_asset_version_id == version.id,
            ContentEvent.event_type == event_type,
            ContentEvent.metadata_json["variant_id"].as_integer() == variant.id,
        ))
        if exists is None:
            values = {"variant_id": variant.id}
            values.update(metadata or {})
            self.session.add(ContentEvent(
                content_asset_id=version.content_asset_id,
                content_asset_version_id=version.id,
                event_type=event_type,
                metadata_json=values,
            ))

    @staticmethod
    def result(version: ContentAssetVersion, variant: ContentVariant) -> dict[str, Any]:
        metadata = variant.metadata_json or {}
        return {
            "content_asset_id": version.content_asset_id,
            "content_asset_version_id": version.id,
            "content_variant_id": variant.id,
            "status": variant.status,
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "mime_type": variant.detected_mime_type,
        }
