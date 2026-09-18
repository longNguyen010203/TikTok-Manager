"""API tests for Runtime CRUD and Account assignment."""

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
def runtime_api(tmp_path: Path) -> Iterator[TestClient]:
    database_url = URL.create(
        drivername="sqlite", database=str(tmp_path / "runtime-api.db")
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


def create_device(client: TestClient, index: int = 1) -> dict[str, Any]:
    response = client.post(
        "/devices",
        json={
            "name": f"Runtime Host {index}",
            "device_type": "virtual",
            "platform": "android",
            "os_version": "15",
            "status": "online",
        },
    )
    assert response.status_code == 201
    return response.json()


def runtime_payload(device_id: int, index: int = 1) -> dict[str, Any]:
    return {
        "device_id": device_id,
        "name": f"Runtime {index}",
        "runtime_type": "emulator",
        "status": "running",
        "last_seen_at": "2026-09-18T10:00:00Z",
    }


def create_runtime(
    client: TestClient, device_id: int, index: int = 1
) -> dict[str, Any]:
    response = client.post("/runtimes", json=runtime_payload(device_id, index))
    assert response.status_code == 201
    return response.json()


def account_payload(index: int = 1) -> dict[str, Any]:
    return {
        "name": f"Runtime Account {index}",
        "username": f"runtime-account-{index}",
        "platform": "tiktok",
        "status": "active",
    }


def test_runtime_crud(runtime_api: TestClient) -> None:
    first_device = create_device(runtime_api, 1)
    second_device = create_device(runtime_api, 2)
    created = create_runtime(runtime_api, first_device["id"])
    runtime_id = created["id"]
    assert created["device_id"] == first_device["id"]
    assert created["last_seen_at"]

    get_response = runtime_api.get(f"/runtimes/{runtime_id}")
    assert get_response.status_code == 200
    assert get_response.json() == created

    update_response = runtime_api.patch(
        f"/runtimes/{runtime_id}",
        json={
            "device_id": second_device["id"],
            "name": "Updated Runtime",
            "last_seen_at": None,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["device_id"] == second_device["id"]
    assert update_response.json()["name"] == "Updated Runtime"
    assert update_response.json()["last_seen_at"] is None

    delete_response = runtime_api.delete(f"/runtimes/{runtime_id}")
    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert runtime_api.get(f"/runtimes/{runtime_id}").status_code == 404


def test_list_runtimes_supports_pagination(runtime_api: TestClient) -> None:
    device = create_device(runtime_api)
    created = [
        create_runtime(runtime_api, device["id"], index) for index in range(1, 6)
    ]

    response = runtime_api.get("/runtimes?page=2&page_size=2")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert [item["id"] for item in body["items"]] == [
        created[2]["id"],
        created[3]["id"],
    ]


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_missing_runtime_returns_404(runtime_api: TestClient, method: str) -> None:
    payload = {"name": "Updated"} if method == "patch" else None
    response = runtime_api.request(method, "/runtimes/999", json=payload)

    assert response.status_code == 404
    assert response.json() == {"detail": "Runtime not found"}


def test_runtime_validates_device_id(runtime_api: TestClient) -> None:
    missing_device = runtime_api.post("/runtimes", json=runtime_payload(999))
    assert missing_device.status_code == 404
    assert missing_device.json() == {"detail": "Device not found"}

    invalid_device = runtime_api.post("/runtimes", json=runtime_payload(0))
    assert invalid_device.status_code == 422

    device = create_device(runtime_api)
    runtime = create_runtime(runtime_api, device["id"])
    missing_update_device = runtime_api.patch(
        f"/runtimes/{runtime['id']}", json={"device_id": 999}
    )
    assert missing_update_device.status_code == 404
    assert missing_update_device.json() == {"detail": "Device not found"}


def test_account_runtime_assignment_is_validated(runtime_api: TestClient) -> None:
    invalid_create = runtime_api.post(
        "/accounts", json=account_payload() | {"runtime_id": 999}
    )
    assert invalid_create.status_code == 404
    assert invalid_create.json() == {"detail": "Runtime not found"}

    account = runtime_api.post("/accounts", json=account_payload()).json()
    invalid_update = runtime_api.patch(
        f"/accounts/{account['id']}", json={"runtime_id": 999}
    )
    assert invalid_update.status_code == 404
    assert invalid_update.json() == {"detail": "Runtime not found"}

    invalid_id = runtime_api.patch(
        f"/accounts/{account['id']}", json={"runtime_id": 0}
    )
    assert invalid_id.status_code == 422


def test_account_can_be_assigned_and_unassigned(runtime_api: TestClient) -> None:
    device = create_device(runtime_api)
    runtime = create_runtime(runtime_api, device["id"])
    account = runtime_api.post(
        "/accounts", json=account_payload() | {"runtime_id": runtime["id"]}
    )
    assert account.status_code == 201
    assert account.json()["runtime_id"] == runtime["id"]

    unassigned = runtime_api.patch(
        f"/accounts/{account.json()['id']}", json={"runtime_id": None}
    )
    assert unassigned.status_code == 200
    assert unassigned.json()["runtime_id"] is None


def test_delete_runtime_preserves_and_unassigns_account(
    runtime_api: TestClient,
) -> None:
    device = create_device(runtime_api)
    runtime = create_runtime(runtime_api, device["id"])
    account = runtime_api.post(
        "/accounts", json=account_payload() | {"runtime_id": runtime["id"]}
    ).json()

    delete_response = runtime_api.delete(f"/runtimes/{runtime['id']}")

    assert delete_response.status_code == 204
    account_response = runtime_api.get(f"/accounts/{account['id']}")
    assert account_response.status_code == 200
    assert account_response.json()["runtime_id"] is None
