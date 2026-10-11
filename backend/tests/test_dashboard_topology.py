"""API tests for the normalized read-only Dashboard topology graph."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, init_db
from app.routers.accounts import get_account_secret_provider
from app.services.account_secrets import AccountSecretProvider
from app.services.network_credentials import MasterKeyManager
from tests.app_factory import create_test_app


@pytest.fixture
def topology_api(tmp_path: Path) -> Iterator[tuple[TestClient, Engine]]:
    database_url = URL.create(
        drivername="sqlite", database=str(tmp_path / "topology-api.db")
    )
    test_engine = create_engine(
        database_url, connect_args={"check_same_thread": False}
    )
    testing_session = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )
    init_db(test_engine)
    application: FastAPI = create_test_app()
    secret_provider = AccountSecretProvider(
        MasterKeyManager(tmp_path / "config" / "credentials.key")
    )

    def override_get_db() -> Iterator[Session]:
        with testing_session() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_account_secret_provider] = lambda: secret_provider
    try:
        with TestClient(application) as client:
            yield client, test_engine
    finally:
        application.dependency_overrides.clear()
        test_engine.dispose()


def _create_device(client: TestClient, name: str) -> dict[str, Any]:
    response = client.post(
        "/devices",
        json={
            "name": name,
            "device_type": "virtual",
            "platform": "android",
            "os_version": "15",
            "status": "online",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_runtime(
    client: TestClient, device_id: int, name: str
) -> dict[str, Any]:
    response = client.post(
        "/runtimes",
        json={
            "device_id": device_id,
            "name": name,
            "runtime_type": "redroid",
            "status": "running",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_account(
    client: TestClient,
    name: str,
    *,
    runtime_id: int | None = None,
    registration_state: str = "pending",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "display_name": name,
        "status": "active",
        "registration_state": registration_state,
    }
    if runtime_id is not None:
        payload["runtime_id"] = runtime_id
    response = client.post("/accounts", json=payload)
    assert response.status_code == 201
    return response.json()


def test_topology_returns_complete_normalized_deterministic_graph(
    topology_api: tuple[TestClient, Engine],
) -> None:
    client, engine = topology_api
    hosting_device = _create_device(client, "Redroid Device 07")
    empty_device = _create_device(client, "Empty Device")
    assigned_runtime = _create_runtime(
        client, hosting_device["id"], "redroid-runtime-31"
    )
    empty_runtime = _create_runtime(
        client, hosting_device["id"], "redroid-runtime-empty"
    )
    ready_account = _create_account(
        client, "Manual Test 01", runtime_id=assigned_runtime["id"]
    )
    attention_account = _create_account(
        client, "Needs Attention", runtime_id=assigned_runtime["id"]
    )
    unassigned_account = _create_account(client, "Unassigned Account")
    archived_account = _create_account(
        client, "Archived Account", runtime_id=empty_runtime["id"]
    )

    completed = client.post(
        f"/accounts/{ready_account['id']}/registration/complete",
        json={"username": "@ReadyCreator"},
    )
    assert completed.status_code == 200
    failed = client.post(
        f"/accounts/{attention_account['id']}/registration/fail",
        json={"reason": "Manual verification failed"},
    )
    assert failed.status_code == 200
    secret = "topology-must-never-return-this-secret"
    assert client.put(
        f"/accounts/{ready_account['id']}/secrets/account_password",
        json={"value": secret},
    ).status_code == 200
    assert client.delete(f"/accounts/{archived_account['id']}").status_code == 204

    selects: list[str] = []

    def count_selects(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        response = client.get("/dashboard/topology")
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)

    assert response.status_code == 200
    assert secret not in response.text
    body = response.json()
    assert body["generated_at"]
    assert body["summary"] == {
        "devices": 2,
        "runtimes": 2,
        "accounts": 3,
        "ready_accounts": 1,
        "not_ready_accounts": 2,
        "attention_accounts": 1,
    }
    assert len(selects) == 4

    expected_node_ids = [
        f"device:{hosting_device['id']}",
        f"device:{empty_device['id']}",
        f"runtime:{assigned_runtime['id']}",
        f"runtime:{empty_runtime['id']}",
        f"account:{ready_account['id']}",
        f"account:{attention_account['id']}",
        f"account:{unassigned_account['id']}",
    ]
    actual_node_ids = [node["id"] for node in body["nodes"]]
    assert actual_node_ids == expected_node_ids
    assert len(expected_node_ids) == len(set(expected_node_ids))
    assert all(
        node["type"] in {"device", "runtime", "account"}
        for node in body["nodes"]
    )
    assert f"account:{archived_account['id']}" not in actual_node_ids

    nodes = {node["id"]: node for node in body["nodes"]}
    assert nodes[f"device:{hosting_device['id']}"]["metadata"]["runtime_count"] == 2
    assert nodes[f"device:{empty_device['id']}"]["metadata"]["runtime_count"] == 0
    assert (
        nodes[f"runtime:{assigned_runtime['id']}"]["metadata"][
            "assigned_account_count"
        ]
        == 2
    )
    assert (
        nodes[f"runtime:{empty_runtime['id']}"]["metadata"][
            "assigned_account_count"
        ]
        == 0
    )
    ready_metadata = nodes[f"account:{ready_account['id']}"]["metadata"]
    assert ready_metadata["registration_ready"] is True
    assert ready_metadata["username"] == "readycreator"
    assert ready_metadata["secret_present"] is True
    assert "secret_types" not in ready_metadata
    unassigned_metadata = nodes[f"account:{unassigned_account['id']}"]["metadata"]
    assert unassigned_metadata["runtime_id"] is None
    assert unassigned_metadata["device_id"] is None
    assert unassigned_metadata["registration_ready"] is False

    expected_edges = [
        {
            "id": f"device:{hosting_device['id']}->runtime:{assigned_runtime['id']}",
            "source": f"device:{hosting_device['id']}",
            "target": f"runtime:{assigned_runtime['id']}",
            "type": "hosts",
        },
        {
            "id": f"device:{hosting_device['id']}->runtime:{empty_runtime['id']}",
            "source": f"device:{hosting_device['id']}",
            "target": f"runtime:{empty_runtime['id']}",
            "type": "hosts",
        },
        {
            "id": f"runtime:{assigned_runtime['id']}->account:{ready_account['id']}",
            "source": f"runtime:{assigned_runtime['id']}",
            "target": f"account:{ready_account['id']}",
            "type": "assigned",
        },
        {
            "id": f"runtime:{assigned_runtime['id']}->account:{attention_account['id']}",
            "source": f"runtime:{assigned_runtime['id']}",
            "target": f"account:{attention_account['id']}",
            "type": "assigned",
        },
    ]
    assert body["edges"] == expected_edges
    assert len(body["edges"]) == len({edge["id"] for edge in body["edges"]})

    repeated = client.get("/dashboard/topology?page=1&page_size=1")
    assert repeated.status_code == 200
    assert repeated.json()["nodes"] == body["nodes"]
    assert repeated.json()["edges"] == body["edges"]
    assert repeated.json()["summary"] == body["summary"]


def test_topology_reflects_assignment_changes_immediately(
    topology_api: tuple[TestClient, Engine],
) -> None:
    client, _engine = topology_api
    device = _create_device(client, "Assignment Device")
    runtime = _create_runtime(client, device["id"], "Assignment Runtime")
    account = _create_account(client, "Moving Account")
    account_node_id = f"account:{account['id']}"
    assignment_edge_id = f"runtime:{runtime['id']}->account:{account['id']}"

    initial = client.get("/dashboard/topology").json()
    initial_node = next(node for node in initial["nodes"] if node["id"] == account_node_id)
    assert initial_node["metadata"]["runtime_id"] is None
    assert assignment_edge_id not in {edge["id"] for edge in initial["edges"]}

    assigned = client.put(
        f"/accounts/{account['id']}/runtime", json={"runtime_id": runtime["id"]}
    )
    assert assigned.status_code == 200
    assert client.post(
        f"/accounts/{account['id']}/registration/complete", json={}
    ).status_code == 200

    after_assignment = client.get("/dashboard/topology").json()
    assigned_node = next(
        node for node in after_assignment["nodes"] if node["id"] == account_node_id
    )
    assert assigned_node["metadata"]["runtime_id"] == runtime["id"]
    assert assigned_node["metadata"]["device_id"] == device["id"]
    assert assigned_node["metadata"]["registration_ready"] is True
    assert assignment_edge_id in {edge["id"] for edge in after_assignment["edges"]}

    unassigned = client.delete(f"/accounts/{account['id']}/runtime")
    assert unassigned.status_code == 200
    after_unassignment = client.get("/dashboard/topology").json()
    unassigned_node = next(
        node for node in after_unassignment["nodes"] if node["id"] == account_node_id
    )
    assert unassigned_node["metadata"]["runtime_id"] is None
    assert unassigned_node["metadata"]["device_id"] is None
    assert unassigned_node["metadata"]["registration_ready"] is False
    assert assignment_edge_id not in {
        edge["id"] for edge in after_unassignment["edges"]
    }
