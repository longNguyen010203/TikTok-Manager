"""API tests for Device CRUD operations."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, init_db
from app.main import create_app
from app.models import Account, Device, Runtime


@dataclass(frozen=True)
class DeviceApiEnvironment:
    client: TestClient
    engine: Engine


@pytest.fixture
def device_api(tmp_path: Path) -> Iterator[DeviceApiEnvironment]:
    database_url = URL.create(
        drivername="sqlite", database=str(tmp_path / "device-api.db")
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
            yield DeviceApiEnvironment(client=client, engine=test_engine)
    finally:
        application.dependency_overrides.clear()
        test_engine.dispose()


def device_payload(index: int) -> dict[str, str]:
    return {
        "name": f"Device {index}",
        "device_type": "physical",
        "platform": "android",
        "os_version": "15",
        "status": "online",
        "notes": f"Device notes {index}",
    }


def create_device(environment: DeviceApiEnvironment, index: int) -> dict[str, object]:
    response = environment.client.post("/devices", json=device_payload(index))
    assert response.status_code == 201
    return response.json()


def test_device_crud(device_api: DeviceApiEnvironment) -> None:
    created = create_device(device_api, 1)
    device_id = created["id"]
    assert created["name"] == "Device 1"
    assert created["created_at"]
    assert created["updated_at"]

    get_response = device_api.client.get(f"/devices/{device_id}")
    assert get_response.status_code == 200
    assert get_response.json() == created

    update_response = device_api.client.patch(
        f"/devices/{device_id}",
        json={"name": "Updated Device", "notes": None},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Device"
    assert update_response.json()["notes"] is None

    delete_response = device_api.client.delete(f"/devices/{device_id}")
    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert device_api.client.get(f"/devices/{device_id}").status_code == 404


def test_list_devices_supports_pagination(device_api: DeviceApiEnvironment) -> None:
    created = [create_device(device_api, index) for index in range(1, 6)]

    response = device_api.client.get("/devices?page=2&page_size=2")

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
def test_missing_device_returns_404(
    device_api: DeviceApiEnvironment, method: str
) -> None:
    payload = {"name": "Updated"} if method == "patch" else None
    response = device_api.client.request(method, "/devices/999", json=payload)

    assert response.status_code == 404
    assert response.json() == {"detail": "Device not found"}


def test_device_payloads_are_validated(device_api: DeviceApiEnvironment) -> None:
    invalid_create = device_api.client.post(
        "/devices", json=device_payload(1) | {"name": "   "}
    )
    assert invalid_create.status_code == 422

    created = create_device(device_api, 1)
    invalid_patch = device_api.client.patch(
        f"/devices/{created['id']}", json={"status": None}
    )
    assert invalid_patch.status_code == 422

    invalid_page = device_api.client.get("/devices?page_size=101")
    assert invalid_page.status_code == 422


def test_delete_device_cascades_runtimes_and_preserves_accounts(
    device_api: DeviceApiEnvironment,
) -> None:
    with Session(device_api.engine) as session:
        device = Device(
            name="Device with Runtime",
            device_type="virtual",
            platform="android",
            os_version="14",
            status="online",
        )
        runtime = Runtime(name="Runtime 1", runtime_type="emulator", status="running")
        device.runtimes.append(runtime)
        account = Account(
            name="Assigned Account",
            username="assigned-device-delete",
            platform="tiktok",
            status="active",
            runtime=runtime,
        )
        session.add_all([device, account])
        session.commit()
        device_id = device.id
        runtime_id = runtime.id
        account_id = account.id

    response = device_api.client.delete(f"/devices/{device_id}")

    assert response.status_code == 204
    with Session(device_api.engine) as session:
        preserved_account = session.get(Account, account_id)
        assert session.get(Device, device_id) is None
        assert session.get(Runtime, runtime_id) is None
        assert preserved_account is not None
        assert preserved_account.runtime_id is None
