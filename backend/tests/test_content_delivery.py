"""Content delivery creation, execution, history, and isolation tests."""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, init_db
from app.models import (
    ContentAssetVersion, ContentDelivery, ContentEvent, Device, Job, JobArtifact, Runtime,
)
from app.services.android_automation import AndroidAutomationService
from app.services.content_inspection import ContentInspectionService
from app.services.content_operation_lock import ContentVersionOperationGuard
from app.services.content_storage import ContentStorageService
from app.services.media_probe import FfprobeInspector
from app.services.runtime_automation_cleanup import (
    RuntimeAutomationBusyError,
    RuntimeAutomationCleanupCoordinator,
)
from app.services.runtime_operation_lock import RuntimeOperationGuard
from tests.app_factory import create_test_app


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (6, 4), (1, 2, 3)).save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def delivery_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("TIKTOK_MANAGER_CONTENT_ROOT", str(tmp_path / "content"))
    monkeypatch.setenv("TIKTOK_MANAGER_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("TIKTOK_MANAGER_BRIDGE_LOCK_DIRECTORY", str(tmp_path / "locks"))
    database_url = URL.create("sqlite", database=str(tmp_path / "delivery.db"))
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    init_db(engine)
    with sessions() as session:
        device = Device(
            name="Delivery Device", device_type="emulator", platform="android",
            os_version="12", status="online",
        )
        device.runtimes.append(Runtime(
            name="Delivery Runtime", runtime_type="redroid", status="running",
            adb_serial="localhost:5699", docker_container_name="delivery-runtime",
        ))
        session.add(device)
        session.commit()
    application = create_test_app()

    def override_get_db() -> Iterator[Session]:
        with sessions() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    application.state.delivery_sessions = sessions
    with TestClient(application) as client:
        yield client
    application.dependency_overrides.clear()
    engine.dispose()


def upload(client: TestClient) -> dict:
    return client.post(
        "/content",
        files=[
            ("file", ("delivery.png", png_bytes(), "image/png")),
            ("display_name", (None, "Delivery image", None)),
        ],
    ).json()


def make_ready(client: TestClient, asset: dict) -> int:
    sessions = client.app.state.delivery_sessions
    with sessions() as session:
        version_id = asset["versions"][0]["id"]
        storage = ContentStorageService.from_application_config()
        executable = Path(client.app.state.delivery_sessions.kw["bind"].url.database).parent / "ffprobe"
        executable.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        executable.chmod(0o700)
        ContentInspectionService(
            session,
            storage=storage,
            guard=ContentVersionOperationGuard(executable.parent / "inspection-locks"),
            ffprobe=FfprobeInspector(executable),
            max_image_dimension=4096,
            max_image_pixels=1_000_000,
            max_image_frames=10,
        ).inspect(asset["id"], version_id)
        return version_id


def claim_headers(claim: dict) -> dict[str, str]:
    return {
        "X-Job-Claim-Token": claim["claim_token"],
        "X-Job-Attempt": str(claim["attempt_count"]),
    }


def test_delivery_creation_pins_version_and_enforces_repeat_idempotency(
    delivery_api: TestClient,
) -> None:
    asset = upload(delivery_api)
    runtime_id = 1
    processing = delivery_api.post(
        f"/content/{asset['id']}/deliver", json={"runtime_id": runtime_id}
    )
    assert processing.status_code == 409
    version_id = make_ready(delivery_api, asset)

    first = delivery_api.post(
        f"/content/{asset['id']}/deliver",
        json={"runtime_id": runtime_id, "idempotency_key": "delivery-key"},
    )
    assert first.status_code == 202
    first_body = first.json()
    assert first_body["created"] is True
    assert first_body["delivery"]["content_asset_version_id"] == version_id
    assert first_body["delivery"]["remote_path"].startswith(
        "/sdcard/Download/TikTokManager/"
    )
    assert ".." not in first_body["delivery"]["remote_filename"]
    repeated_key = delivery_api.post(
        f"/content/{asset['id']}/deliver",
        json={"runtime_id": runtime_id, "idempotency_key": "delivery-key"},
    ).json()
    assert repeated_key["created"] is False
    assert repeated_key["delivery"]["id"] == first_body["delivery"]["id"]

    no_repeat = delivery_api.post(
        f"/content/{asset['id']}/deliver", json={"runtime_id": runtime_id}
    ).json()
    assert no_repeat["created"] is False
    assert no_repeat["delivery"]["id"] == first_body["delivery"]["id"]
    intentional = delivery_api.post(
        f"/content/{asset['id']}/deliver",
        json={"runtime_id": runtime_id, "allow_repeat": True},
    ).json()
    assert intentional["created"] is True
    assert intentional["delivery"]["id"] != first_body["delivery"]["id"]
    assert intentional["delivery"]["remote_filename"] != first_body["delivery"]["remote_filename"]

    history = delivery_api.get(f"/content/{asset['id']}/deliveries").json()
    assert history["total"] == 2
    assert history["items"][0]["id"] == intentional["delivery"]["id"]
    with delivery_api.app.state.delivery_sessions() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.job_type == "content.deliver")) == 2
        assert session.scalar(select(func.count()).select_from(ContentEvent).where(
            ContentEvent.event_type == "delivery_repeated"
        )) == 1


def test_delivery_rejects_deleted_content_and_invalid_runtime(
    delivery_api: TestClient,
) -> None:
    asset = upload(delivery_api)
    make_ready(delivery_api, asset)
    missing_runtime = delivery_api.post(
        f"/content/{asset['id']}/deliver", json={"runtime_id": 9999}
    )
    assert missing_runtime.status_code == 404
    deleted = delivery_api.delete(f"/content/{asset['id']}")
    assert deleted.status_code == 200
    response = delivery_api.post(
        f"/content/{asset['id']}/deliver", json={"runtime_id": 1}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CONTENT_DELETED"


def test_delivery_executes_pinned_blob_without_job_artifact_copy(
    delivery_api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset = upload(delivery_api)
    version_id = make_ready(delivery_api, asset)
    created = delivery_api.post(
        f"/content/{asset['id']}/deliver",
        json={"runtime_id": 1, "filename": "safe name.png", "import_media": True},
    ).json()
    observed = {}

    def fake_deliver(self, runtime_id, source, *, filename, import_media):
        observed.update(runtime_id=runtime_id, source=source, filename=filename)
        return {
            "runtime_id": runtime_id,
            "remote_path": f"/sdcard/Download/TikTokManager/{filename}",
            "filename": filename,
            "size_bytes": source.size_bytes,
            "sha256": source.sha256,
            "media_imported": import_media,
            "media_uri": "content://media/external/file/77",
        }

    monkeypatch.setattr(AndroidAutomationService, "deliver_managed_file", fake_deliver)
    # The older upload-created inspection Job is already logically complete in
    # the version state; mark it terminal so the delivery Job is claimed next.
    with delivery_api.app.state.delivery_sessions() as session:
        version = session.get(ContentAssetVersion, version_id)
        inspect_job = session.get(Job, version.inspection_job_id)
        inspect_job.status = "succeeded"
        session.commit()
    claim = delivery_api.post("/jobs/claim").json()
    assert claim["job_type"] == "content.deliver" and claim["runtime_id"] == 1
    executed = delivery_api.post(
        f"/jobs/{claim['id']}/execute", headers=claim_headers(claim), json={}
    )
    assert executed.status_code == 200
    result = executed.json()["result"]
    assert result["status"] == "succeeded"
    assert result["content_asset_version_id"] == version_id
    assert observed["runtime_id"] == 1
    assert observed["source"].path.parent.name == "blobs"
    assert "safe_name-d" in observed["filename"]
    detail = delivery_api.get(
        f"/content-deliveries/{created['delivery']['id']}"
    ).json()
    assert detail["media_uri"] == "content://media/external/file/77"
    with delivery_api.app.state.delivery_sessions() as session:
        assert session.scalar(select(func.count()).select_from(ContentDelivery)) == 1
        assert session.scalar(select(func.count()).select_from(JobArtifact)) == 0


def test_pending_delivery_cancellation_updates_history(delivery_api: TestClient) -> None:
    asset = upload(delivery_api)
    make_ready(delivery_api, asset)
    created = delivery_api.post(
        f"/content/{asset['id']}/deliver", json={"runtime_id": 1}
    ).json()
    job_id = created["delivery"]["job_id"]
    cancelled = delivery_api.post(f"/jobs/{job_id}/cancel")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    detail = delivery_api.get(
        f"/content-deliveries/{created['delivery']['id']}"
    ).json()
    assert detail["status"] == "cancelled"
    assert detail["error_code"] == "CONTENT_DELIVERY_CANCELLED"


def test_delivery_deprovision_cleanup_cancels_pending_and_preserves_snapshot(
    delivery_api: TestClient, tmp_path: Path
) -> None:
    asset = upload(delivery_api)
    make_ready(delivery_api, asset)
    created = delivery_api.post(
        f"/content/{asset['id']}/deliver", json={"runtime_id": 1}
    ).json()
    factory = delivery_api.app.state.delivery_sessions
    RuntimeAutomationCleanupCoordinator(
        factory, RuntimeOperationGuard(tmp_path / "deprovision-locks")
    ).cleanup_before_delete(1)
    with factory() as session:
        delivery = session.get(ContentDelivery, created["delivery"]["id"])
        assert delivery.status == "cancelled"
        assert session.get(Job, delivery.job_id).status == "cancelled"
        session.delete(session.get(Runtime, 1))
        session.commit()
        session.refresh(delivery)
        assert delivery.runtime_id is None and delivery.runtime_id_snapshot == 1


def test_active_delivery_blocks_deprovision(delivery_api: TestClient, tmp_path: Path) -> None:
    asset = upload(delivery_api)
    make_ready(delivery_api, asset)
    created = delivery_api.post(
        f"/content/{asset['id']}/deliver", json={"runtime_id": 1}
    ).json()
    factory = delivery_api.app.state.delivery_sessions
    with factory() as session:
        job = session.get(Job, created["delivery"]["job_id"])
        job.status = "running"
        session.commit()
    coordinator = RuntimeAutomationCleanupCoordinator(
        factory, RuntimeOperationGuard(tmp_path / "deprovision-locks-active")
    )
    with pytest.raises(RuntimeAutomationBusyError):
        coordinator.cleanup_before_delete(1)
