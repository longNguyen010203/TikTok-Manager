"""Workflow persistence, API, locking, and reconciliation tests."""

from __future__ import annotations

import os
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, init_db
from app.models import (
    Account, ContentAsset, ContentAssetVersion, ContentBlob, Device, Job,
    Runtime, Workflow, WorkflowEvent, WorkflowStep, WorkflowStepJobRun,
)
from app.services.workflow_lock import WorkflowOperationGuard, WorkflowOperationLockBusy, WorkflowOperationLockError
from app.services.workflow_orchestrator import WorkflowOrchestrator
from app.services.workflow_service import WorkflowError, WorkflowService
from app.services.workflow_state import WorkflowTransitionError, transition_step, transition_workflow
from app.services.workflow_wait import WorkflowWaitError, calculate_resume_at
from app.services.job_lifecycle import recover_expired_jobs
from app.workflow_orchestrator import poll_delay
from app.models.timestamps import utc_now
from tests.app_factory import create_test_app


def _hold_workflow_lock(directory: str, ready: multiprocessing.synchronize.Event) -> None:
    with WorkflowOperationGuard(Path(directory)).acquire_workflow(77):
        ready.set()
        multiprocessing.Event().wait(30)


@pytest.fixture
def workflow_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("TIKTOK_MANAGER_WORKFLOW_LOCK_DIRECTORY", str(tmp_path / "locks"))
    engine = create_engine(f"sqlite:///{tmp_path / 'workflow.db'}", connect_args={"check_same_thread": False})
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    init_db(engine)
    with sessions() as session:
        device = Device(name="Workflow Device", device_type="emulator", platform="android", os_version="12", status="online")
        runtime = Runtime(name="Workflow Runtime", runtime_type="redroid", status="running", adb_serial="localhost:5799", docker_container_name="workflow-runtime")
        device.runtimes.append(runtime)
        blob = ContentBlob(storage_key="a" * 32, sha256="b" * 64, size_bytes=10, detected_mime_type="image/png", status="active")
        asset = ContentAsset(asset_type="image", display_name="Workflow image", source="upload", status="ready")
        version = ContentAssetVersion(asset=asset, version_number=1, blob=blob, original_filename="image.png", detected_mime_type="image/png", canonical_extension=".png", processing_status="ready")
        session.add_all([device, blob, asset, version]); session.flush()
        asset.current_version_id = version.id
        account = Account(name="A", username="a", platform="generic", status="active", runtime_id=runtime.id)
        session.add(account); session.commit()
    app = create_test_app()
    def override() -> Iterator[Session]:
        with sessions() as session:
            yield session
    app.dependency_overrides[get_db] = override
    app.state.workflow_sessions = sessions
    app.state.workflow_lock_directory = tmp_path / "locks"
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear(); engine.dispose()


def request_body(**updates: object) -> dict:
    body = {
        "template_key": "content_delivery_review", "name": "Review image",
        "runtime_id": 1, "content_asset_id": 1,
        "parameters": {"import_media": True},
    }
    body.update(updates)
    return body


def test_template_creation_pins_bindings_and_is_idempotent(workflow_api: TestClient) -> None:
    templates = workflow_api.get("/workflow-templates")
    assert templates.status_code == 200
    assert [(item["key"], item["version"]) for item in templates.json()] == [
        ("content_delivery_review", 1), ("content_delivery_wait_review", 1),
    ]
    first = workflow_api.post("/workflows", json=request_body(idempotency_key="create-1"))
    assert first.status_code == 201
    data = first.json()
    assert data["status"] == "draft"
    assert data["runtime_id_snapshot"] == 1
    assert data["content_asset_version_id"] == 1
    assert [step["step_type"] for step in data["steps"]] == ["content.deliver", "workflow.approval"]
    repeat = workflow_api.post("/workflows", json=request_body(idempotency_key="create-1"))
    assert repeat.status_code == 200
    assert repeat.json()["id"] == data["id"]
    conflict = workflow_api.post("/workflows", json=request_body(idempotency_key="create-1", name="Other"))
    assert conflict.status_code == 409
    with workflow_api.app.state.workflow_sessions() as session:
        assert len(list(session.scalars(select(WorkflowStep)))) == 2
        assert len(list(session.scalars(select(WorkflowEvent)))) == 1


def test_concurrent_idempotent_creation_returns_one_workflow(
    workflow_api: TestClient,
) -> None:
    body = request_body(idempotency_key="concurrent-create-1")

    def create() -> tuple[int, int]:
        response = workflow_api.post("/workflows", json=body)
        return response.status_code, response.json()["id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: create(), range(16)))

    assert {status for status, _ in outcomes} <= {200, 201}
    assert len({workflow_id for _, workflow_id in outcomes}) == 1
    with workflow_api.app.state.workflow_sessions() as session:
        workflow_id = outcomes[0][1]
        assert session.query(Workflow).filter_by(
            idempotency_key="concurrent-create-1"
        ).count() == 1
        assert session.query(WorkflowStep).filter_by(
            workflow_id=workflow_id
        ).count() == 2
        assert session.query(WorkflowEvent).filter_by(
            workflow_id=workflow_id, event_type="workflow_created"
        ).count() == 1


def test_creation_rejects_arbitrary_steps_jobs_parameters_and_binding_mismatch(workflow_api: TestClient) -> None:
    assert workflow_api.post("/workflows", json={**request_body(), "steps": []}).status_code == 422
    assert workflow_api.post("/workflows", json={**request_body(), "job_type": "device.tap"}).status_code == 422
    response = workflow_api.post("/workflows", json=request_body(parameters={"raw_payload": {"shell": "id"}}))
    assert response.status_code == 422
    assert workflow_api.post("/workflows", json=request_body(runtime_id=999)).status_code == 404
    with workflow_api.app.state.workflow_sessions() as session:
        other_device = Device(name="Other", device_type="emulator", platform="android", os_version="12", status="online")
        other_device.runtimes.append(Runtime(name="Other Runtime", runtime_type="redroid", status="running"))
        session.add(other_device); session.flush()
        account = session.get(Account, 1); assert account is not None
        account.runtime_id = other_device.runtimes[0].id; session.commit()
    assert workflow_api.post("/workflows", json=request_body(account_id=1)).status_code == 409


def test_orchestrator_materializes_one_job_reconciles_and_waits_for_approval(workflow_api: TestClient) -> None:
    workflow = workflow_api.post("/workflows", json=request_body()).json()
    assert workflow_api.post(f"/workflows/{workflow['id']}/start").status_code == 200
    sessions = workflow_api.app.state.workflow_sessions
    orchestrator = WorkflowOrchestrator(sessions, WorkflowOperationGuard(workflow_api.app.state.workflow_lock_directory))
    assert orchestrator.run_once() == 1
    with sessions() as session:
        row = session.get(Workflow, workflow["id"]); assert row is not None
        steps = list(session.scalars(select(WorkflowStep).where(WorkflowStep.workflow_id == row.id).order_by(WorkflowStep.step_index)))
        assert row.status == "running" and steps[0].status == "running"
        assert steps[0].job_id is not None and steps[1].job_id is None
        assert len(list(session.scalars(select(WorkflowStepJobRun)))) == 1
        job = session.get(Job, steps[0].job_id); assert job is not None
        # Reconciliation while the linked Job is active must not duplicate it.
    orchestrator.run_once()
    with sessions() as session:
        assert len(list(session.scalars(select(Job)))) == 1
        steps = list(session.scalars(select(WorkflowStep).order_by(WorkflowStep.step_index)))
        job = session.get(Job, steps[0].job_id); assert job is not None
        job.status = "succeeded"; job.result = {"delivery_id": 1, "unsafe": "/host/path"}; session.commit()
    orchestrator.run_once()
    detail = workflow_api.get(f"/workflows/{workflow['id']}").json()
    assert detail["status"] == "waiting"
    assert detail["steps"][0]["result_json"] == {
        "delivery_id": 1, "job_id": 1, "runtime_id_snapshot": 1,
        "content_asset_version_id": 1,
    }
    approval = detail["steps"][1]
    assert approval["status"] == "waiting" and approval["job_id"] is None
    approved = workflow_api.post(
        f"/workflows/{workflow['id']}/steps/{approval['id']}/approve",
        json={"actor": "operator", "comment": "Looks good"},
    )
    assert approved.status_code == 200 and approved.json()["status"] == "running"
    orchestrator.run_once()
    assert workflow_api.get(f"/workflows/{workflow['id']}").json()["status"] == "succeeded"
    with sessions() as session:
        assert len(list(session.scalars(select(Job)))) == 1


def test_rejection_pause_and_list_order_filters(workflow_api: TestClient) -> None:
    first = workflow_api.post("/workflows", json=request_body(name="First")).json()
    second = workflow_api.post("/workflows", json=request_body(name="Second")).json()
    listed = workflow_api.get("/workflows", params={"runtime_id": 1, "template": "content_delivery_review", "page_size": 1}).json()
    assert listed["total"] == 2 and listed["items"][0]["id"] == second["id"]
    assert workflow_api.post(f"/workflows/{first['id']}/start").status_code == 200
    paused = workflow_api.post(f"/workflows/{first['id']}/pause").json()
    assert paused["status"] == "paused"
    assert workflow_api.post(f"/workflows/{first['id']}/resume").json()["status"] == "pending"


def test_explicit_state_machines_reject_invalid_transitions() -> None:
    workflow = Workflow(status="draft", transition_version=0)
    transition_workflow(workflow, "pending")
    with pytest.raises(WorkflowTransitionError): transition_workflow(workflow, "succeeded")
    step = WorkflowStep(status="pending", transition_version=0)
    transition_step(step, "ready")
    with pytest.raises(WorkflowTransitionError): transition_step(step, "succeeded")


def test_workflow_lock_contention_release_isolation_and_symlink(tmp_path: Path) -> None:
    guard = WorkflowOperationGuard(tmp_path / "locks")
    with guard.acquire_workflow(1):
        with pytest.raises(WorkflowOperationLockBusy):
            with guard.acquire_workflow(1, blocking=False): pass
        with guard.acquire_workflow(2, blocking=False): pass
    with guard.acquire_workflow(1, blocking=False): pass
    unsafe = tmp_path / "unsafe"
    os.symlink(tmp_path, unsafe)
    with pytest.raises(WorkflowOperationLockError):
        with WorkflowOperationGuard(unsafe).acquire_workflow(1): pass


def test_workflow_lock_releases_when_owner_process_dies(tmp_path: Path) -> None:
    directory = tmp_path / "process-locks"
    ready = multiprocessing.Event()
    process = multiprocessing.Process(target=_hold_workflow_lock, args=(str(directory), ready))
    process.start()
    try:
        assert ready.wait(5)
        with pytest.raises(WorkflowOperationLockBusy):
            with WorkflowOperationGuard(directory).acquire_workflow(77, blocking=False): pass
    finally:
        process.terminate()
        process.join(5)
    assert not process.is_alive()
    with WorkflowOperationGuard(directory).acquire_workflow(77, blocking=False): pass


def test_cancel_draft_and_approval_reject_are_durable(workflow_api: TestClient) -> None:
    cancelled = workflow_api.post("/workflows", json=request_body(name="Cancel")).json()
    result = workflow_api.post(f"/workflows/{cancelled['id']}/cancel").json()
    assert result["status"] == "cancelled"
    assert all(step["status"] == "cancelled" for step in result["steps"])


def test_active_pause_stops_at_boundary_and_resume_restores_approval(workflow_api: TestClient) -> None:
    workflow = workflow_api.post("/workflows", json=request_body(name="Pause boundary")).json()
    workflow_api.post(f"/workflows/{workflow['id']}/start")
    sessions = workflow_api.app.state.workflow_sessions
    orchestrator = WorkflowOrchestrator(sessions, WorkflowOperationGuard(workflow_api.app.state.workflow_lock_directory))
    orchestrator.run_once()
    paused = workflow_api.post(f"/workflows/{workflow['id']}/pause").json()
    assert paused["status"] == "running" and paused["pause_requested_at"] is not None
    with sessions() as session:
        step = session.scalar(select(WorkflowStep).where(WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 0))
        job = session.get(Job, step.job_id); job.status = "succeeded"; session.commit()
    orchestrator.run_once()
    assert workflow_api.get(f"/workflows/{workflow['id']}").json()["status"] == "paused"
    workflow_api.post(f"/workflows/{workflow['id']}/resume")
    orchestrator.run_once()
    resumed = workflow_api.get(f"/workflows/{workflow['id']}").json()
    assert resumed["status"] == "waiting"
    assert resumed["steps"][1]["waiting_reason"] == "waiting_for_approval"


def test_failed_step_retry_reuses_job_and_active_cancel_reconciles(workflow_api: TestClient) -> None:
    sessions = workflow_api.app.state.workflow_sessions
    guard = WorkflowOperationGuard(workflow_api.app.state.workflow_lock_directory)
    orchestrator = WorkflowOrchestrator(sessions, guard)
    failed = workflow_api.post("/workflows", json=request_body(name="Retry")).json()
    workflow_api.post(f"/workflows/{failed['id']}/start"); orchestrator.run_once()
    with sessions() as session:
        step = session.scalar(select(WorkflowStep).where(WorkflowStep.workflow_id == failed["id"], WorkflowStep.step_index == 0))
        original_job_id = step.job_id
        job = session.get(Job, original_job_id); job.status = "failed"; job.attempt_count = 1; job.error_code = "ADB_UNAVAILABLE"; session.commit()
    orchestrator.run_once()
    retried = workflow_api.post(f"/workflows/{failed['id']}/retry")
    assert retried.status_code == 200 and retried.json()["status"] == "pending"
    assert retried.json()["completed_at"] is None
    assert retried.json()["steps"][0]["completed_at"] is None
    orchestrator.run_once()
    with sessions() as session:
        step = session.scalar(select(WorkflowStep).where(WorkflowStep.workflow_id == failed["id"], WorkflowStep.step_index == 0))
        assert step.job_id == original_job_id
        assert len(list(session.scalars(select(WorkflowStepJobRun).where(WorkflowStepJobRun.workflow_step_id == step.id)))) == 1

    cancelling = workflow_api.post("/workflows", json=request_body(name="Cancel active", idempotency_key="cancel-active")).json()
    workflow_api.post(f"/workflows/{cancelling['id']}/start"); orchestrator.run_once()
    response = workflow_api.post(f"/workflows/{cancelling['id']}/cancel")
    assert response.status_code == 200 and response.json()["status"] == "cancelling"
    orchestrator.run_once()
    assert workflow_api.get(f"/workflows/{cancelling['id']}").json()["status"] == "cancelled"


def test_approval_rejection_survives_reconciliation(workflow_api: TestClient) -> None:
    workflow = workflow_api.post("/workflows", json=request_body(name="Reject")).json()
    workflow_api.post(f"/workflows/{workflow['id']}/start")
    sessions = workflow_api.app.state.workflow_sessions
    orchestrator = WorkflowOrchestrator(sessions, WorkflowOperationGuard(workflow_api.app.state.workflow_lock_directory))
    orchestrator.run_once()
    with sessions() as session:
        step = session.scalar(select(WorkflowStep).where(WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 0))
        job = session.get(Job, step.job_id); job.status = "succeeded"; session.commit()
    orchestrator.run_once()
    detail = workflow_api.get(f"/workflows/{workflow['id']}").json()
    approval_id = detail["steps"][1]["id"]
    rejected = workflow_api.post(
        f"/workflows/{workflow['id']}/steps/{approval_id}/reject",
        json={"actor": "operator", "comment": "Needs review"},
    ).json()
    assert rejected["status"] == "failed"
    assert rejected["error_code"] == "WORKFLOW_APPROVAL_REJECTED"
    duplicate = workflow_api.post(
        f"/workflows/{workflow['id']}/steps/{approval_id}/reject",
        json={"actor": "operator"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "WORKFLOW_APPROVAL_NOT_WAITING"


def test_wait_step_persists_deadline_and_recovers_with_new_orchestrator(workflow_api: TestClient) -> None:
    body = request_body(
        template_key="content_delivery_wait_review",
        name="Wait review",
        parameters={"import_media": True, "wait_duration_seconds": 10},
    )
    workflow = workflow_api.post("/workflows", json=body).json()
    workflow_api.post(f"/workflows/{workflow['id']}/start")
    sessions = workflow_api.app.state.workflow_sessions
    guard = WorkflowOperationGuard(workflow_api.app.state.workflow_lock_directory)
    WorkflowOrchestrator(sessions, guard).run_once()
    with sessions() as session:
        delivery = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 0
        ))
        job = session.get(Job, delivery.job_id)
        job.status = "succeeded"
        job.result = {"content_delivery_id": 42, "status": "succeeded", "remote_path": "/unsafe"}
        session.commit()
    WorkflowOrchestrator(sessions, guard).run_once()
    with sessions() as session:
        wait = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 1
        ))
        original_resume_at = wait.resume_at
        assert wait.status == "waiting" and original_resume_at is not None
    # A restart/repeated pass must not recalculate the duration.
    WorkflowOrchestrator(sessions, guard).run_once()
    with sessions() as session:
        wait = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 1
        ))
        assert wait.resume_at == original_resume_at
        wait.resume_at = utc_now() - timedelta(seconds=1)
        session.commit()
    WorkflowOrchestrator(sessions, guard).run_once()
    detail = workflow_api.get(f"/workflows/{workflow['id']}").json()
    assert detail["status"] == "waiting"
    assert [step["status"] for step in detail["steps"]] == ["succeeded", "succeeded", "waiting"]
    assert detail["steps"][0]["result_json"]["delivery_id"] == 42
    assert "remote_path" not in detail["steps"][0]["result_json"]
    events = workflow_api.get(f"/workflows/{workflow['id']}/events").json()["items"]
    assert [event["event_type"] for event in events].count("waiting") == 1
    assert [event["event_type"] for event in events].count("job_created") == 1


def test_wait_validation_requires_exactly_one_bounded_time_source(workflow_api: TestClient) -> None:
    invalid = workflow_api.post("/workflows", json=request_body(
        template_key="content_delivery_wait_review",
        parameters={"wait_duration_seconds": 0},
    ))
    assert invalid.status_code == 422
    now = utc_now()
    with pytest.raises(WorkflowWaitError):
        calculate_resume_at({}, now=now)
    with pytest.raises(WorkflowWaitError):
        calculate_resume_at({"duration_seconds": 1, "resume_at": now.isoformat()}, now=now)
    absolute = calculate_resume_at({"resume_at": (now + timedelta(seconds=5)).isoformat()}, now=now)
    assert absolute >= now + timedelta(seconds=5)


def test_unexpected_job_cancel_fails_and_binding_disappearance_never_retargets(workflow_api: TestClient) -> None:
    sessions = workflow_api.app.state.workflow_sessions
    guard = WorkflowOperationGuard(workflow_api.app.state.workflow_lock_directory)
    orchestrator = WorkflowOrchestrator(sessions, guard)
    cancelled = workflow_api.post("/workflows", json=request_body(name="Unexpected cancel")).json()
    workflow_api.post(f"/workflows/{cancelled['id']}/start"); orchestrator.run_once()
    with sessions() as session:
        step = session.scalar(select(WorkflowStep).where(WorkflowStep.workflow_id == cancelled["id"], WorkflowStep.step_index == 0))
        job = session.get(Job, step.job_id); job.status = "cancelled"; session.commit()
    orchestrator.run_once()
    detail = workflow_api.get(f"/workflows/{cancelled['id']}").json()
    assert detail["status"] == "failed" and detail["error_code"] == "WORKFLOW_JOB_CANCELLED"

    missing = workflow_api.post("/workflows", json=request_body(name="Missing runtime")).json()
    workflow_api.post(f"/workflows/{missing['id']}/start")
    with sessions() as session:
        session.delete(session.get(Runtime, 1)); session.commit()
    orchestrator.run_once()
    detail = workflow_api.get(f"/workflows/{missing['id']}").json()
    assert detail["status"] == "failed"
    assert detail["error_code"] == "WORKFLOW_RUNTIME_UNAVAILABLE"
    assert detail["runtime_id"] is None and detail["runtime_id_snapshot"] == 1


def test_deleted_content_fails_before_job_and_events_are_not_duplicated(workflow_api: TestClient) -> None:
    workflow = workflow_api.post("/workflows", json=request_body(name="Deleted content")).json()
    workflow_api.post(f"/workflows/{workflow['id']}/start")
    sessions = workflow_api.app.state.workflow_sessions
    with sessions() as session:
        asset = session.get(ContentAsset, 1)
        asset.status = "deleted"
        session.commit()
    orchestrator = WorkflowOrchestrator(
        sessions, WorkflowOperationGuard(workflow_api.app.state.workflow_lock_directory)
    )
    orchestrator.run_once()
    orchestrator.run_once()
    detail = workflow_api.get(f"/workflows/{workflow['id']}").json()
    assert detail["status"] == "failed" and detail["error_code"] == "CONTENT_DELETED"
    with sessions() as session:
        assert session.scalar(select(Job).where(Job.job_type == "content.deliver")) is None
        events = list(session.scalars(select(WorkflowEvent).where(
            WorkflowEvent.workflow_id == workflow["id"]
        ).order_by(WorkflowEvent.id)))
        kinds = [event.event_type for event in events]
        assert kinds.count("workflow_started") == 1
        assert kinds.count("step_failed") == 1
        assert kinds.count("workflow_failed") == 1


def test_job_success_winning_cancellation_race_is_truthful(workflow_api: TestClient) -> None:
    workflow = workflow_api.post("/workflows", json=request_body(name="Cancel race")).json()
    workflow_api.post(f"/workflows/{workflow['id']}/start")
    sessions = workflow_api.app.state.workflow_sessions
    orchestrator = WorkflowOrchestrator(
        sessions, WorkflowOperationGuard(workflow_api.app.state.workflow_lock_directory)
    )
    orchestrator.run_once()
    with sessions() as session:
        step = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 0
        ))
        job = session.get(Job, step.job_id)
        job.status = "running"
        session.commit()
    assert workflow_api.post(f"/workflows/{workflow['id']}/cancel").json()["status"] == "cancelling"
    with sessions() as session:
        step = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 0
        ))
        job = session.get(Job, step.job_id)
        job.status = "succeeded"
        job.result = {"content_delivery_id": 77, "status": "succeeded"}
        session.commit()
    orchestrator.run_once()
    detail = workflow_api.get(f"/workflows/{workflow['id']}").json()
    assert detail["status"] == "cancelled"
    assert detail["steps"][0]["status"] == "succeeded"
    assert detail["steps"][0]["result_json"]["delivery_id"] == 77
    assert detail["steps"][1]["status"] == "cancelled"


def test_worker_lease_recovery_keeps_exact_linked_job(workflow_api: TestClient) -> None:
    workflow = workflow_api.post("/workflows", json=request_body(name="Worker interruption")).json()
    workflow_api.post(f"/workflows/{workflow['id']}/start")
    sessions = workflow_api.app.state.workflow_sessions
    orchestrator = WorkflowOrchestrator(
        sessions, WorkflowOperationGuard(workflow_api.app.state.workflow_lock_directory)
    )
    orchestrator.run_once()
    with sessions() as session:
        step = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 0
        ))
        job_id = step.job_id
        job = session.get(Job, job_id)
        job.status = "running"
        job.attempt_count = 1
        job.lease_expires_at = utc_now() - timedelta(seconds=1)
        job.execution_started_at = utc_now()
        session.commit()
        assert recover_expired_jobs(session, now=utc_now(), retry_delay=timedelta(0)) == 1
    orchestrator.run_once()
    orchestrator.run_once()
    with sessions() as session:
        step = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 0
        ))
        assert step.job_id == job_id
        assert session.get(Job, job_id).status == "pending"
        assert session.query(WorkflowStepJobRun).filter_by(
            workflow_step_id=step.id
        ).count() == 1
        assert session.query(Job).filter_by(job_type="content.deliver").count() == 1


def test_crash_windows_reconcile_same_job_once(workflow_api: TestClient) -> None:
    workflow = workflow_api.post("/workflows", json=request_body(name="Crash windows")).json()
    workflow_api.post(f"/workflows/{workflow['id']}/start")
    sessions = workflow_api.app.state.workflow_sessions
    guard = WorkflowOperationGuard(workflow_api.app.state.workflow_lock_directory)
    WorkflowOrchestrator(sessions, guard).run_once()
    with sessions() as session:
        step = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 0
        ))
        job_id = step.job_id
        assert session.query(WorkflowStepJobRun).filter_by(
            workflow_step_id=step.id
        ).count() == 1
    # A new process after the job-link commit must reuse that exact Job.
    WorkflowOrchestrator(sessions, guard).run_once()
    with sessions() as session:
        step = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 0
        ))
        job = session.get(Job, job_id)
        job.status = "succeeded"
        job.result = {"content_delivery_id": 88, "status": "succeeded"}
        session.commit()
    # Simulate restart after Job success but before the Workflow transition.
    WorkflowOrchestrator(sessions, guard).run_once()
    WorkflowOrchestrator(sessions, guard).run_once()
    with sessions() as session:
        steps = list(session.scalars(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"]
        ).order_by(WorkflowStep.step_index)))
        events = list(session.scalars(select(WorkflowEvent).where(
            WorkflowEvent.workflow_id == workflow["id"]
        )))
        kinds = [event.event_type for event in events]
        assert steps[0].job_id == job_id and steps[0].status == "succeeded"
        assert steps[1].status == "waiting"
        assert session.query(Job).filter_by(job_type="content.deliver").count() == 1
        assert session.query(WorkflowStepJobRun).filter_by(
            workflow_step_id=steps[0].id
        ).count() == 1
        assert kinds.count("job_created") == 1
        assert kinds.count("step_succeeded") == 1
        assert kinds.count("waiting_for_approval") == 1


def test_retry_requests_are_serialized_without_duplicate_materialization(
    workflow_api: TestClient,
) -> None:
    workflow = workflow_api.post("/workflows", json=request_body(name="Retry race")).json()
    workflow_api.post(f"/workflows/{workflow['id']}/start")
    sessions = workflow_api.app.state.workflow_sessions
    guard = WorkflowOperationGuard(workflow_api.app.state.workflow_lock_directory)
    orchestrator = WorkflowOrchestrator(sessions, guard)
    orchestrator.run_once()
    with sessions() as session:
        step = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 0
        ))
        job_id = step.job_id
        job = session.get(Job, job_id)
        job.status = "failed"
        job.attempt_count = 1
        job.error_code = "ADB_UNAVAILABLE"
        session.commit()
    orchestrator.run_once()

    def request_retry() -> str:
        with sessions() as session:
            try:
                WorkflowService(guard).command(session, workflow["id"], "retry")
                return "accepted"
            except WorkflowError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: request_retry(), range(2)))
    assert outcomes.count("accepted") == 1
    assert set(outcomes) <= {"accepted", "WORKFLOW_BUSY", "INVALID_WORKFLOW_TRANSITION"}
    orchestrator.run_once()
    with sessions() as session:
        step = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 0
        ))
        assert step.job_id == job_id
        assert session.query(WorkflowStepJobRun).filter_by(
            workflow_step_id=step.id
        ).count() == 1
        assert session.query(WorkflowEvent).filter_by(
            workflow_id=workflow["id"], event_type="retry_requested"
        ).count() == 1


@pytest.mark.parametrize("decisions", [(True, True), (False, False), (True, False)])
def test_approval_decisions_are_serialized(
    workflow_api: TestClient, decisions: tuple[bool, bool]
) -> None:
    workflow = workflow_api.post("/workflows", json=request_body(
        name=f"Approval race {decisions}",
        idempotency_key=f"approval-race-{int(decisions[0])}-{int(decisions[1])}",
    )).json()
    workflow_api.post(f"/workflows/{workflow['id']}/start")
    sessions = workflow_api.app.state.workflow_sessions
    guard = WorkflowOperationGuard(workflow_api.app.state.workflow_lock_directory)
    orchestrator = WorkflowOrchestrator(sessions, guard)
    orchestrator.run_once()
    with sessions() as session:
        delivery = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 0
        ))
        job = session.get(Job, delivery.job_id)
        job.status = "succeeded"
        session.commit()
    orchestrator.run_once()
    with sessions() as session:
        approval_id = session.scalar(select(WorkflowStep.id).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 1
        ))

    def decide(approved: bool) -> str:
        with sessions() as session:
            try:
                WorkflowService(guard).decide_approval(
                    session, workflow["id"], approval_id,
                    approved=approved, actor="concurrent-operator", comment=None,
                )
                return "accepted"
            except WorkflowError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(decide, decisions))
    assert outcomes.count("accepted") == 1
    assert set(outcomes) <= {"accepted", "WORKFLOW_BUSY", "WORKFLOW_APPROVAL_NOT_WAITING"}
    with sessions() as session:
        step = session.get(WorkflowStep, approval_id)
        decision_events = session.query(WorkflowEvent).filter(
            WorkflowEvent.workflow_id == workflow["id"],
            WorkflowEvent.event_type.in_(["approved", "rejected"]),
        ).all()
        assert step.approval_decision in {"approved", "rejected"}
        assert len(decision_events) == 1


def test_due_wait_concurrent_reconciliation_advances_once(workflow_api: TestClient) -> None:
    workflow = workflow_api.post("/workflows", json=request_body(
        template_key="content_delivery_wait_review",
        name="Concurrent wait",
        parameters={"import_media": True, "wait_duration_seconds": 10},
    )).json()
    workflow_api.post(f"/workflows/{workflow['id']}/start")
    sessions = workflow_api.app.state.workflow_sessions
    guard = WorkflowOperationGuard(workflow_api.app.state.workflow_lock_directory)
    orchestrator = WorkflowOrchestrator(sessions, guard)
    orchestrator.run_once()
    with sessions() as session:
        delivery = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 0
        ))
        session.get(Job, delivery.job_id).status = "succeeded"
        session.commit()
    orchestrator.run_once()
    with sessions() as session:
        wait = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 1
        ))
        wait.resume_at = utc_now() - timedelta(seconds=1)
        session.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: WorkflowOrchestrator(sessions, guard).run_once(), range(2)))
    with sessions() as session:
        steps = list(session.scalars(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"]
        ).order_by(WorkflowStep.step_index)))
        events = list(session.scalars(select(WorkflowEvent).where(
            WorkflowEvent.workflow_id == workflow["id"]
        )))
        kinds = [event.event_type for event in events]
        assert [step.status for step in steps] == ["succeeded", "succeeded", "waiting"]
        assert kinds.count("waiting") == 1
        assert kinds.count("waiting_for_approval") == 1
        assert sum(
            event.event_type == "step_succeeded" and event.workflow_step_id == steps[1].id
            for event in events
        ) == 1


def test_result_and_error_projection_is_bounded_and_sanitized(workflow_api: TestClient) -> None:
    workflow = workflow_api.post("/workflows", json=request_body(name="Safe projection")).json()
    workflow_api.post(f"/workflows/{workflow['id']}/start")
    sessions = workflow_api.app.state.workflow_sessions
    orchestrator = WorkflowOrchestrator(
        sessions, WorkflowOperationGuard(workflow_api.app.state.workflow_lock_directory)
    )
    orchestrator.run_once()
    with sessions() as session:
        step = session.scalar(select(WorkflowStep).where(
            WorkflowStep.workflow_id == workflow["id"], WorkflowStep.step_index == 0
        ))
        job = session.get(Job, step.job_id)
        job.status = "succeeded"
        job.result = {
            "content_delivery_id": 91,
            "remote_filename": "safe.png",
            "claim_token": "do-not-project",
            "remote_path": "/host/private/path",
            "payload": {"raw": "unsafe"},
            "stderr": "unsafe",
        }
        session.commit()
    orchestrator.run_once()
    detail = workflow_api.get(f"/workflows/{workflow['id']}").json()
    result = detail["steps"][0]["result_json"]
    serialized = str(result)
    assert result["delivery_id"] == 91 and result["remote_filename"] == "safe.png"
    assert "claim_token" not in serialized
    assert "remote_path" not in serialized
    assert "/host/private/path" not in serialized
    assert "stderr" not in serialized
    assert len(serialized) < 16384


def test_poll_delay_is_idle_bounded_and_recovers() -> None:
    assert poll_delay(2.0, 0) == 2.0
    assert poll_delay(2.0, 1) == 4.0
    assert poll_delay(2.0, 1000) == 30.0
    assert poll_delay(2.0, 0) == 2.0
    with pytest.raises(ValueError):
        poll_delay(0, 0)
    with pytest.raises(ValueError):
        poll_delay(1, -1)
