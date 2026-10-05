"""Thumbnail variants, idempotency, quota accounting, and cleanup."""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.database import init_db
from app.models import ContentAssetVersion, ContentBlob, ContentVariant
from app.services.content_assets import ContentAssetService
from app.services.content_jobs import enqueue_content_thumbnail
from app.services.content_operation_lock import ContentVersionOperationGuard
from app.services.content_storage import ContentMaintenanceBusy, ContentStorageService
from app.services.content_thumbnail import ContentThumbnailService
from app.services.content_validation import DetectedContent


def image_bytes(fmt: str = "PNG", size: tuple[int, int] = (1200, 600)) -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", size, (12, 34, 56)).save(stream, format=fmt)
    return stream.getvalue()


def setup(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    init_db(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    storage = ContentStorageService(
        tmp_path / "content", max_upload_bytes=10_000_000, max_total_bytes=50_000_000
    )
    return engine, sessions, storage


def ready_image(session, storage: ContentStorageService):
    asset = ContentAssetService(storage).create_upload(
        session, stream=io.BytesIO(image_bytes()), original_filename="wide.png",
        declared_mime_type="image/png", display_name="Wide", notes=None, tags=[],
    )
    version = asset.versions[0]
    version.processing_status = "ready"
    asset.status = "ready"
    asset.current_version_id = version.id
    enqueue_content_thumbnail(session, version)
    session.commit()
    return asset, version, session.scalar(select(ContentVariant))


def test_image_thumbnail_is_bounded_deduplicated_and_idempotent(tmp_path: Path) -> None:
    engine, sessions, storage = setup(tmp_path)
    try:
        with sessions() as session:
            asset, version, variant = ready_image(session, storage)
            service = ContentThumbnailService(
                session, storage=storage,
                guard=ContentVersionOperationGuard(tmp_path / "locks"),
                ffmpeg_path=Path("/usr/bin/ffmpeg"),
            )
            result = service.generate(asset.id, version.id, variant.id)
            assert result["status"] == "ready"
            assert (result["width"], result["height"]) == (480, 240)
            assert session.scalar(select(func.count()).select_from(ContentBlob)) == 2
            assert service.generate(asset.id, version.id, variant.id) == result
            assert session.scalar(select(func.count()).select_from(ContentBlob)) == 2
            path = storage.verify_blob(session.get(ContentVariant, variant.id).blob)
            with Image.open(path) as image:
                assert image.format == "JPEG" and image.size == (480, 240)
    finally:
        engine.dispose()


def test_video_thumbnail_command_is_local_bounded_and_shell_free(tmp_path: Path) -> None:
    _engine, sessions, storage = setup(tmp_path)
    with sessions() as session:
        service = ContentThumbnailService(
            session, storage=storage,
            guard=ContentVersionOperationGuard(tmp_path / "locks"),
            ffmpeg_path=Path("/usr/bin/ffmpeg"),
        )
        captured: list[str] = []

        def fake(command: list[str]) -> bytes:
            captured.extend(command)
            return image_bytes("JPEG", (480, 270))

        service._validate_ffmpeg = lambda: None  # type: ignore[method-assign]
        service._run_ffmpeg = fake  # type: ignore[method-assign]
        result = service._video_thumbnail(Path("/managed/blob"))
        assert result.startswith(b"\xff\xd8")
        assert captured[0] == "/usr/bin/ffmpeg"
        assert captured[captured.index("-protocol_whitelist") + 1] == "file"
        assert "pipe:1" in captured and "/managed/blob" in captured


def test_cleanup_reclaims_only_grace_aged_unreferenced_blob(tmp_path: Path) -> None:
    engine, sessions, storage = setup(tmp_path)
    try:
        with sessions() as session:
            staged = storage.stage_stream(io.BytesIO(image_bytes()))
            with storage.maintenance_lock():
                item = storage.materialize_blob(
                    session, staged,
                    DetectedContent("image", "image/png", ".png", frozenset({".png"})),
                )
                session.commit()
            now = datetime.now(timezone.utc)
            first = storage.reconcile(session, now=now)
            assert first.orphaned_rows == 1
            result = storage.cleanup(
                session, now=now + timedelta(days=8), orphan_grace=timedelta(days=7)
            )
            assert result.deleted_orphan_blobs == 1
            assert result.bytes_reclaimed == item.blob.size_bytes
            assert item.blob.status == "deleted"
            assert not (storage.blobs / item.blob.storage_key).exists()
    finally:
        engine.dispose()


def test_deleted_ready_asset_does_not_schedule_new_thumbnail(tmp_path: Path) -> None:
    engine, sessions, storage = setup(tmp_path)
    try:
        with sessions() as session:
            asset, version, _variant = ready_image(session, storage)
            version.thumbnail_job_id = None
            for variant in list(version.variants):
                session.delete(variant)
            asset.status = "deleted"
            session.flush()
            assert enqueue_content_thumbnail(session, version) is None
    finally:
        engine.dispose()


def test_content_cleanup_rejects_concurrent_maintenance(tmp_path: Path) -> None:
    engine, sessions, storage = setup(tmp_path)
    try:
        with sessions() as session, storage.maintenance_lock():
            with pytest.raises(ContentMaintenanceBusy):
                storage.cleanup(session, wait=False)
    finally:
        engine.dispose()
