"""Phase 3 device Job claims, leases, cancellation, and artifact API tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, init_db
from app.models import Job, JobArtifact, JobLog
from app.models.timestamps import utc_now
from app.services.job_lifecycle import claim_next_job, mark_job_failed, recover_expired_jobs
from tests.app_factory import create_test_app


@pytest.fixture
def phase3_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    url = URL.create(drivername="sqlite", database=str(tmp_path / "phase3.db"))
    engine = create_engine(url, connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    init_db(engine)
    monkeypatch.setenv("TIKTOK_MANAGER_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("TIKTOK_MANAGER_ARTIFACT_MAX_SIZE_BYTES", "1024")
    app = create_test_app()
    def override() -> Iterator[Session]:
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = override
    app.state.phase3_factory = factory
    with TestClient(app) as client:
        yield client
    engine.dispose()


def add_redroid(client: TestClient, suffix: str = "01") -> dict:
    device = client.post("/devices", json={
        "name": f"Automation {suffix}", "device_type": "virtual",
        "platform": "android", "os_version": "12", "status": "offline",
    }).json()
    response = client.post("/runtimes", json={
        "device_id": device["id"], "name": f"Redroid {suffix}",
        "runtime_type": "redroid", "status": "stopped",
        "adb_serial": f"localhost:56{suffix}",
        "docker_container_name": f"redroid-auto-{suffix}",
    })
    assert response.status_code == 201
    return response.json()


def headers(claim: dict) -> dict[str, str]:
    return {"X-Job-Claim-Token": claim["claim_token"], "X-Job-Attempt": str(claim["attempt_count"])}


def test_device_job_requires_exact_valid_redroid_runtime(phase3_api: TestClient) -> None:
    missing = phase3_api.post("/jobs", json={"job_type": "device.screenshot", "payload": {}})
    assert missing.status_code == 422
    runtime = add_redroid(phase3_api)
    created = phase3_api.post("/jobs", json={"job_type": "device.screenshot", "runtime_id": runtime["id"], "payload": {}})
    assert created.status_code == 201
    assert created.json()["runtime_id"] == runtime["id"]
    assert phase3_api.post("/jobs", json={"job_type": "device.tap", "runtime_id": runtime["id"], "payload": {"x": 1, "y": 2}}).status_code == 422


def test_claim_token_is_unique_hashed_hidden_and_heartbeat_owned(phase3_api: TestClient) -> None:
    runtime = add_redroid(phase3_api)
    job = phase3_api.post("/jobs", json={"job_type": "device.screenshot", "runtime_id": runtime["id"], "payload": {}}).json()
    claim = phase3_api.post("/jobs/claim", json={"claimed_by": "worker-a"}).json()
    assert len(claim["claim_token"]) >= 32
    assert "claim_token" not in phase3_api.get(f"/jobs/{job['id']}").json()
    wrong = phase3_api.post(f"/jobs/{job['id']}/heartbeat", headers={"X-Job-Claim-Token": "x" * 32, "X-Job-Attempt": "1"}, json={})
    assert wrong.status_code == 409
    heartbeat = phase3_api.post(f"/jobs/{job['id']}/heartbeat", headers=headers(claim), json={})
    assert heartbeat.status_code == 200
    with phase3_api.app.state.phase3_factory() as session:
        stored = session.get(Job, job["id"])
        assert stored.claim_token_hash and claim["claim_token"] not in stored.claim_token_hash
        assert all(claim["claim_token"] not in str(log.log_metadata) for log in session.scalars(select(JobLog)).all())


def test_retryability_and_stale_worker_protection(phase3_api: TestClient) -> None:
    runtime = add_redroid(phase3_api)
    job = phase3_api.post("/jobs", json={"job_type": "device.screenshot", "runtime_id": runtime["id"], "payload": {}, "max_attempts": 2}).json()
    first = phase3_api.post("/jobs/claim").json()
    failed = phase3_api.post(f"/jobs/{job['id']}/fail", headers=headers(first), json={"error_code": "ADB_UNAVAILABLE", "error_message": "ADB unavailable", "retryable": True})
    assert failed.json()["status"] == "pending"
    with phase3_api.app.state.phase3_factory() as session:
        current = session.get(Job, job["id"]); current.scheduled_at = None; session.commit()
    second = phase3_api.post("/jobs/claim").json()
    stale = phase3_api.post(f"/jobs/{job['id']}/succeed", headers=headers(first), json={"result": {}})
    assert stale.status_code == 409
    assert phase3_api.post(f"/jobs/{job['id']}/succeed", headers=headers(second), json={"result": {"runtime_id": runtime["id"]}}).status_code == 200


def test_running_cancellation_requires_worker_acknowledgement(phase3_api: TestClient) -> None:
    runtime = add_redroid(phase3_api)
    job = phase3_api.post("/jobs", json={"job_type": "device.screenshot", "runtime_id": runtime["id"], "payload": {}}).json()
    claim = phase3_api.post("/jobs/claim").json()
    requested = phase3_api.post(f"/jobs/{job['id']}/cancel").json()
    assert requested["status"] == "cancelling"
    acknowledged = phase3_api.post(f"/jobs/{job['id']}/cancel/acknowledge", headers=headers(claim), json={})
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "cancelled"


def test_execute_boundary_accepts_only_current_claim_and_registered_job(
    phase3_api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = add_redroid(phase3_api)
    job = phase3_api.post("/jobs", json={"job_type": "device.package_state", "runtime_id": runtime["id"], "payload": {"package_name": "com.android.settings"}}).json()
    claim = phase3_api.post("/jobs/claim").json()
    seen: dict = {}
    def fake_execute(_service, model, token, attempt):
        seen.update(job_id=model.id, runtime_id=model.runtime_id, token=token, attempt=attempt)
        return {"runtime_id": model.runtime_id, "package_name": "com.android.settings", "installed": True, "running": False, "pid": None}
    monkeypatch.setattr("app.routers.jobs.DeviceJobExecutionService.execute", fake_execute)
    assert phase3_api.post(f"/jobs/{job['id']}/execute", json={}).status_code == 422
    response = phase3_api.post(f"/jobs/{job['id']}/execute", headers=headers(claim), json={})
    assert response.status_code == 200
    assert seen == {"job_id": job["id"], "runtime_id": runtime["id"], "token": claim["claim_token"], "attempt": 1}


def test_expired_safe_job_is_recovered_but_uncertain_job_fails(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'leases.db'}")
    init_db(engine)
    with Session(engine, expire_on_commit=False) as session:
        safe = Job(job_type="device.screenshot", runtime_id=None, payload={}, max_attempts=2)
        uncertain = Job(job_type="device.push_file", runtime_id=None, payload={"artifact_id": 1}, max_attempts=2)
        session.add_all([safe, uncertain]); session.commit()
        safe_claim = claim_next_job(session, now=utc_now() - timedelta(minutes=3)); assert safe_claim
        safe.execution_started_at = utc_now() - timedelta(minutes=2); session.commit()
        uncertain_claim = claim_next_job(session, now=utc_now() - timedelta(minutes=3)); assert uncertain_claim
        uncertain.execution_started_at = utc_now() - timedelta(minutes=2); session.commit()
        recover_expired_jobs(session, now=utc_now())
        session.refresh(safe); session.refresh(uncertain)
        assert safe.status == "pending"
        assert uncertain.status == "failed"


def test_artifact_upload_association_and_download(phase3_api: TestClient) -> None:
    runtime = add_redroid(phase3_api)
    upload = phase3_api.post("/artifacts", files={"file": ("hello.txt", b"hello", "text/plain")})
    assert upload.status_code == 201
    artifact = upload.json()
    assert "storage_key" not in artifact
    assert artifact["state"] == "available"
    job = phase3_api.post("/jobs", json={
        "job_type": "device.push_file", "runtime_id": runtime["id"],
        "payload": {"artifact_id": artifact["id"]},
    })
    assert job.status_code == 201
    download = phase3_api.get(f"/jobs/{job.json()['id']}/artifacts/{artifact['id']}")
    assert download.status_code == 200 and download.content == b"hello"
    assert phase3_api.get(f"/jobs/{job.json()['id'] + 1}/artifacts/{artifact['id']}").status_code == 404


def test_expired_artifact_metadata_preserves_job_history(
    phase3_api: TestClient,
) -> None:
    runtime = add_redroid(phase3_api)
    artifact = phase3_api.post(
        "/artifacts",
        files={"file": ("history.txt", b"history", "text/plain")},
    ).json()
    job = phase3_api.post(
        "/jobs",
        json={
            "job_type": "device.push_file",
            "runtime_id": runtime["id"],
            "payload": {"artifact_id": artifact["id"]},
        },
    ).json()
    with phase3_api.app.state.phase3_factory() as session:
        stored = session.get(JobArtifact, artifact["id"])
        stored.cleanup_status = "expired"
        session.commit()

    metadata = phase3_api.get(f"/artifacts/{artifact['id']}")
    download = phase3_api.get(
        f"/jobs/{job['id']}/artifacts/{artifact['id']}"
    )

    assert metadata.status_code == 200
    assert metadata.json()["state"] == "expired"
    assert "storage_key" not in metadata.json()
    assert download.status_code == 410
    assert phase3_api.get(f"/jobs/{job['id']}").status_code == 200
