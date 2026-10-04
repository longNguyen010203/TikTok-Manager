"""Content inspection Job creation, execution boundary, and API behavior."""

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
from app.models import ContentAssetVersion, ContentBlob, Job
from tests.app_factory import create_test_app


def png_bytes(color=(20, 30, 40)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 6), color).save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def content_job_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("TIKTOK_MANAGER_CONTENT_ROOT", str(tmp_path / "content"))
    monkeypatch.setenv(
        "TIKTOK_MANAGER_CONTENT_INSPECTION_LOCK_DIRECTORY", str(tmp_path / "locks")
    )
    database_url = URL.create(drivername="sqlite", database=str(tmp_path / "api.db"))
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    init_db(engine)
    application = create_test_app()
    application.state.content_sessions = sessions

    def override_get_db() -> Iterator[Session]:
        with sessions() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as client:
        yield client
    application.dependency_overrides.clear()
    engine.dispose()


def upload(client: TestClient, data: bytes, name: str = "image.png"):
    return client.post(
        "/content",
        files=[
            ("file", (name, data, "image/png")),
            ("display_name", (None, "Inspected image", None)),
        ],
    )


def claim_headers(claim: dict) -> dict[str, str]:
    return {
        "X-Job-Claim-Token": claim["claim_token"],
        "X-Job-Attempt": str(claim["attempt_count"]),
    }


def test_upload_schedules_runtime_free_internal_inspection_and_executes(
    content_job_api: TestClient,
) -> None:
    content = png_bytes()
    created = upload(content_job_api, content)
    assert created.status_code == 202
    asset = created.json()
    with content_job_api.app.state.content_sessions() as session:
        version = session.get(ContentAssetVersion, asset["versions"][0]["id"])
        job = session.get(Job, version.inspection_job_id)
        assert job.job_type == "content.inspect"
        assert job.runtime_id is None
        assert job.payload == {
            "content_asset_id": asset["id"],
            "content_asset_version_id": version.id,
        }

    denied = content_job_api.post(
        "/jobs",
        json={
            "job_type": "content.inspect",
            "payload": {
                "content_asset_id": asset["id"],
                "content_asset_version_id": asset["versions"][0]["id"],
            },
        },
    )
    assert denied.status_code == 422

    claim = content_job_api.post("/jobs/claim").json()
    assert claim["job_type"] == "content.inspect" and claim["runtime_id"] is None
    executed = content_job_api.post(
        f"/jobs/{claim['id']}/execute", headers=claim_headers(claim), json={}
    )
    assert executed.status_code == 200
    assert executed.json()["result"]["processing_status"] == "ready"
    succeeded = content_job_api.post(
        f"/jobs/{claim['id']}/succeed",
        headers=claim_headers(claim),
        json={"result": executed.json()["result"]},
    )
    assert succeeded.status_code == 200

    ready = content_job_api.get(f"/content/{asset['id']}").json()
    assert ready["status"] == "ready"
    assert ready["current_version"]["width"] == 8
    assert ready["current_version"]["height"] == 6
    downloaded = content_job_api.get(f"/content/{asset['id']}/download")
    assert downloaded.status_code == 200 and downloaded.content == content


def test_replacement_switches_only_after_success_and_failed_one_preserves_download(
    content_job_api: TestClient,
) -> None:
    original = png_bytes((1, 2, 3))
    asset = upload(content_job_api, original).json()
    first_claim = content_job_api.post("/jobs/claim").json()
    first_result = content_job_api.post(
        f"/jobs/{first_claim['id']}/execute",
        headers=claim_headers(first_claim), json={},
    ).json()["result"]
    content_job_api.post(
        f"/jobs/{first_claim['id']}/succeed",
        headers=claim_headers(first_claim), json={"result": first_result},
    )
    first_version_id = first_result["content_asset_version_id"]

    replacement = content_job_api.post(
        f"/content/{asset['id']}/versions",
        files={"file": ("replacement.png", b"\x89PNG\r\n\x1a\nbroken", "image/png")},
    )
    assert replacement.status_code == 202
    assert replacement.json()["current_version"]["id"] == first_version_id
    second_claim = content_job_api.post("/jobs/claim").json()
    failed = content_job_api.post(
        f"/jobs/{second_claim['id']}/execute",
        headers=claim_headers(second_claim), json={},
    )
    assert failed.status_code == 422
    assert failed.json()["detail"]["code"] == "CONTENT_IMAGE_INVALID"
    content_job_api.post(
        f"/jobs/{second_claim['id']}/fail",
        headers=claim_headers(second_claim),
        json={
            "error_code": "CONTENT_IMAGE_INVALID",
            "error_message": "Image could not be decoded",
            "retryable": False,
        },
    )
    current = content_job_api.get(f"/content/{asset['id']}").json()
    assert current["status"] == "ready"
    assert current["current_version"]["id"] == first_version_id
    assert current["versions"][-1]["processing_status"] == "invalid"
    assert content_job_api.get(f"/content/{asset['id']}/download").content == original


def test_duplicate_uploads_schedule_independent_jobs_but_share_blob(
    content_job_api: TestClient,
) -> None:
    content = png_bytes()
    first = upload(content_job_api, content).json()
    second = upload(content_job_api, content).json()
    assert first["id"] != second["id"]
    with content_job_api.app.state.content_sessions() as session:
        assert session.scalar(select(func.count()).select_from(ContentBlob)) == 1
        jobs = list(session.scalars(select(Job).where(Job.job_type == "content.inspect")))
        assert len(jobs) == 2
