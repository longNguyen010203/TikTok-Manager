"""Artifact retention, quota, and safe cleanup tests."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import init_db
from app.models import Job
from app.models.timestamps import utc_now
from app.services.automation_artifacts import (
    ArtifactCleanupBusy,
    AutomationArtifactStore,
)
from app.services.automation_errors import AutomationError


def make_store(tmp_path: Path, *, quota: int = 100) -> AutomationArtifactStore:
    return AutomationArtifactStore(
        tmp_path / "artifacts",
        max_size_bytes=min(quota, 50),
        max_total_bytes=quota,
        retention_days=30,
        upload_retention_days=7,
    )


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'artifacts.db'}")
    init_db(engine)
    with Session(engine, expire_on_commit=False) as value:
        yield value
    engine.dispose()


def store_bytes(
    store: AutomationArtifactStore,
    session: Session,
    data: bytes,
    *,
    job_id: int | None = None,
):
    return store.store_bytes(
        session,
        data=data,
        kind="upload",
        original_filename="fixture.bin",
        mime_type="application/octet-stream",
        job_id=job_id,
    )


def test_retention_expires_bytes_but_preserves_metadata(
    session: Session, tmp_path: Path
) -> None:
    store = make_store(tmp_path)
    artifact = store_bytes(store, session, b"expired")
    artifact.expires_at = utc_now() - timedelta(seconds=1)
    session.commit()

    result = store.cleanup(session)

    session.refresh(artifact)
    assert result.expired == 1
    assert result.bytes_released == len(b"expired")
    assert artifact.cleanup_status == "expired"
    assert not (store.root / artifact.storage_key).exists()
    assert session.get(type(artifact), artifact.id) is artifact


def test_active_job_artifact_is_protected_even_when_expired(
    session: Session, tmp_path: Path
) -> None:
    store = make_store(tmp_path)
    job = Job(job_type="device.push_file", status="running", payload={})
    session.add(job)
    session.commit()
    artifact = store_bytes(store, session, b"protected", job_id=job.id)
    artifact.expires_at = utc_now() - timedelta(days=1)
    session.commit()

    result = store.cleanup(session)

    session.refresh(artifact)
    assert result.expired == 0
    assert artifact.cleanup_status == "active"
    assert store.path_for(artifact).is_file()


def test_quota_evicts_old_eligible_artifact(session: Session, tmp_path: Path) -> None:
    store = make_store(tmp_path, quota=10)
    first = store_bytes(store, session, b"123456")

    second = store.store_bytes(
        session,
        data=b"abcdef",
        kind="screenshot",
        original_filename="screen.png",
        mime_type="image/png",
    )

    session.refresh(first)
    assert first.cleanup_status == "expired"
    assert second.cleanup_status == "active"


def test_quota_rejects_when_only_active_job_artifacts_can_be_reclaimed(
    session: Session, tmp_path: Path
) -> None:
    store = make_store(tmp_path, quota=10)
    job = Job(job_type="device.push_file", status="pending", payload={})
    session.add(job)
    session.commit()
    store_bytes(store, session, b"123456", job_id=job.id)

    with pytest.raises(AutomationError) as raised:
        store.store_bytes(
            session,
            data=b"abcdef",
            kind="screenshot",
            original_filename="screen.png",
            mime_type="image/png",
        )

    assert raised.value.code == "ARTIFACT_STORAGE_FULL"


def test_missing_file_is_marked_expired_without_failing_cleanup(
    session: Session, tmp_path: Path
) -> None:
    store = make_store(tmp_path)
    artifact = store_bytes(store, session, b"missing")
    artifact.expires_at = utc_now() - timedelta(seconds=1)
    session.commit()
    store.path_for(artifact).unlink()

    result = store.cleanup(session)

    session.refresh(artifact)
    assert result.missing == 1
    assert artifact.cleanup_status == "expired"


def test_cleanup_rejects_symlink_and_leaves_target_untouched(
    session: Session, tmp_path: Path
) -> None:
    store = make_store(tmp_path)
    artifact = store_bytes(store, session, b"unsafe")
    artifact.expires_at = utc_now() - timedelta(seconds=1)
    session.commit()
    path = store.path_for(artifact)
    path.unlink()
    target = tmp_path / "outside"
    target.write_bytes(b"outside")
    path.symlink_to(target)

    result = store.cleanup(session)

    session.refresh(artifact)
    assert result.failed == 1
    assert artifact.cleanup_status == "failed"
    assert path.is_symlink()
    assert target.read_bytes() == b"outside"


def test_cleanup_lock_rejects_concurrent_maintenance(
    session: Session, tmp_path: Path
) -> None:
    store = make_store(tmp_path)
    with store.maintenance_lock():
        with pytest.raises(ArtifactCleanupBusy):
            store.cleanup(session, wait=False)


def test_default_lifetimes_distinguish_uploads_and_results(
    session: Session, tmp_path: Path
) -> None:
    store = make_store(tmp_path)
    before = utc_now().replace(tzinfo=None)
    upload = store_bytes(store, session, b"upload")
    screenshot = store.store_bytes(
        session,
        data=b"result",
        kind="screenshot",
        original_filename="screen.png",
        mime_type="image/png",
    )

    assert upload.expires_at >= before + timedelta(days=6)
    assert screenshot.expires_at >= before + timedelta(days=29)
