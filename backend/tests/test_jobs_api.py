"""API tests for Job CRUD, filtering, and target validation."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, init_db
from app.main import create_app


@pytest.fixture
def job_api(tmp_path: Path) -> Iterator[TestClient]:
    database_url = URL.create(
        drivername="sqlite", database=str(tmp_path / "job-api.db")
    )
    test_engine = create_engine(
        database_url, connect_args={"check_same_thread": False}
    )
    testing_session = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )
    init_db(test_engine)
    application = create_app()

    def override_get_db() -> Iterator[Session]:
        with testing_session() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()
        test_engine.dispose()


def create_targets(
    client: TestClient, index: int = 1
) -> tuple[dict[str, Any], dict[str, Any]]:
    device_response = client.post(
        "/devices",
        json={
            "name": f"Job Device {index}",
            "device_type": "virtual",
            "platform": "android",
            "os_version": "15",
            "status": "online",
        },
    )
    assert device_response.status_code == 201
    device = device_response.json()

    runtime_response = client.post(
        "/runtimes",
        json={
            "device_id": device["id"],
            "name": f"Job Runtime {index}",
            "runtime_type": "emulator",
            "status": "running",
        },
    )
    assert runtime_response.status_code == 201
    runtime = runtime_response.json()

    account_response = client.post(
        "/accounts",
        json={
            "name": f"Job Account {index}",
            "username": f"job-account-{index}",
            "platform": "tiktok",
            "status": "active",
            "runtime_id": runtime["id"],
        },
    )
    assert account_response.status_code == 201
    return account_response.json(), runtime


def job_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "job_type": "publish_video",
        "payload": {"video_id": 42},
    }
    return payload | overrides


def test_job_crud(job_api: TestClient) -> None:
    account, runtime = create_targets(job_api)
    create_response = job_api.post(
        "/jobs",
        json=job_payload(
            account_id=account["id"],
            runtime_id=runtime["id"],
            max_attempts=5,
            scheduled_at="2026-09-19T10:00:00Z",
        ),
    )
    assert create_response.status_code == 201
    created = create_response.json()
    job_id = created["id"]
    assert created["job_type"] == "publish_video"
    assert created["status"] == "pending"
    assert created["account_id"] == account["id"]
    assert created["runtime_id"] == runtime["id"]
    assert created["payload"] == {"video_id": 42}
    assert created["result"] is None
    assert created["attempt_count"] == 0
    assert created["max_attempts"] == 5
    assert created["scheduled_at"]
    assert created["created_at"]
    assert created["updated_at"]

    get_response = job_api.get(f"/jobs/{job_id}")
    assert get_response.status_code == 200
    assert get_response.json() == created

    update_response = job_api.patch(
        f"/jobs/{job_id}",
        json={
            "job_type": "publish_video_updated",
            "account_id": None,
            "payload": None,
            "max_attempts": 6,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["job_type"] == "publish_video_updated"
    assert updated["status"] == "pending"
    assert updated["account_id"] is None
    assert updated["runtime_id"] == runtime["id"]
    assert updated["payload"] is None
    assert updated["max_attempts"] == 6

    delete_response = job_api.delete(f"/jobs/{job_id}")
    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert job_api.get(f"/jobs/{job_id}").status_code == 404


def test_list_jobs_supports_pagination_and_exact_filters(job_api: TestClient) -> None:
    first_account, first_runtime = create_targets(job_api, 1)
    second_account, second_runtime = create_targets(job_api, 2)
    definitions = [
        job_payload(
            job_type="sync_analytics",
            status="pending",
            account_id=first_account["id"],
            runtime_id=first_runtime["id"],
        ),
        job_payload(
            job_type="sync_analytics",
            status="running",
            account_id=second_account["id"],
            runtime_id=second_runtime["id"],
        ),
        job_payload(
            job_type="publish_video",
            status="failed",
            account_id=first_account["id"],
            runtime_id=second_runtime["id"],
        ),
        job_payload(job_type="cleanup", status="pending"),
    ]
    created = []
    for definition in definitions:
        response = job_api.post("/jobs", json=definition)
        assert response.status_code == 201
        created.append(response.json())

    page_response = job_api.get("/jobs?page=2&page_size=2")
    assert page_response.status_code == 200
    page = page_response.json()
    assert page["total"] == 4
    assert page["page"] == 2
    assert page["page_size"] == 2
    assert [item["id"] for item in page["items"]] == [
        created[2]["id"],
        created[3]["id"],
    ]

    filter_expectations = [
        ("status=pending", 2),
        ("job_type=sync_analytics", 2),
        (f"account_id={first_account['id']}", 2),
        (f"runtime_id={second_runtime['id']}", 2),
    ]
    for query, expected_total in filter_expectations:
        response = job_api.get(f"/jobs?{query}")
        assert response.status_code == 200
        assert response.json()["total"] == expected_total

    combined_response = job_api.get(
        "/jobs?status=failed&job_type=publish_video"
        f"&account_id={first_account['id']}&runtime_id={second_runtime['id']}"
    )
    assert combined_response.status_code == 200
    combined = combined_response.json()
    assert combined["total"] == 1
    assert combined["items"][0]["id"] == created[2]["id"]

    empty_response = job_api.get("/jobs?account_id=999")
    assert empty_response.status_code == 200
    assert empty_response.json()["items"] == []
    assert empty_response.json()["total"] == 0


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_missing_job_returns_404(
    job_api: TestClient, method: str
) -> None:
    payload = {"status": "running"} if method == "patch" else None
    response = job_api.request(method, "/jobs/999", json=payload)

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}


def test_job_validates_account_and_runtime_targets(job_api: TestClient) -> None:
    missing_account = job_api.post(
        "/jobs", json=job_payload(account_id=999)
    )
    assert missing_account.status_code == 404
    assert missing_account.json() == {"detail": "Account not found"}

    missing_runtime = job_api.post(
        "/jobs", json=job_payload(runtime_id=999)
    )
    assert missing_runtime.status_code == 404
    assert missing_runtime.json() == {"detail": "Runtime not found"}

    job = job_api.post("/jobs", json=job_payload()).json()
    missing_account_update = job_api.patch(
        f"/jobs/{job['id']}", json={"account_id": 999}
    )
    assert missing_account_update.status_code == 404
    assert missing_account_update.json() == {"detail": "Account not found"}

    missing_runtime_update = job_api.patch(
        f"/jobs/{job['id']}", json={"runtime_id": 999}
    )
    assert missing_runtime_update.status_code == 404
    assert missing_runtime_update.json() == {"detail": "Runtime not found"}


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/jobs", {}),
        ("post", "/jobs", {"job_type": "", "status": "pending"}),
        ("post", "/jobs", {"job_type": "test", "status": "unknown"}),
        ("post", "/jobs", {"job_type": "test", "account_id": 0}),
        ("post", "/jobs", {"job_type": "test", "runtime_id": -1}),
        ("post", "/jobs", {"job_type": "test", "attempt_count": -1}),
        ("post", "/jobs", {"job_type": "test", "max_attempts": 0}),
        ("post", "/jobs", {"job_type": "test", "unknown": "value"}),
        ("get", "/jobs?page=0", None),
        ("get", "/jobs?page_size=101", None),
        ("get", "/jobs?status=unknown", None),
        ("get", "/jobs?job_type=", None),
        ("get", "/jobs?account_id=0", None),
        ("get", "/jobs?runtime_id=-1", None),
        ("get", "/jobs/0", None),
    ],
)
def test_job_inputs_return_422(
    job_api: TestClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    response = job_api.request(method, path, json=body)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "update",
    [
        {"job_type": None},
        {"status": None},
        {"attempt_count": None},
        {"max_attempts": None},
        {"unknown": "value"},
    ],
)
def test_job_patch_rejects_invalid_fields(
    job_api: TestClient, update: dict[str, Any]
) -> None:
    job = job_api.post("/jobs", json=job_payload()).json()
    response = job_api.patch(f"/jobs/{job['id']}", json=update)
    assert response.status_code == 422


def test_claim_selects_only_due_pending_jobs_in_id_order(
    job_api: TestClient,
) -> None:
    future = job_api.post(
        "/jobs",
        json=job_payload(
            job_type="future", scheduled_at="2999-01-01T00:00:00Z"
        ),
    ).json()
    first_eligible = job_api.post(
        "/jobs",
        json=job_payload(job_type="immediate", attempt_count=1),
    ).json()
    second_eligible = job_api.post(
        "/jobs",
        json=job_payload(
            job_type="overdue", scheduled_at="2000-01-01T00:00:00Z"
        ),
    ).json()
    job_api.post(
        "/jobs", json=job_payload(job_type="terminal", status="failed")
    )

    first_claim = job_api.post("/jobs/claim")
    assert first_claim.status_code == 200
    first_claimed = first_claim.json()
    assert first_claimed["id"] == first_eligible["id"]
    assert first_claimed["status"] == "running"
    assert first_claimed["started_at"] is not None
    assert first_claimed["attempt_count"] == 2

    second_claim = job_api.post("/jobs/claim")
    assert second_claim.status_code == 200
    second_claimed = second_claim.json()
    assert second_claimed["id"] == second_eligible["id"]
    assert second_claimed["status"] == "running"
    assert second_claimed["started_at"] is not None
    assert second_claimed["attempt_count"] == 1

    no_claim = job_api.post("/jobs/claim")
    assert no_claim.status_code == 204
    assert no_claim.content == b""

    future_response = job_api.get(f"/jobs/{future['id']}")
    assert future_response.json()["status"] == "pending"
    assert future_response.json()["attempt_count"] == 0
    assert future_response.json()["started_at"] is None


def test_running_job_can_succeed_with_result(job_api: TestClient) -> None:
    job = job_api.post("/jobs", json=job_payload()).json()
    claimed = job_api.post("/jobs/claim").json()
    assert claimed["id"] == job["id"]

    response = job_api.post(
        f"/jobs/{job['id']}/succeed",
        json={"result": {"post_id": "post-123"}},
    )

    assert response.status_code == 200
    succeeded = response.json()
    assert succeeded["status"] == "succeeded"
    assert succeeded["result"] == {"post_id": "post-123"}
    assert succeeded["completed_at"] is not None
    assert succeeded["attempt_count"] == 1


def test_running_job_can_fail_with_error_message(job_api: TestClient) -> None:
    job = job_api.post("/jobs", json=job_payload()).json()
    job_api.post("/jobs/claim")

    response = job_api.post(
        f"/jobs/{job['id']}/fail", json={"error_message": "Upload failed"}
    )

    assert response.status_code == 200
    failed = response.json()
    assert failed["status"] == "failed"
    assert failed["error_message"] == "Upload failed"
    assert failed["completed_at"] is not None


@pytest.mark.parametrize("initial_status", ["pending", "running", "retrying"])
def test_eligible_job_can_be_cancelled(
    job_api: TestClient, initial_status: str
) -> None:
    job = job_api.post(
        "/jobs", json=job_payload(status=initial_status)
    ).json()

    response = job_api.post(f"/jobs/{job['id']}/cancel")

    assert response.status_code == 200
    cancelled = response.json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["completed_at"] is not None


@pytest.mark.parametrize(
    ("initial_status", "action", "body", "target_status"),
    [
        ("pending", "succeed", {"result": {}}, "succeeded"),
        ("pending", "fail", {"error_message": "error"}, "failed"),
        ("succeeded", "succeed", {"result": {}}, "succeeded"),
        ("succeeded", "fail", {"error_message": "error"}, "failed"),
        ("succeeded", "cancel", None, "cancelled"),
        ("failed", "succeed", {"result": {}}, "succeeded"),
        ("failed", "cancel", None, "cancelled"),
        ("cancelled", "cancel", None, "cancelled"),
    ],
)
def test_invalid_lifecycle_transitions_return_409(
    job_api: TestClient,
    initial_status: str,
    action: str,
    body: dict[str, Any] | None,
    target_status: str,
) -> None:
    job = job_api.post(
        "/jobs", json=job_payload(status=initial_status)
    ).json()

    response = job_api.post(f"/jobs/{job['id']}/{action}", json=body)

    assert response.status_code == 409
    assert response.json() == {
        "detail": f"Cannot transition job from {initial_status} to {target_status}"
    }


def test_patch_cannot_bypass_lifecycle_actions(job_api: TestClient) -> None:
    job = job_api.post("/jobs", json=job_payload()).json()

    response = job_api.patch(f"/jobs/{job['id']}", json={"status": "running"})

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Job status changes require a lifecycle action"
    }
    assert job_api.get(f"/jobs/{job['id']}").json()["status"] == "pending"


@pytest.mark.parametrize("action", ["succeed", "fail", "cancel", "retry"])
def test_lifecycle_action_for_missing_job_returns_404(
    job_api: TestClient, action: str
) -> None:
    body: dict[str, Any] = {}
    response = job_api.post(f"/jobs/999/{action}", json=body)
    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}


def test_lifecycle_payloads_forbid_unknown_fields(job_api: TestClient) -> None:
    job = job_api.post(
        "/jobs", json=job_payload(status="running")
    ).json()

    succeeded = job_api.post(
        f"/jobs/{job['id']}/succeed", json={"unknown": "value"}
    )
    failed = job_api.post(
        f"/jobs/{job['id']}/fail", json={"unknown": "value"}
    )

    assert succeeded.status_code == 422
    assert failed.status_code == 422


def test_failed_job_can_be_retried_without_consuming_attempt(
    job_api: TestClient,
) -> None:
    job = job_api.post(
        "/jobs",
        json=job_payload(
            max_attempts=3,
            result={"stale": True},
            scheduled_at="2000-01-01T00:00:00Z",
        ),
    ).json()
    claimed = job_api.post("/jobs/claim").json()
    assert claimed["id"] == job["id"]
    assert claimed["attempt_count"] == 1
    failed = job_api.post(
        f"/jobs/{job['id']}/fail", json={"error_message": "Temporary error"}
    ).json()
    assert failed["completed_at"] is not None

    response = job_api.post(f"/jobs/{job['id']}/retry")

    assert response.status_code == 200
    retried = response.json()
    assert retried["status"] == "pending"
    assert retried["attempt_count"] == 1
    assert retried["max_attempts"] == 3
    assert retried["scheduled_at"] is None
    assert retried["started_at"] is None
    assert retried["completed_at"] is None
    assert retried["result"] is None
    assert retried["error_message"] is None
    assert retried["payload"] == {"video_id": 42}

    claimed_again = job_api.post("/jobs/claim").json()
    assert claimed_again["id"] == job["id"]
    assert claimed_again["attempt_count"] == 2


def test_retry_can_be_scheduled_for_the_future(job_api: TestClient) -> None:
    job = job_api.post("/jobs", json=job_payload()).json()
    job_api.post("/jobs/claim")
    job_api.post(f"/jobs/{job['id']}/fail", json={})

    response = job_api.post(
        f"/jobs/{job['id']}/retry",
        json={"scheduled_at": "2999-01-01T00:00:00Z"},
    )

    assert response.status_code == 200
    retried = response.json()
    assert retried["status"] == "pending"
    assert retried["scheduled_at"].startswith("2999-01-01T00:00:00")
    assert retried["attempt_count"] == 1

    claim_response = job_api.post("/jobs/claim")
    assert claim_response.status_code == 204


def test_retry_is_blocked_when_max_attempts_is_reached(
    job_api: TestClient,
) -> None:
    job = job_api.post(
        "/jobs", json=job_payload(max_attempts=1)
    ).json()
    job_api.post("/jobs/claim")
    failed = job_api.post(
        f"/jobs/{job['id']}/fail", json={"error_message": "Permanent error"}
    ).json()

    response = job_api.post(f"/jobs/{job['id']}/retry")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Job has reached maximum attempts (1/1)"
    }
    unchanged = job_api.get(f"/jobs/{job['id']}").json()
    assert unchanged["status"] == "failed"
    assert unchanged["attempt_count"] == 1
    assert unchanged["error_message"] == "Permanent error"
    assert unchanged["completed_at"] == failed["completed_at"]


@pytest.mark.parametrize(
    "initial_status",
    ["pending", "running", "retrying", "succeeded", "cancelled"],
)
def test_retry_rejects_invalid_states(
    job_api: TestClient, initial_status: str
) -> None:
    job = job_api.post(
        "/jobs", json=job_payload(status=initial_status)
    ).json()

    response = job_api.post(f"/jobs/{job['id']}/retry")

    assert response.status_code == 409
    assert response.json() == {
        "detail": f"Cannot transition job from {initial_status} to retrying"
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"scheduled_at": "not-a-datetime"},
        {"unknown": "value"},
    ],
)
def test_retry_payload_is_validated(
    job_api: TestClient, payload: dict[str, Any]
) -> None:
    job = job_api.post(
        "/jobs", json=job_payload(status="failed")
    ).json()

    response = job_api.post(f"/jobs/{job['id']}/retry", json=payload)

    assert response.status_code == 422


def test_lifecycle_logs_preserve_failure_history_across_retry(
    job_api: TestClient,
) -> None:
    job = job_api.post(
        "/jobs", json=job_payload(result={"stale": True})
    ).json()
    job_api.post("/jobs/claim")
    job_api.post(
        f"/jobs/{job['id']}/fail",
        json={"error_message": "First attempt failed"},
    )
    retried = job_api.post(
        f"/jobs/{job['id']}/retry",
        json={"scheduled_at": "2000-01-01T00:00:00Z"},
    ).json()
    assert retried["error_message"] is None
    assert retried["result"] is None
    job_api.post("/jobs/claim")
    job_api.post(
        f"/jobs/{job['id']}/succeed",
        json={"result": {"post_id": "post-456"}},
    )

    response = job_api.get(f"/jobs/{job['id']}/logs")

    assert response.status_code == 200
    logs = response.json()
    assert [log["message"] for log in logs] == [
        "Job claimed",
        "Job failed",
        "Job retry scheduled",
        "Job claimed",
        "Job succeeded",
    ]
    assert [log["level"] for log in logs] == [
        "info",
        "error",
        "info",
        "info",
        "info",
    ]
    assert all(log["job_id"] == job["id"] for log in logs)
    assert all(log["created_at"] for log in logs)
    assert logs[0]["metadata"] == {"attempt_count": 1}
    assert logs[1]["metadata"] == {"error_message": "First attempt failed"}
    assert logs[2]["metadata"] == {
        "scheduled_at": "2000-01-01T00:00:00+00:00",
        "attempt_count": 1,
    }
    assert logs[3]["metadata"] == {"attempt_count": 2}
    assert logs[4]["metadata"] is None


def test_cancel_is_logged(job_api: TestClient) -> None:
    job = job_api.post("/jobs", json=job_payload()).json()

    cancel_response = job_api.post(f"/jobs/{job['id']}/cancel")
    logs_response = job_api.get(f"/jobs/{job['id']}/logs")

    assert cancel_response.status_code == 200
    assert logs_response.status_code == 200
    assert logs_response.json() == [
        {
            "id": 1,
            "job_id": job["id"],
            "level": "info",
            "message": "Job cancelled",
            "metadata": None,
            "created_at": logs_response.json()[0]["created_at"],
        }
    ]


def test_logs_for_missing_or_invalid_job_return_errors(job_api: TestClient) -> None:
    missing = job_api.get("/jobs/999/logs")
    invalid = job_api.get("/jobs/0/logs")

    assert missing.status_code == 404
    assert missing.json() == {"detail": "Job not found"}
    assert invalid.status_code == 422
