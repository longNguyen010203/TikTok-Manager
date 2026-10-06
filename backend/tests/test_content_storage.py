"""Content storage, admission, quota, deduplication, and recovery tests."""

from __future__ import annotations

import io
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import init_db
from app.models import ContentAsset, ContentBlob
from app.services.content_assets import ContentAssetService
from app.services.content_storage import ContentStorageError, ContentStorageService
from app.services.content_validation import (
    ContentValidationError,
    detect_content_signature,
    normalize_content_filename,
    validate_content_hints,
)


PNG = b"\x89PNG\r\n\x1a\n" + b"phase-two-png"
JPEG = b"\xff\xd8\xff\xe0" + b"phase-two-jpeg"
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"webp"
MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isommp42"
MOV = b"\x00\x00\x00\x18ftypqt  \x00\x00\x00\x00qt  "
WEBM = b"\x1aE\xdf\xa3webm"
MP3 = b"ID3\x04\x00\x00\x00\x00\x00\x00"
M4A = b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00M4A "
AAC = b"\xff\xf1\x50\x80\x00\x1f\xfc"
WAV = b"RIFF\x24\x00\x00\x00WAVEfmt "
OGG = b"OggS\x00\x02" + b"\x00" * 20 + b"OpusHead"


def make_database(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'content.db'}",
        connect_args={"check_same_thread": False},
    )
    init_db(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def service(tmp_path: Path, *, maximum: int = 1024, total: int = 4096):
    storage = ContentStorageService(
        tmp_path / "content", max_upload_bytes=maximum, max_total_bytes=total
    )
    return ContentAssetService(storage), storage


@pytest.mark.parametrize(
    ("data", "filename", "mime", "asset_type", "detected_mime", "extension"),
    [
        (PNG, "photo.png", "image/png", "image", "image/png", ".png"),
        (JPEG, "photo.jpeg", "image/jpeg", "image", "image/jpeg", ".jpg"),
        (WEBP, "photo.webp", "image/webp", "image", "image/webp", ".webp"),
        (MP4, "clip.mp4", "video/mp4", "video", "video/mp4", ".mp4"),
        (MOV, "clip.mov", "video/quicktime", "video", "video/quicktime", ".mov"),
        (WEBM, "clip.webm", "video/webm", "video", "video/webm", ".webm"),
        (MP3, "sound.mp3", "audio/mpeg", "audio", "audio/mpeg", ".mp3"),
        (M4A, "sound.m4a", "audio/mp4", "audio", "audio/mp4", ".m4a"),
        (AAC, "sound.aac", "audio/aac", "audio", "audio/aac", ".aac"),
        (WAV, "sound.wav", "audio/wav", "audio", "audio/wav", ".wav"),
        (OGG, "sound.ogg", "audio/ogg", "audio", "audio/ogg", ".ogg"),
    ],
)
def test_signature_admission_allowlist(
    data, filename, mime, asset_type, detected_mime, extension
) -> None:
    detected = detect_content_signature(data)
    assert validate_content_hints(filename, mime, detected) == filename
    assert (detected.asset_type, detected.mime_type, detected.canonical_extension) == (
        asset_type,
        detected_mime,
        extension,
    )


@pytest.mark.parametrize("data", [b"MZ executable", b"PK\x03\x04 archive", b"not-media"])
def test_signature_admission_rejects_unsupported_content(data: bytes) -> None:
    with pytest.raises(ContentValidationError, match="unsupported"):
        detect_content_signature(data)


def test_admission_rejects_mismatched_hints_and_paths() -> None:
    detected = detect_content_signature(PNG)
    with pytest.raises(ContentValidationError, match="extension"):
        validate_content_hints("photo.jpg", "image/png", detected)
    with pytest.raises(ContentValidationError, match="Declared"):
        validate_content_hints("photo.png", "image/jpeg", detected)
    with pytest.raises(ContentValidationError, match="filename"):
        normalize_content_filename("../../photo.png")


def test_storage_permissions_atomic_install_and_duplicate_reuse(tmp_path: Path) -> None:
    engine, sessions = make_database(tmp_path)
    assets, storage = service(tmp_path)
    try:
        with sessions() as session:
            first = assets.create_upload(
                session,
                stream=io.BytesIO(PNG),
                original_filename="first.png",
                declared_mime_type="image/png",
                display_name="First",
                notes=None,
                tags=[" Demo ", "demo"],
            )
            second = assets.create_upload(
                session,
                stream=io.BytesIO(PNG),
                original_filename="second.png",
                declared_mime_type="image/png",
                display_name="Second",
                notes="independent metadata",
                tags=["second"],
            )
            assert first.id != second.id
            assert session.scalar(select(func.count()).select_from(ContentAsset)) == 2
            assert session.scalar(select(func.count()).select_from(ContentBlob)) == 1
            blob = session.scalar(select(ContentBlob))
            assert stat.S_IMODE(storage.root.stat().st_mode) == 0o700
            assert stat.S_IMODE(storage.blobs.stat().st_mode) == 0o700
            assert stat.S_IMODE(storage.staging.stat().st_mode) == 0o700
            assert stat.S_IMODE(storage.path_for(blob).stat().st_mode) == 0o600
            original = storage.path_for(blob)
            with storage.temporary_apk_view(blob) as apk_view:
                assert apk_view.name.endswith(".apk")
                assert apk_view.parent == storage.staging
                assert apk_view.is_file()
                assert apk_view.stat().st_ino == original.stat().st_ino
                assert stat.S_IMODE(apk_view.stat().st_mode) == 0o600
            assert not apk_view.exists()
            assert list(storage.staging.iterdir()) == []
    finally:
        engine.dispose()


def test_concurrent_duplicate_uploads_share_one_blob(tmp_path: Path) -> None:
    engine, sessions = make_database(tmp_path)
    assets, _storage = service(tmp_path)

    def upload(index: int) -> int:
        with sessions() as session:
            return assets.create_upload(
                session,
                stream=io.BytesIO(PNG),
                original_filename=f"duplicate-{index}.png",
                declared_mime_type="image/png",
                display_name=f"Duplicate {index}",
                notes=None,
                tags=[],
            ).id

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            ids = list(executor.map(upload, (1, 2)))
        assert len(set(ids)) == 2
        with sessions() as session:
            assert session.scalar(select(func.count()).select_from(ContentBlob)) == 1
            assert session.scalar(select(func.count()).select_from(ContentAsset)) == 2
    finally:
        engine.dispose()


def test_storage_rejects_empty_oversized_and_full_uploads(tmp_path: Path) -> None:
    engine, sessions = make_database(tmp_path)
    assets, _storage = service(tmp_path, maximum=len(PNG), total=len(PNG))
    try:
        with sessions() as session:
            with pytest.raises(ContentStorageError) as empty:
                assets.create_upload(
                    session, stream=io.BytesIO(b""), original_filename="empty.png",
                    declared_mime_type="image/png", display_name="Empty", notes=None, tags=[],
                )
            assert empty.value.code == "EMPTY_CONTENT"
            with pytest.raises(ContentStorageError) as oversized:
                assets.create_upload(
                    session, stream=io.BytesIO(PNG + b"x"), original_filename="large.png",
                    declared_mime_type="image/png", display_name="Large", notes=None, tags=[],
                )
            assert oversized.value.code == "CONTENT_UPLOAD_TOO_LARGE"
            assets.create_upload(
                session, stream=io.BytesIO(PNG), original_filename="first.png",
                declared_mime_type="image/png", display_name="First", notes=None, tags=[],
            )
            with pytest.raises(ContentStorageError) as full:
                assets.create_upload(
                    session, stream=io.BytesIO(JPEG), original_filename="second.jpg",
                    declared_mime_type="image/jpeg", display_name="Second", notes=None, tags=[],
                )
            assert full.value.code == "CONTENT_STORAGE_FULL"
    finally:
        engine.dispose()


def test_storage_rejects_symlink_root(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    storage = ContentStorageService(linked, max_upload_bytes=100, max_total_bytes=100)
    with pytest.raises(ContentStorageError, match="symlink"):
        storage.prepare()


def test_storage_rejects_symlink_blob(tmp_path: Path) -> None:
    engine, sessions = make_database(tmp_path)
    assets, storage = service(tmp_path)
    try:
        with sessions() as session:
            asset = assets.create_upload(
                session, stream=io.BytesIO(PNG), original_filename="photo.png",
                declared_mime_type="image/png", display_name="Photo", notes=None, tags=[],
            )
            blob = asset.versions[0].blob
            path = storage.path_for(blob)
            path.unlink()
            path.symlink_to(tmp_path / "outside")
            with pytest.raises(ContentStorageError, match="unavailable|unsafe"):
                storage.path_for(blob)
    finally:
        engine.dispose()


def test_reconcile_removes_only_proven_stale_staging_and_marks_missing(
    tmp_path: Path,
) -> None:
    engine, sessions = make_database(tmp_path)
    assets, storage = service(tmp_path)
    try:
        with sessions() as session:
            asset = assets.create_upload(
                session, stream=io.BytesIO(PNG), original_filename="photo.png",
                declared_mime_type="image/png", display_name="Photo", notes=None, tags=[],
            )
            blob = asset.versions[0].blob
            storage.path_for(blob).unlink()
            staged = storage.stage_stream(io.BytesIO(JPEG))
            staged_path = storage.staging / staged.name
            old = (datetime.now(timezone.utc) - timedelta(days=2)).timestamp()
            os.utime(staged_path, (old, old))
            uncertain = storage.staging / "operator-file"
            uncertain.write_bytes(b"leave-me")
            uncertain.chmod(0o600)

            result = storage.reconcile(session)

            assert result.removed_staging_files == 1
            assert result.missing_blobs == 1
            assert result.uncertain_files == ("staging:operator-file",)
            assert session.get(ContentBlob, blob.id).status == "missing"
            assert not staged_path.exists()
            assert uncertain.exists()
    finally:
        engine.dispose()
