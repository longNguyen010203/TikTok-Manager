"""API tests for scrcpy-backed Device screen sessions."""

import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, init_db
from app.models import Device, Runtime
from app.routers.devices import get_screen_process_manager
from app.services.device_screen import ScreenProcessManager
from tests.app_factory import create_test_app


@dataclass(frozen=True)
class ScreenApiEnvironment:
    client: TestClient
    engine: Engine
    manager: ScreenProcessManager


@pytest.fixture
def screen_api(tmp_path: Path) -> Iterator[ScreenApiEnvironment]:
    database_url = URL.create(
        drivername="sqlite", database=str(tmp_path / "screen-api.db")
    )
    test_engine = create_engine(
        database_url, connect_args={"check_same_thread": False}
    )
    testing_session = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )
    init_db(test_engine)
    application = create_test_app()
    manager = ScreenProcessManager(terminate_timeout=0.01)

    def override_get_db() -> Iterator[Session]:
        with testing_session() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_screen_process_manager] = lambda: manager
    try:
        with TestClient(application) as client:
            yield ScreenApiEnvironment(client, test_engine, manager)
    finally:
        application.dependency_overrides.clear()
        test_engine.dispose()


def create_device(environment: ScreenApiEnvironment) -> dict[str, object]:
    response = environment.client.post(
        "/devices",
        json={
            "name": "Redroid Host",
            "device_type": "virtual",
            "platform": "android",
            "os_version": "14",
            "status": "online",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_runtime(
    environment: ScreenApiEnvironment,
    device_id: int,
    *,
    runtime_type: str = "redroid",
    docker_container_name: str | None = "redroid-device-01",
    adb_serial: str | None = "localhost:5555",
) -> dict[str, object]:
    response = environment.client.post(
        "/runtimes",
        json={
            "device_id": device_id,
            "name": "Redroid Runtime",
            "runtime_type": runtime_type,
            "docker_container_name": docker_container_name,
            "adb_serial": adb_serial,
            "status": "running",
        },
    )
    assert response.status_code == 201
    return response.json()


def screen_process(pid: int = 4321) -> MagicMock:
    process = MagicMock()
    process.pid = pid
    process.poll.return_value = None
    process.wait.return_value = 0
    return process


@patch("app.services.device_screen.subprocess.Popen")
def test_open_status_duplicate_and_close_screen(
    mock_popen, screen_api: ScreenApiEnvironment
) -> None:
    device = create_device(screen_api)
    runtime = create_runtime(screen_api, int(device["id"]))
    process = screen_process()
    mock_popen.return_value = process

    opened = screen_api.client.post(f"/devices/{device['id']}/screen/open")
    duplicate = screen_api.client.post(f"/devices/{device['id']}/screen/open")
    current = screen_api.client.get(f"/devices/{device['id']}/screen/status")
    closed = screen_api.client.post(f"/devices/{device['id']}/screen/close")

    expected_open = {
        "device_id": device["id"],
        "runtime_id": runtime["id"],
        "adb_serial": "localhost:5555",
        "status": "open",
        "process_id": 4321,
    }
    assert opened.status_code == 200
    assert opened.json() == expected_open
    assert duplicate.json() == expected_open
    assert current.json() == expected_open
    assert closed.json() == {
        **expected_open,
        "status": "closed",
        "process_id": None,
    }
    mock_popen.assert_called_once_with(
        ["scrcpy", "--serial", "localhost:5555"],
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    process.terminate.assert_called_once_with()
    process.wait.assert_called_once_with(timeout=0.01)

    with Session(screen_api.engine) as session:
        stored_device = session.get(Device, int(device["id"]))
        stored_runtime = session.get(Runtime, int(runtime["id"]))
        assert stored_device is not None and stored_device.status == "online"
        assert stored_runtime is not None and stored_runtime.status == "running"


@patch("app.services.device_screen.subprocess.Popen")
def test_two_device_screen_sessions_are_independent(
    mock_popen, screen_api: ScreenApiEnvironment
) -> None:
    device_01 = create_device(screen_api)
    runtime_01 = create_runtime(screen_api, int(device_01["id"]))
    device_02 = create_device(screen_api)
    runtime_02 = create_runtime(
        screen_api,
        int(device_02["id"]),
        docker_container_name="redroid-device-02",
        adb_serial="localhost:5556",
    )
    process_01 = screen_process(1001)
    process_02 = screen_process(1002)
    replacement_01 = screen_process(1003)
    mock_popen.side_effect = [process_01, process_02, replacement_01]

    opened_01 = screen_api.client.post(
        f"/devices/{device_01['id']}/screen/open"
    )
    opened_02 = screen_api.client.post(
        f"/devices/{device_02['id']}/screen/open"
    )

    assert opened_01.json()["process_id"] == 1001
    assert opened_01.json()["adb_serial"] == "localhost:5555"
    assert opened_02.json()["process_id"] == 1002
    assert opened_02.json()["adb_serial"] == "localhost:5556"
    assert mock_popen.call_args_list[0].args[0] == [
        "scrcpy",
        "--serial",
        "localhost:5555",
    ]
    assert mock_popen.call_args_list[1].args[0] == [
        "scrcpy",
        "--serial",
        "localhost:5556",
    ]

    closed_01 = screen_api.client.post(
        f"/devices/{device_01['id']}/screen/close"
    )
    still_open_02 = screen_api.client.get(
        f"/devices/{device_02['id']}/screen/status"
    )
    assert closed_01.json()["status"] == "closed"
    assert still_open_02.json()["status"] == "open"
    process_01.terminate.assert_called_once_with()
    process_02.terminate.assert_not_called()

    reopened_01 = screen_api.client.post(
        f"/devices/{device_01['id']}/screen/open"
    )
    assert reopened_01.json()["process_id"] == 1003
    process_02.poll.return_value = 0

    reaped_02 = screen_api.client.get(
        f"/devices/{device_02['id']}/screen/status"
    )
    unaffected_01 = screen_api.client.get(
        f"/devices/{device_01['id']}/screen/status"
    )
    assert reaped_02.json()["status"] == "closed"
    assert unaffected_01.json()["status"] == "open"
    assert unaffected_01.json()["runtime_id"] == runtime_01["id"]
    assert reaped_02.json()["runtime_id"] == runtime_02["id"]


@patch("app.services.device_screen.subprocess.Popen")
def test_status_reaps_exited_process_and_allows_reopen(
    mock_popen, screen_api: ScreenApiEnvironment
) -> None:
    device = create_device(screen_api)
    create_runtime(screen_api, int(device["id"]))
    exited = screen_process(1001)
    replacement = screen_process(1002)
    mock_popen.side_effect = [exited, replacement]

    opened = screen_api.client.post(f"/devices/{device['id']}/screen/open")
    assert opened.json()["process_id"] == 1001
    exited.poll.return_value = 0

    status_response = screen_api.client.get(
        f"/devices/{device['id']}/screen/status"
    )
    reopened = screen_api.client.post(f"/devices/{device['id']}/screen/open")

    assert status_response.json()["status"] == "closed"
    assert reopened.json()["process_id"] == 1002
    assert mock_popen.call_count == 2


@patch("app.services.device_screen.subprocess.Popen")
def test_close_without_session_is_idempotent(
    mock_popen, screen_api: ScreenApiEnvironment
) -> None:
    device = create_device(screen_api)
    create_runtime(screen_api, int(device["id"]))

    response = screen_api.client.post(f"/devices/{device['id']}/screen/close")

    assert response.status_code == 200
    assert response.json()["status"] == "closed"
    assert response.json()["process_id"] is None
    mock_popen.assert_not_called()


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
@patch("app.services.device_screen.subprocess.Popen")
def test_screen_requires_valid_redroid_runtime(
    mock_popen,
    screen_api: ScreenApiEnvironment,
    runtime_options: dict[str, object],
    detail: str,
) -> None:
    device = create_device(screen_api)
    create_runtime(screen_api, int(device["id"]), **runtime_options)

    response = screen_api.client.post(f"/devices/{device['id']}/screen/open")

    assert response.status_code == 409
    assert response.json() == {"detail": detail}
    mock_popen.assert_not_called()


@patch("app.services.device_screen.subprocess.Popen")
def test_screen_requires_exactly_one_assigned_runtime(
    mock_popen, screen_api: ScreenApiEnvironment
) -> None:
    device = create_device(screen_api)

    missing = screen_api.client.get(f"/devices/{device['id']}/screen/status")
    assert missing.status_code == 409
    assert missing.json() == {"detail": "Device has no assigned Runtime"}

    create_runtime(screen_api, int(device["id"]))
    create_runtime(
        screen_api,
        int(device["id"]),
        docker_container_name="redroid-device-02",
        adb_serial="localhost:5556",
    )
    ambiguous = screen_api.client.post(f"/devices/{device['id']}/screen/open")

    assert ambiguous.status_code == 409
    assert ambiguous.json() == {
        "detail": "Device lifecycle requires exactly one assigned Runtime"
    }
    mock_popen.assert_not_called()


@patch("app.services.device_screen.subprocess.Popen")
def test_screen_launch_failure_returns_bad_gateway(
    mock_popen, screen_api: ScreenApiEnvironment
) -> None:
    device = create_device(screen_api)
    create_runtime(screen_api, int(device["id"]))
    mock_popen.side_effect = FileNotFoundError("scrcpy not found")

    response = screen_api.client.post(f"/devices/{device['id']}/screen/open")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Unable to launch scrcpy for ADB target 'localhost:5555': "
        "scrcpy not found"
    }


def test_screen_missing_device_returns_not_found(
    screen_api: ScreenApiEnvironment,
) -> None:
    response = screen_api.client.get("/devices/999/screen/status")

    assert response.status_code == 404
    assert response.json() == {"detail": "Device not found"}
