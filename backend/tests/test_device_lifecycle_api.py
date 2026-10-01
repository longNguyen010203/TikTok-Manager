"""API tests for Redroid-backed Device lifecycle operations."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, init_db
from app.main import create_app
from app.models import Device, Runtime
from app.routers.devices import get_redroid_runtime_adapter
from app.services.redroid_runtime import (
    RedroidAdbTimeoutError,
    RedroidBootTimeoutError,
    RedroidCommandError,
    RedroidRuntimeAdapter,
)


@dataclass(frozen=True)
class LifecycleApiEnvironment:
    client: TestClient
    engine: Engine
    adapter: MagicMock


@pytest.fixture
def lifecycle_api(tmp_path: Path) -> Iterator[LifecycleApiEnvironment]:
    database_url = URL.create(
        drivername="sqlite", database=str(tmp_path / "lifecycle-api.db")
    )
    test_engine = create_engine(
        database_url, connect_args={"check_same_thread": False}
    )
    testing_session = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )
    init_db(test_engine)
    application = create_app()
    adapter = MagicMock(spec=RedroidRuntimeAdapter)

    def override_get_db() -> Iterator[Session]:
        with testing_session() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_redroid_runtime_adapter] = lambda: adapter
    try:
        with TestClient(application) as client:
            yield LifecycleApiEnvironment(client, test_engine, adapter)
    finally:
        application.dependency_overrides.clear()
        test_engine.dispose()


def create_device(environment: LifecycleApiEnvironment) -> dict[str, object]:
    response = environment.client.post(
        "/devices",
        json={
            "name": "Redroid Host",
            "device_type": "virtual",
            "platform": "android",
            "os_version": "14",
            "status": "unknown",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_runtime(
    environment: LifecycleApiEnvironment,
    device_id: int,
    *,
    runtime_type: str = "redroid",
    docker_container_name: str | None = "redroid-device-01",
    adb_serial: str | None = "localhost:5555",
    name: str = "Redroid Runtime",
) -> dict[str, object]:
    response = environment.client.post(
        "/runtimes",
        json={
            "device_id": device_id,
            "name": name,
            "runtime_type": runtime_type,
            "docker_container_name": docker_container_name,
            "adb_serial": adb_serial,
            "status": "unknown",
        },
    )
    assert response.status_code == 201
    return response.json()


def assert_persisted_status(
    environment: LifecycleApiEnvironment,
    device_id: int,
    runtime_id: int,
    *,
    device_status: str,
    runtime_status: str,
) -> None:
    with Session(environment.engine) as session:
        device = session.get(Device, device_id)
        runtime = session.get(Runtime, runtime_id)
        assert device is not None
        assert runtime is not None
        assert device.status == device_status
        assert runtime.status == runtime_status


def test_status_reconciles_ready_external_state(
    lifecycle_api: LifecycleApiEnvironment,
) -> None:
    device = create_device(lifecycle_api)
    runtime = create_runtime(lifecycle_api, int(device["id"]))
    lifecycle_api.adapter.get_container_status.return_value = "running"
    lifecycle_api.adapter.check_boot.return_value = True
    lifecycle_api.adapter.check_adb.return_value = True

    response = lifecycle_api.client.get(f"/devices/{device['id']}/status")

    assert response.status_code == 200
    assert response.json() == {
        "device_id": device["id"],
        "runtime_id": runtime["id"],
        "docker_container_name": "redroid-device-01",
        "adb_serial": "localhost:5555",
        "container_status": "running",
        "boot_completed": True,
        "adb_state": "device",
        "ready": True,
        "runtime_status": "running",
        "device_status": "online",
    }
    lifecycle_api.adapter.get_container_status.assert_called_once_with(
        "redroid-device-01"
    )
    lifecycle_api.adapter.check_boot.assert_called_once_with("redroid-device-01")
    lifecycle_api.adapter.check_adb.assert_called_once_with("localhost:5555")
    assert_persisted_status(
        lifecycle_api,
        int(device["id"]),
        int(runtime["id"]),
        device_status="online",
        runtime_status="running",
    )


def test_status_reconciles_booting_and_degraded_states(
    lifecycle_api: LifecycleApiEnvironment,
) -> None:
    device = create_device(lifecycle_api)
    runtime = create_runtime(lifecycle_api, int(device["id"]))
    lifecycle_api.adapter.get_container_status.return_value = "running"
    lifecycle_api.adapter.check_boot.return_value = False
    lifecycle_api.adapter.check_adb.return_value = False

    booting = lifecycle_api.client.get(f"/devices/{device['id']}/status")
    assert booting.status_code == 200
    assert booting.json()["runtime_status"] == "starting"
    assert booting.json()["device_status"] == "offline"

    lifecycle_api.adapter.check_boot.return_value = True
    degraded = lifecycle_api.client.get(f"/devices/{device['id']}/status")
    assert degraded.status_code == 200
    assert degraded.json()["runtime_status"] == "degraded"
    assert degraded.json()["device_status"] == "offline"
    assert_persisted_status(
        lifecycle_api,
        int(device["id"]),
        int(runtime["id"]),
        device_status="offline",
        runtime_status="degraded",
    )


def test_start_waits_connects_adb_and_updates_statuses(
    lifecycle_api: LifecycleApiEnvironment,
) -> None:
    device = create_device(lifecycle_api)
    runtime = create_runtime(lifecycle_api, int(device["id"]))
    lifecycle_api.adapter.wait_for_adb.return_value = True

    response = lifecycle_api.client.post(f"/devices/{device['id']}/start")

    assert response.status_code == 200
    assert response.json()["ready"] is True
    lifecycle_api.adapter.start_container.assert_called_once_with(
        "redroid-device-01"
    )
    lifecycle_api.adapter.wait_for_boot.assert_called_once_with(
        "redroid-device-01", 120
    )
    lifecycle_api.adapter.wait_for_adb.assert_called_once_with(
        "localhost:5555", 30
    )
    assert_persisted_status(
        lifecycle_api,
        int(device["id"]),
        int(runtime["id"]),
        device_status="online",
        runtime_status="running",
    )


def test_restart_waits_for_adb_readiness(
    lifecycle_api: LifecycleApiEnvironment,
) -> None:
    device = create_device(lifecycle_api)
    runtime = create_runtime(lifecycle_api, int(device["id"]))
    lifecycle_api.adapter.wait_for_adb.return_value = True

    response = lifecycle_api.client.post(f"/devices/{device['id']}/restart")

    assert response.status_code == 200
    assert response.json()["ready"] is True
    lifecycle_api.adapter.restart_container.assert_called_once_with(
        "redroid-device-01"
    )
    lifecycle_api.adapter.wait_for_boot.assert_called_once_with(
        "redroid-device-01", 120
    )
    lifecycle_api.adapter.wait_for_adb.assert_called_once_with(
        "localhost:5555", 30
    )
    assert_persisted_status(
        lifecycle_api,
        int(device["id"]),
        int(runtime["id"]),
        device_status="online",
        runtime_status="running",
    )


def test_stop_preserves_runtime_and_reconciles_stopped_state(
    lifecycle_api: LifecycleApiEnvironment,
) -> None:
    device = create_device(lifecycle_api)
    runtime = create_runtime(lifecycle_api, int(device["id"]))
    lifecycle_api.adapter.get_container_status.return_value = "exited"
    lifecycle_api.adapter.check_adb.return_value = False

    response = lifecycle_api.client.post(f"/devices/{device['id']}/stop")

    assert response.status_code == 200
    assert response.json()["container_status"] == "exited"
    assert response.json()["runtime_status"] == "stopped"
    assert response.json()["device_status"] == "offline"
    lifecycle_api.adapter.stop_container.assert_called_once_with(
        "redroid-device-01"
    )
    lifecycle_api.adapter.check_boot.assert_not_called()
    with Session(lifecycle_api.engine) as session:
        assert session.get(Runtime, int(runtime["id"])) is not None


@pytest.mark.parametrize(
    ("runtime_options", "detail"),
    [
        ({"runtime_type": "emulator"}, "Assigned Runtime is not Redroid-backed"),
        (
            {"docker_container_name": None},
            "Assigned Runtime is missing docker_container_name",
        ),
        ({"adb_serial": None}, "Assigned Runtime is missing adb_serial"),
    ],
)
def test_lifecycle_rejects_invalid_runtime_configuration(
    lifecycle_api: LifecycleApiEnvironment,
    runtime_options: dict[str, object],
    detail: str,
) -> None:
    device = create_device(lifecycle_api)
    create_runtime(lifecycle_api, int(device["id"]), **runtime_options)

    response = lifecycle_api.client.get(f"/devices/{device['id']}/status")

    assert response.status_code == 409
    assert response.json() == {"detail": detail}
    lifecycle_api.adapter.get_container_status.assert_not_called()


def test_lifecycle_requires_exactly_one_runtime(
    lifecycle_api: LifecycleApiEnvironment,
) -> None:
    device = create_device(lifecycle_api)

    missing = lifecycle_api.client.get(f"/devices/{device['id']}/status")
    assert missing.status_code == 409
    assert missing.json() == {"detail": "Device has no assigned Runtime"}

    create_runtime(lifecycle_api, int(device["id"]), name="Runtime 1")
    create_runtime(
        lifecycle_api,
        int(device["id"]),
        name="Runtime 2",
        docker_container_name="redroid-device-02",
        adb_serial="localhost:5556",
    )
    ambiguous = lifecycle_api.client.get(f"/devices/{device['id']}/status")
    assert ambiguous.status_code == 409
    assert ambiguous.json() == {
        "detail": "Device lifecycle requires exactly one assigned Runtime"
    }


def test_start_returns_bad_gateway_when_adb_never_becomes_ready(
    lifecycle_api: LifecycleApiEnvironment,
) -> None:
    device = create_device(lifecycle_api)
    create_runtime(lifecycle_api, int(device["id"]))
    lifecycle_api.adapter.wait_for_adb.side_effect = RedroidAdbTimeoutError(
        "localhost:5555", 30
    )

    response = lifecycle_api.client.post(f"/devices/{device['id']}/start")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "ADB target 'localhost:5555' did not reach device state "
        "within 30 seconds"
    }


def test_adapter_failures_map_to_gateway_errors(
    lifecycle_api: LifecycleApiEnvironment,
) -> None:
    device = create_device(lifecycle_api)
    create_runtime(lifecycle_api, int(device["id"]))
    lifecycle_api.adapter.get_container_status.side_effect = RedroidCommandError(
        ["docker", "inspect"], returncode=1, stderr="daemon unavailable"
    )
    status_response = lifecycle_api.client.get(f"/devices/{device['id']}/status")
    assert status_response.status_code == 502
    assert "daemon unavailable" in status_response.json()["detail"]

    lifecycle_api.adapter.reset_mock(side_effect=True)
    lifecycle_api.adapter.wait_for_boot.side_effect = RedroidBootTimeoutError(
        "redroid-device-01", 120
    )
    start_response = lifecycle_api.client.post(f"/devices/{device['id']}/start")
    assert start_response.status_code == 504


def test_missing_device_returns_404_without_using_adapter(
    lifecycle_api: LifecycleApiEnvironment,
) -> None:
    response = lifecycle_api.client.get("/devices/999/status")

    assert response.status_code == 404
    assert response.json() == {"detail": "Device not found"}
    lifecycle_api.adapter.get_container_status.assert_not_called()
