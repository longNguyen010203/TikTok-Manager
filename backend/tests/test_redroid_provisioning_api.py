"""API tests for managed Redroid provisioning and idempotency."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import init_db
from app.routers.redroid_provisionings import get_redroid_provisioning_service
from app.services.redroid_provisioning import RedroidProvisioningService
from app.services.redroid_provisioning_adapter import (
    OccupiedResources,
    ProvisioningAllocation,
    ProvisioningAdapterError,
    ProvisioningConflictError,
    ProvisioningVerificationError,
)
from app.services.redroid_provisioning_config import RedroidProvisioningSettings
from tests.app_factory import create_test_app


class ApiFakeAdapter:
    def __init__(self, *, fail_at: str | None = None, blocking: bool = False) -> None:
        self.fail_at = fail_at
        self.calls: list[str] = []
        self.blocking = blocking
        self.preflight_entered = Event()
        self.release_preflight = Event()

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if self.fail_at == name:
            if name == "network":
                raise ProvisioningConflictError("SECRET docker conflict output")
            if name == "inspect":
                raise ProvisioningVerificationError("SECRET inspect output")
            if name == "preflight":
                raise ProvisioningAdapterError("SECRET host output")
            raise RuntimeError("SECRET unexpected output")

    def preflight(self) -> None:
        self._call("preflight")
        self.preflight_entered.set()
        if self.blocking:
            assert self.release_preflight.wait(timeout=10)

    def occupied_resources(self) -> OccupiedResources:
        return OccupiedResources(frozenset(), frozenset(), frozenset(), frozenset())

    def port_is_available(self, port: int) -> bool: return True
    def create_owned_data_directory(self, allocation: ProvisioningAllocation) -> bool:
        self._call("data"); return True
    def create_network(self, allocation: ProvisioningAllocation) -> str:
        self._call("network"); return "network-id"
    def verify_network(self, allocation: ProvisioningAllocation, network_id: str) -> None:
        self._call("network_inspect")
    def create_container(self, allocation: ProvisioningAllocation) -> str:
        self._call("container"); return "container-id"
    def verify_container(self, allocation: ProvisioningAllocation, container_id: str) -> None:
        self._call("inspect")
    def owned_container_id(self, allocation: ProvisioningAllocation) -> str | None: return None
    def owned_network_id(self, allocation: ProvisioningAllocation) -> str | None: return None
    def remove_owned_container(self, allocation: ProvisioningAllocation, container_id: str) -> bool:
        self.calls.append("remove_container"); return True
    def remove_owned_network(self, allocation: ProvisioningAllocation, network_id: str) -> bool:
        self.calls.append("remove_network"); return True
    def remove_owned_data_directory(self, allocation: ProvisioningAllocation) -> bool:
        self.calls.append("remove_data"); return True


@pytest.fixture
def api_context(tmp_path: Path):
    database_url = URL.create("sqlite", database=str(tmp_path / "api.db"))
    engine = create_engine(database_url, connect_args={"check_same_thread": False, "timeout": 10})
    init_db(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    root = tmp_path / "redroid-data"; root.mkdir()
    settings = RedroidProvisioningSettings(
        installation_id="api-test",
        image_reference="redroid/redroid@sha256:" + "a" * 64,
        data_root=root,
    )
    app = create_test_app()
    yield app, factory, settings
    engine.dispose()


def client_for(api_context, adapter: ApiFakeAdapter):
    app, factory, settings = api_context
    service = RedroidProvisioningService(factory, adapter, settings)
    app.dependency_overrides[get_redroid_provisioning_service] = lambda: service
    return TestClient(app), service


def payload() -> dict[str, object]:
    return {"name": "Redroid Device 03", "notes": None, "profile": "android-12-redroid"}


def test_success_and_get_status(api_context) -> None:
    client, _ = client_for(api_context, ApiFakeAdapter())
    response = client.post("/redroid-provisionings", headers={"Idempotency-Key": "success-key"}, json=payload())
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "completed"
    assert body["container_name"] == "redroid-device-01"
    assert body["adb_serial"] == "localhost:5555"
    assert body["device_id"] is not None and body["runtime_id"] is not None
    status_response = client.get(f"/redroid-provisionings/{body['provisioning_id']}")
    assert status_response.status_code == 200
    assert status_response.json() == body


def test_missing_and_invalid_idempotency_key(api_context) -> None:
    client, _ = client_for(api_context, ApiFakeAdapter())
    assert client.post("/redroid-provisionings", json=payload()).status_code == 422
    assert client.post("/redroid-provisionings", headers={"Idempotency-Key": "bad key"}, json=payload()).status_code == 422


def test_same_key_same_payload_reuses_completed_attempt(api_context) -> None:
    adapter = ApiFakeAdapter(); client, _ = client_for(api_context, adapter)
    first = client.post("/redroid-provisionings", headers={"Idempotency-Key": "same"}, json=payload())
    calls = list(adapter.calls)
    second = client.post("/redroid-provisionings", headers={"Idempotency-Key": "same"}, json=payload())
    assert second.status_code == 201
    assert second.json()["provisioning_id"] == first.json()["provisioning_id"]
    assert adapter.calls == calls


def test_same_key_different_payload_is_conflict(api_context) -> None:
    client, _ = client_for(api_context, ApiFakeAdapter())
    assert client.post("/redroid-provisionings", headers={"Idempotency-Key": "same"}, json=payload()).status_code == 201
    changed = payload(); changed["name"] = "Different"
    assert client.post("/redroid-provisionings", headers={"Idempotency-Key": "same"}, json=changed).status_code == 409


@pytest.mark.parametrize(
    ("stage", "expected_status"),
    [("network", 409), ("preflight", 503), ("container", 500)],
)
def test_failure_mapping_and_sanitization(api_context, stage, expected_status) -> None:
    client, _ = client_for(api_context, ApiFakeAdapter(fail_at=stage))
    response = client.post("/redroid-provisionings", headers={"Idempotency-Key": f"fail-{stage}"}, json=payload())
    assert response.status_code == expected_status
    assert "provisioning_id" in response.json()["detail"]
    assert "SECRET" not in response.text


def test_unknown_status_is_404(api_context) -> None:
    client, _ = client_for(api_context, ApiFakeAdapter())
    assert client.get("/redroid-provisionings/unknown").status_code == 404


def test_concurrent_duplicate_executes_external_path_once(api_context) -> None:
    adapter = ApiFakeAdapter(blocking=True)
    client, _ = client_for(api_context, adapter)
    headers = {"Idempotency-Key": "concurrent"}
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(client.post, "/redroid-provisionings", headers=headers, json=payload())
        assert adapter.preflight_entered.wait(timeout=10)
        second = executor.submit(client.post, "/redroid-provisionings", headers=headers, json=payload())
        second_response = second.result(timeout=10)
        adapter.release_preflight.set()
        first_response = first.result(timeout=10)
    assert {first_response.status_code, second_response.status_code} == {201, 202}
    assert first_response.json()["provisioning_id"] == second_response.json()["provisioning_id"]
    assert adapter.calls.count("data") == 1
    assert adapter.calls.count("network") == 1
    assert adapter.calls.count("container") == 1
