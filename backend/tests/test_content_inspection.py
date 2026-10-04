"""Authoritative content inspection, metadata, state, and recovery tests."""

from __future__ import annotations

import io
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import init_db
from app.models import ContentAssetVersion, ContentEvent, Job
from app.services.content_assets import ContentAssetService
from app.services.content_inspection import ContentInspectionService, ContentProcessingError
from app.services.content_jobs import reconcile_content_inspections
from app.services.content_operation_lock import (
    ContentOperationLockError,
    ContentVersionOperationGuard,
)
from app.services.content_storage import ContentStorageService
from app.services.media_probe import FfprobeInspector, MediaProbeError


def image_bytes(format_name: str, size=(7, 5), *, orientation: int | None = None) -> bytes:
    output = io.BytesIO()
    image = Image.new("RGB", size, (10, 20, 30))
    kwargs = {}
    if orientation is not None:
        exif = Image.Exif()
        exif[274] = orientation
        kwargs["exif"] = exif
    image.save(output, format=format_name, **kwargs)
    return output.getvalue()


@pytest.fixture
def content_environment(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'content.db'}")
    init_db(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    storage = ContentStorageService(
        tmp_path / "content", max_upload_bytes=1024 * 1024, max_total_bytes=8 * 1024 * 1024
    )
    yield sessions, storage, tmp_path
    engine.dispose()


def inspection(session, storage, tmp_path, **limits):
    executable = tmp_path / "ffprobe"
    executable.write_bytes(b"#!/bin/sh\nexit 1\n")
    executable.chmod(0o700)
    return ContentInspectionService(
        session,
        storage=storage,
        guard=ContentVersionOperationGuard(tmp_path / "locks"),
        ffprobe=FfprobeInspector(executable),
        max_image_dimension=limits.get("dimension", 4096),
        max_image_pixels=limits.get("pixels", 10_000_000),
        max_image_frames=limits.get("frames", 20),
        cancellation_hook=limits.get("cancellation_hook"),
    )


@pytest.mark.parametrize(
    ("format_name", "filename", "mime"),
    [("PNG", "image.png", "image/png"), ("JPEG", "image.jpg", "image/jpeg"), ("WEBP", "image.webp", "image/webp")],
)
def test_image_inspection_ready_metadata_and_idempotency(
    content_environment, format_name, filename, mime
) -> None:
    sessions, storage, tmp_path = content_environment
    with sessions() as session:
        asset = ContentAssetService(storage).create_upload(
            session,
            stream=io.BytesIO(image_bytes(format_name, orientation=6 if format_name == "JPEG" else None)),
            original_filename=filename,
            declared_mime_type=mime,
            display_name="Decoded image",
            notes=None,
            tags=[],
        )
        version = asset.versions[0]
        assert session.get(Job, version.inspection_job_id).job_type == "content.inspect"
        service = inspection(session, storage, tmp_path)
        result = service.inspect(asset.id, version.id)
        assert result["processing_status"] == "ready"
        assert (result["width"], result["height"]) == (7, 5)
        assert result["metadata"]["format"] == format_name
        if format_name == "JPEG":
            assert session.get(ContentAssetVersion, version.id).orientation == 6
        assert asset.current_version_id == version.id
        assert asset.status == "ready"
        service.inspect(asset.id, version.id)
        assert session.scalar(select(func.count()).select_from(ContentEvent).where(
            ContentEvent.content_asset_version_id == version.id,
            ContentEvent.event_type == "ready",
        )) == 1


def test_corrupt_and_pixel_limited_images_become_invalid(content_environment) -> None:
    sessions, storage, tmp_path = content_environment
    with sessions() as session:
        corrupt = ContentAssetService(storage).create_upload(
            session, stream=io.BytesIO(b"\x89PNG\r\n\x1a\ncorrupt"),
            original_filename="bad.png", declared_mime_type="image/png",
            display_name="Bad", notes=None, tags=[],
        )
        with pytest.raises(ContentProcessingError) as invalid:
            inspection(session, storage, tmp_path).inspect(corrupt.id, corrupt.versions[0].id)
        assert invalid.value.code == "CONTENT_IMAGE_INVALID"
        session.refresh(corrupt)
        assert corrupt.status == "invalid" and corrupt.current_version_id is None

        large = ContentAssetService(storage).create_upload(
            session, stream=io.BytesIO(image_bytes("PNG", (20, 20))),
            original_filename="large.png", declared_mime_type="image/png",
            display_name="Large", notes=None, tags=[],
        )
        with pytest.raises(ContentProcessingError) as too_large:
            inspection(session, storage, tmp_path, pixels=100).inspect(large.id, large.versions[0].id)
        assert too_large.value.code == "CONTENT_IMAGE_TOO_LARGE"


def test_animated_webp_frame_metadata(content_environment) -> None:
    sessions, storage, tmp_path = content_environment
    output = io.BytesIO()
    frames = [Image.new("RGB", (4, 3), color) for color in ((255, 0, 0), (0, 0, 255))]
    frames[0].save(
        output, format="WEBP", save_all=True, append_images=frames[1:], duration=50, loop=0
    )
    with sessions() as session:
        asset = ContentAssetService(storage).create_upload(
            session, stream=io.BytesIO(output.getvalue()), original_filename="animated.webp",
            declared_mime_type="image/webp", display_name="Animated", notes=None, tags=[],
        )
        result = inspection(session, storage, tmp_path).inspect(
            asset.id, asset.versions[0].id
        )
        assert result["metadata"]["animated"] is True
        assert result["metadata"]["frame_count"] == 2


def test_failed_replacement_preserves_ready_current_version(content_environment) -> None:
    sessions, storage, tmp_path = content_environment
    with sessions() as session:
        assets = ContentAssetService(storage)
        asset = assets.create_upload(
            session, stream=io.BytesIO(image_bytes("PNG")), original_filename="first.png",
            declared_mime_type="image/png", display_name="Versioned", notes=None, tags=[],
        )
        first = asset.versions[0]
        inspection(session, storage, tmp_path).inspect(asset.id, first.id)
        asset = assets.get(session, asset.id)
        asset = assets.create_replacement(
            session, asset=asset, stream=io.BytesIO(b"\x89PNG\r\n\x1a\nbroken"),
            original_filename="replacement.png", declared_mime_type="image/png",
        )
        second = asset.versions[-1]
        with pytest.raises(ContentProcessingError):
            inspection(session, storage, tmp_path).inspect(asset.id, second.id)
        asset = assets.get(session, asset.id)
        assert asset.current_version_id == first.id
        assert asset.status == "ready"
        assert second.processing_status == "invalid"


def test_cancellation_leaves_processing_recoverable(content_environment) -> None:
    sessions, storage, tmp_path = content_environment
    with sessions() as session:
        asset = ContentAssetService(storage).create_upload(
            session, stream=io.BytesIO(image_bytes("PNG")), original_filename="cancel.png",
            declared_mime_type="image/png", display_name="Cancel", notes=None, tags=[],
        )
        with pytest.raises(ContentProcessingError) as cancelled:
            inspection(
                session, storage, tmp_path, cancellation_hook=lambda: True
            ).inspect(asset.id, asset.versions[0].id)
        assert cancelled.value.code == "CONTENT_PROCESSING_CANCELLED"
        assert asset.versions[0].processing_status == "processing"


def test_duplicate_inspection_is_prevented_by_version_lock(content_environment) -> None:
    sessions, storage, tmp_path = content_environment
    guard = ContentVersionOperationGuard(tmp_path / "locks")
    with sessions() as session:
        asset = ContentAssetService(storage).create_upload(
            session, stream=io.BytesIO(image_bytes("PNG")), original_filename="busy.png",
            declared_mime_type="image/png", display_name="Busy", notes=None, tags=[],
        )
        service = ContentInspectionService(
            session, storage=storage, guard=guard,
            ffprobe=FfprobeInspector(tmp_path / "missing"),
            max_image_dimension=4096, max_image_pixels=10_000_000,
            max_image_frames=20,
        )
        with guard.acquire(asset.versions[0].id):
            with pytest.raises(ContentProcessingError) as busy:
                service.inspect(asset.id, asset.versions[0].id)
        assert busy.value.code == "CONTENT_PROCESSING_BUSY"
        assert asset.versions[0].processing_status == "processing"


def test_content_version_guard_rejects_symlink_directory(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    with pytest.raises(ContentOperationLockError, match="unsafe"):
        with ContentVersionOperationGuard(linked).acquire(1):
            pass


def test_processing_reconciliation_replaces_missing_or_retryable_terminal_job(
    content_environment,
) -> None:
    sessions, storage, tmp_path = content_environment
    with sessions() as session:
        asset = ContentAssetService(storage).create_upload(
            session, stream=io.BytesIO(image_bytes("PNG")), original_filename="recover.png",
            declared_mime_type="image/png", display_name="Recover", notes=None, tags=[],
        )
        version = asset.versions[0]
        old = session.get(Job, version.inspection_job_id)
        old.status = "failed"
        old.error_retryable = True
        session.commit()
        assert reconcile_content_inspections(
            session, ContentVersionOperationGuard(tmp_path / "locks")
        ) == 1
        session.refresh(version)
        assert version.inspection_job_id != old.id
        assert session.get(Job, version.inspection_job_id).status == "pending"


def probe_payload(*, video=True):
    streams = []
    if video:
        streams.append({
            "index": 0, "codec_type": "video", "codec_name": "h264",
            "width": 1920, "height": 1080, "avg_frame_rate": "30000/1001",
            "r_frame_rate": "30000/1001", "tags": {"rotate": "90"},
        })
    streams.append({
        "index": len(streams), "codec_type": "audio", "codec_name": "aac" if video else "mp3",
        "sample_rate": "48000", "channels": 2,
    })
    return {"streams": streams, "format": {
        "format_name": "mov,mp4,m4a,3gp,3g2,mj2" if video else "mp3",
        "duration": "2.500", "bit_rate": "1000000",
    }}


def test_ffprobe_normalizes_video_and_audio_without_raw_output(tmp_path: Path) -> None:
    executable = tmp_path / "ffprobe"
    executable.write_bytes(b"safe")
    executable.chmod(0o700)
    source = tmp_path / "media"
    source.write_bytes(b"media")

    def runner(command, **kwargs):
        assert kwargs["shell"] is False
        assert "-protocol_whitelist" in command and command[-1] == str(source)
        return subprocess.CompletedProcess(command, 0, json.dumps(probe_payload()).encode(), b"")

    result = FfprobeInspector(executable, runner=runner).probe(source, "video/mp4")
    assert (result.width, result.height, result.duration_ms) == (1920, 1080, 2500)
    assert (result.frame_rate_numerator, result.frame_rate_denominator) == (30000, 1001)
    assert result.metadata == {"audio_codec": "aac", "rotation": 90, "stream_count": 2}

    audio = FfprobeInspector(
        executable,
        runner=lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, json.dumps(probe_payload(video=False)).encode(), b""
        ),
    ).probe(source, "audio/mpeg")
    assert (audio.sample_rate, audio.channels, audio.codec) == (48000, 2, "mp3")


@pytest.mark.parametrize(
    ("runner", "code", "retryable"),
    [
        (lambda command, **kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired(command, 1)), "CONTENT_FFPROBE_TIMEOUT", True),
        (lambda command, **kwargs: subprocess.CompletedProcess(command, 0, b"not-json", b""), "CONTENT_METADATA_INVALID", False),
        (lambda command, **kwargs: subprocess.CompletedProcess(command, 0, json.dumps({"streams": [], "format": {}}).encode(), b""), "CONTENT_METADATA_INVALID", False),
    ],
)
def test_ffprobe_failures_are_sanitized(tmp_path: Path, runner, code, retryable) -> None:
    executable = tmp_path / "ffprobe"
    executable.write_bytes(b"safe")
    executable.chmod(0o700)
    source = tmp_path / "media"
    source.write_bytes(b"media")
    with pytest.raises(MediaProbeError) as failure:
        FfprobeInspector(executable, runner=runner, timeout_seconds=1).probe(source, "video/mp4")
    assert failure.value.code == code and failure.value.retryable is retryable
    assert str(source) not in str(failure.value)


def test_ffprobe_missing_no_video_and_output_limit(tmp_path: Path) -> None:
    source = tmp_path / "media"
    source.write_bytes(b"media")
    with pytest.raises(MediaProbeError) as unavailable:
        FfprobeInspector(tmp_path / "missing").probe(source, "video/mp4")
    assert unavailable.value.code == "CONTENT_FFPROBE_UNAVAILABLE"
    assert unavailable.value.retryable is True

    executable = tmp_path / "ffprobe"
    executable.write_bytes(b"safe")
    executable.chmod(0o700)
    audio_only = probe_payload(video=False)
    audio_only["format"]["format_name"] = "mov,mp4,m4a,3gp,3g2,mj2"
    with pytest.raises(MediaProbeError) as no_video:
        FfprobeInspector(
            executable,
            runner=lambda command, **kwargs: subprocess.CompletedProcess(
                command, 0, json.dumps(audio_only).encode(), b""
            ),
        ).probe(source, "video/mp4")
    assert no_video.value.code == "CONTENT_MEDIA_CORRUPT"

    with pytest.raises(MediaProbeError) as bounded:
        FfprobeInspector(
            executable,
            max_output_bytes=16,
            runner=lambda command, **kwargs: subprocess.CompletedProcess(
                command, 0, json.dumps(probe_payload()).encode(), b""
            ),
        ).probe(source, "video/mp4")
    assert bounded.value.code == "CONTENT_METADATA_INVALID"


def test_ffprobe_owned_child_is_cancelled_without_global_process_action(tmp_path: Path) -> None:
    executable = tmp_path / "ffprobe"
    executable.write_text("#!/bin/sh\nsleep 10\n", encoding="utf-8")
    executable.chmod(0o700)
    source = tmp_path / "media"
    source.write_bytes(b"media")
    started_at = time.monotonic()

    with pytest.raises(MediaProbeError) as cancelled:
        FfprobeInspector(
            executable,
            timeout_seconds=5,
            cancellation_hook=lambda: time.monotonic() - started_at > 0.15,
        ).probe(source, "video/mp4")

    assert cancelled.value.code == "CONTENT_PROCESSING_CANCELLED"
    assert time.monotonic() - started_at < 3
    assert os.path.exists(source)
