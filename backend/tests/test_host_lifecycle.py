"""Tests for TikTok Manager host startup and shutdown behavior."""

import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import init_db
from app.main import create_app
from app.models import Device, Runtime
from app.services.device_screen import ScreenCleanupResult, ScreenProcessManager
from app.services.host_lifecycle import (
    STOP_MANAGED_DEVICES_ON_SHUTDOWN,
    BinderHostPaths,
    HostDependencyError,
    HostLifecycleManager,
    check_binder_readiness,
    stop_managed_devices_on_shutdown_from_environment,
)
from app.services.redroid_runtime import RedroidCommandError, RedroidRuntimeAdapter


def session_factory(tmp_path: Path) -> tuple[sessionmaker[Session], object]:
    database_url = URL.create(
        drivername="sqlite", database=str(tmp_path / "host-lifecycle.db")
    )
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    init_db(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False), engine


def host_manager(
    factory: sessionmaker[Session],
    *,
    adapter: MagicMock | None = None,
    screens: MagicMock | ScreenProcessManager | None = None,
    stop_managed_devices_on_shutdown: bool = True,
    binder_readiness_check=None,
) -> HostLifecycleManager:
    runtime_adapter = adapter or MagicMock(spec=RedroidRuntimeAdapter)
    screen_manager = screens or MagicMock(spec=ScreenProcessManager)
    if isinstance(screen_manager, MagicMock):
        screen_manager.close_all.return_value = ScreenCleanupResult((), ())
    return HostLifecycleManager(
        factory,
        runtime_adapter,
        screen_manager,
        stop_managed_devices_on_shutdown=stop_managed_devices_on_shutdown,
        binder_readiness_check=binder_readiness_check or (lambda: ()),
    )


def binder_paths(tmp_path: Path) -> BinderHostPaths:
    return BinderHostPaths(
        module=tmp_path / "sys/module/binder_linux",
        mount_point=tmp_path / "dev/binderfs",
        mountinfo=tmp_path / "proc/self/mountinfo",
        endpoints=(
            tmp_path / "dev/binderfs/binder",
            tmp_path / "dev/binderfs/hwbinder",
            tmp_path / "dev/binderfs/vndbinder",
        ),
    )


def test_binder_readiness_accepts_loaded_module_mount_and_endpoints(
    tmp_path: Path,
) -> None:
    paths = binder_paths(tmp_path)
    paths.module.mkdir(parents=True)
    paths.mount_point.mkdir(parents=True)
    paths.mountinfo.parent.mkdir(parents=True)
    paths.mountinfo.write_text(
        f"31 24 0:28 / {paths.mount_point} rw - binder binder rw\n",
        encoding="utf-8",
    )
    for endpoint in paths.endpoints:
        endpoint.parent.mkdir(parents=True, exist_ok=True)
        endpoint.touch()

    assert check_binder_readiness(paths) == ()


def test_binder_readiness_reports_missing_module_mount_and_endpoints(
    tmp_path: Path,
) -> None:
    paths = binder_paths(tmp_path)
    paths.mountinfo.parent.mkdir(parents=True)
    paths.mountinfo.write_text("", encoding="utf-8")

    failures = check_binder_readiness(paths)

    assert any("binder_linux kernel module is not loaded" in item for item in failures)
    assert any("Binder mount point is missing" in item for item in failures)
    assert any("binderfs is not mounted" in item for item in failures)
    for endpoint in paths.endpoints:
        assert f"Binder endpoint is missing: {endpoint}" in failures


@patch("app.services.host_lifecycle.shutil.which")
@patch("app.services.host_lifecycle.subprocess.run")
def test_startup_fails_clearly_when_binder_is_not_ready(
    mock_run, mock_which, tmp_path: Path
) -> None:
    factory, engine = session_factory(tmp_path)
    manager = host_manager(
        factory,
        binder_readiness_check=lambda: (
            "binder_linux kernel module is not loaded; install or repair "
            "redroid-binder.service",
        ),
    )
    mock_run.return_value = subprocess.CompletedProcess(
        [], 0, stdout="27.3.1\n", stderr=""
    )
    mock_which.side_effect = lambda name: f"/usr/bin/{name}"

    with pytest.raises(HostDependencyError, match="redroid-binder.service"):
        manager.startup()

    manager.runtime_adapter.start_container.assert_not_called()
    manager.runtime_adapter.stop_container.assert_not_called()
    manager.runtime_adapter.restart_container.assert_not_called()
    manager.screen_manager.open.assert_not_called()
    engine.dispose()


def test_managed_device_shutdown_configuration_defaults_true_and_accepts_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(STOP_MANAGED_DEVICES_ON_SHUTDOWN, raising=False)
    assert stop_managed_devices_on_shutdown_from_environment() is True

    monkeypatch.setenv(STOP_MANAGED_DEVICES_ON_SHUTDOWN, "false")
    assert stop_managed_devices_on_shutdown_from_environment() is False


@patch("app.services.host_lifecycle.shutil.which")
@patch("app.services.host_lifecycle.subprocess.run")
def test_startup_succeeds_when_host_dependencies_are_available(
    mock_run, mock_which, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    factory, engine = session_factory(tmp_path)
    adapter = MagicMock(spec=RedroidRuntimeAdapter)
    screens = MagicMock(spec=ScreenProcessManager)
    manager = host_manager(factory, adapter=adapter, screens=screens)
    mock_run.return_value = subprocess.CompletedProcess(
        [], 0, stdout="27.3.1\n", stderr=""
    )
    mock_which.side_effect = lambda name: f"/usr/bin/{name}"

    with caplog.at_level(logging.INFO):
        capabilities = manager.startup()

    assert capabilities.docker_server_version == "27.3.1"
    assert capabilities.adb_path == "/usr/bin/adb"
    assert capabilities.scrcpy_path == "/usr/bin/scrcpy"
    mock_run.assert_called_once_with(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        shell=False,
        capture_output=True,
        text=True,
        check=False,
    )
    assert adapter.method_calls == []
    assert screens.method_calls == []
    assert (
        "Startup reconciliation leaves Redroid containers and screens unchanged"
        in caplog.text
    )
    engine.dispose()


@patch("app.services.host_lifecycle.shutil.which")
@patch("app.services.host_lifecycle.subprocess.run")
def test_startup_reconciles_exited_container_to_stopped_and_offline(
    mock_run, mock_which, tmp_path: Path
) -> None:
    factory, engine = session_factory(tmp_path)
    with factory() as session:
        device = Device(
            name="Stopped Device",
            device_type="virtual",
            platform="android",
            os_version="14",
            status="online",
        )
        session.add(device)
        session.flush()
        session.add(
            Runtime(
                device_id=device.id,
                name="Stopped Redroid",
                runtime_type="redroid",
                docker_container_name="redroid-device-01",
                adb_serial="localhost:5555",
                status="running",
            )
        )
        session.commit()

    adapter = MagicMock(spec=RedroidRuntimeAdapter)
    adapter.get_container_status.return_value = "exited"
    adapter.check_adb.return_value = False
    mock_run.return_value = subprocess.CompletedProcess(
        [], 0, stdout="27.3.1\n", stderr=""
    )
    mock_which.side_effect = lambda name: f"/usr/bin/{name}"

    host_manager(factory, adapter=adapter).startup()

    adapter.get_container_status.assert_called_once_with("redroid-device-01")
    adapter.check_boot.assert_not_called()
    adapter.check_adb.assert_called_once_with("localhost:5555")
    adapter.start_container.assert_not_called()
    adapter.stop_container.assert_not_called()
    adapter.restart_container.assert_not_called()
    with factory() as session:
        runtime = session.scalar(select(Runtime))
        device = session.scalar(select(Device))
        assert runtime is not None and runtime.status == "stopped"
        assert device is not None and device.status == "offline"

    engine.dispose()


@patch("app.services.host_lifecycle.shutil.which")
@patch("app.services.host_lifecycle.subprocess.run")
def test_startup_reconciles_ready_container_to_running_and_online(
    mock_run, mock_which, tmp_path: Path
) -> None:
    factory, engine = session_factory(tmp_path)
    with factory() as session:
        device = Device(
            name="Ready Device",
            device_type="virtual",
            platform="android",
            os_version="14",
            status="offline",
        )
        session.add(device)
        session.flush()
        session.add(
            Runtime(
                device_id=device.id,
                name="Ready Redroid",
                runtime_type="redroid",
                docker_container_name="redroid-device-01",
                adb_serial="localhost:5555",
                status="stopped",
            )
        )
        session.commit()

    adapter = MagicMock(spec=RedroidRuntimeAdapter)
    adapter.get_container_status.return_value = "running"
    adapter.check_boot.return_value = True
    adapter.check_adb.return_value = True
    mock_run.return_value = subprocess.CompletedProcess(
        [], 0, stdout="27.3.1\n", stderr=""
    )
    mock_which.side_effect = lambda name: f"/usr/bin/{name}"

    host_manager(factory, adapter=adapter).startup()

    adapter.get_container_status.assert_called_once_with("redroid-device-01")
    adapter.check_boot.assert_called_once_with("redroid-device-01")
    adapter.check_adb.assert_called_once_with("localhost:5555")
    adapter.start_container.assert_not_called()
    adapter.stop_container.assert_not_called()
    adapter.restart_container.assert_not_called()
    with factory() as session:
        runtime = session.scalar(select(Runtime))
        device = session.scalar(select(Device))
        assert runtime is not None and runtime.status == "running"
        assert device is not None and device.status == "online"
        assert runtime.last_seen_at is not None

    engine.dispose()


@patch("app.services.host_lifecycle.shutil.which")
@patch("app.services.host_lifecycle.subprocess.run")
def test_startup_reconciles_two_redroid_devices_independently(
    mock_run, mock_which, tmp_path: Path
) -> None:
    factory, engine = session_factory(tmp_path)
    with factory() as session:
        devices = [
            Device(
                name=f"Redroid Device {index:02d}",
                device_type="emulator",
                platform="android",
                os_version="12",
                status="offline" if index == 1 else "online",
            )
            for index in (1, 2)
        ]
        session.add_all(devices)
        session.flush()
        session.add_all(
            [
                Runtime(
                    device_id=devices[0].id,
                    name="redroid-runtime-01",
                    runtime_type="redroid",
                    docker_container_name="redroid-device-01",
                    adb_serial="localhost:5555",
                    status="stopped",
                ),
                Runtime(
                    device_id=devices[1].id,
                    name="redroid-runtime-02",
                    runtime_type="redroid",
                    docker_container_name="redroid-device-02",
                    adb_serial="localhost:5556",
                    status="running",
                ),
            ]
        )
        session.commit()

    adapter = MagicMock(spec=RedroidRuntimeAdapter)
    adapter.get_container_status.side_effect = ["running", "exited"]
    adapter.check_boot.return_value = True
    adapter.check_adb.side_effect = [True, False]
    mock_run.return_value = subprocess.CompletedProcess(
        [], 0, stdout="27.3.1\n", stderr=""
    )
    mock_which.side_effect = lambda name: f"/usr/bin/{name}"

    host_manager(factory, adapter=adapter).startup()

    assert adapter.get_container_status.call_args_list == [
        call("redroid-device-01"),
        call("redroid-device-02"),
    ]
    assert adapter.check_adb.call_args_list == [
        call("localhost:5555"),
        call("localhost:5556"),
    ]
    with factory() as session:
        runtimes = {
            runtime.docker_container_name: runtime
            for runtime in session.scalars(select(Runtime).order_by(Runtime.id))
        }
        assert runtimes["redroid-device-01"].status == "running"
        assert runtimes["redroid-device-01"].device.status == "online"
        assert runtimes["redroid-device-02"].status == "stopped"
        assert runtimes["redroid-device-02"].device.status == "offline"

    engine.dispose()


@patch("app.services.host_lifecycle.shutil.which")
@patch("app.services.host_lifecycle.subprocess.run")
def test_startup_reconciliation_continues_after_runtime_failure_and_skips_incomplete(
    mock_run,
    mock_which,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    factory, engine = session_factory(tmp_path)
    with factory() as session:
        devices = [
            Device(
                name=f"Startup Device {index}",
                device_type="virtual",
                platform="android",
                os_version="14",
                status="online",
            )
            for index in range(1, 4)
        ]
        session.add_all(devices)
        session.flush()
        session.add_all(
            [
                Runtime(
                    device_id=devices[0].id,
                    name="Failing Redroid",
                    runtime_type="redroid",
                    docker_container_name="redroid-device-01",
                    adb_serial="localhost:5555",
                    status="running",
                ),
                Runtime(
                    device_id=devices[1].id,
                    name="Healthy Redroid",
                    runtime_type="redroid",
                    docker_container_name="redroid-device-02",
                    adb_serial="localhost:5556",
                    status="running",
                ),
                Runtime(
                    device_id=devices[2].id,
                    name="Incomplete Redroid",
                    runtime_type="redroid",
                    docker_container_name=None,
                    adb_serial=None,
                    status="unknown",
                ),
            ]
        )
        session.commit()

    adapter = MagicMock(spec=RedroidRuntimeAdapter)
    adapter.get_container_status.side_effect = [
        RedroidCommandError(
            ["docker", "inspect", "redroid-device-01"],
            returncode=1,
            stderr="inspect failed",
        ),
        "exited",
    ]
    adapter.check_adb.return_value = False
    mock_run.return_value = subprocess.CompletedProcess(
        [], 0, stdout="27.3.1\n", stderr=""
    )
    mock_which.side_effect = lambda name: f"/usr/bin/{name}"

    with caplog.at_level(logging.INFO):
        host_manager(factory, adapter=adapter).startup()

    assert adapter.get_container_status.call_args_list == [
        call("redroid-device-01"),
        call("redroid-device-02"),
    ]
    adapter.start_container.assert_not_called()
    adapter.stop_container.assert_not_called()
    adapter.restart_container.assert_not_called()
    assert "Startup failed to reconcile Redroid Runtime" in caplog.text
    assert "reconciled=1 failed=1 skipped=1" in caplog.text
    with factory() as session:
        runtimes = {
            runtime.name: runtime
            for runtime in session.scalars(select(Runtime).order_by(Runtime.id))
        }
        assert runtimes["Failing Redroid"].status == "running"
        assert runtimes["Healthy Redroid"].status == "stopped"
        assert runtimes["Healthy Redroid"].device.status == "offline"
        assert runtimes["Incomplete Redroid"].status == "unknown"

    engine.dispose()


@patch("app.services.host_lifecycle.shutil.which")
@patch("app.services.host_lifecycle.subprocess.run")
def test_startup_fails_clearly_when_dependency_is_missing(
    mock_run, mock_which, tmp_path: Path
) -> None:
    factory, engine = session_factory(tmp_path)
    manager = host_manager(factory)
    mock_run.return_value = subprocess.CompletedProcess(
        [], 0, stdout="27.3.1\n", stderr=""
    )
    mock_which.side_effect = lambda name: None if name == "scrcpy" else "/usr/bin/adb"

    with pytest.raises(
        HostDependencyError,
        match="Required host dependencies unavailable: scrcpy executable was not found",
    ):
        manager.startup()

    engine.dispose()


def test_fastapi_lifespan_runs_injected_host_lifecycle() -> None:
    lifecycle = MagicMock()

    with TestClient(create_app(host_lifecycle=lifecycle)) as client:
        lifecycle.startup.assert_called_once_with()
        lifecycle.shutdown.assert_not_called()
        assert client.get("/health").status_code == 200

    lifecycle.shutdown.assert_called_once_with()


@patch("app.services.device_screen.subprocess.Popen")
def test_shutdown_closes_all_tracked_scrcpy_sessions(
    mock_popen, tmp_path: Path
) -> None:
    factory, engine = session_factory(tmp_path)
    first = MagicMock(pid=1001)
    second = MagicMock(pid=1002)
    for process in (first, second):
        process.poll.return_value = None
        process.wait.return_value = 0
    mock_popen.side_effect = [first, second]
    screens = ScreenProcessManager(terminate_timeout=0.01)
    screens.open(1, 1, "localhost:5555")
    screens.open(2, 2, "localhost:5556")

    host_manager(factory, screens=screens).shutdown()

    first.terminate.assert_called_once_with()
    second.terminate.assert_called_once_with()
    assert screens.status(1, 1, "localhost:5555").is_open is False
    assert screens.status(2, 2, "localhost:5556").is_open is False
    engine.dispose()


@patch("app.services.device_screen.subprocess.Popen")
def test_shutdown_disabled_closes_screens_without_stopping_managed_devices(
    mock_popen,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    factory, engine = session_factory(tmp_path)
    with factory() as session:
        device = Device(
            name="Development Device",
            device_type="virtual",
            platform="android",
            os_version="14",
            status="online",
        )
        session.add(device)
        session.flush()
        session.add(
            Runtime(
                device_id=device.id,
                name="Development Redroid",
                runtime_type="redroid",
                docker_container_name="redroid-device-01",
                adb_serial="localhost:5555",
                status="running",
            )
        )
        session.commit()

    process = MagicMock(pid=1001)
    process.poll.return_value = None
    process.wait.return_value = 0
    mock_popen.return_value = process
    screens = ScreenProcessManager(terminate_timeout=0.01)
    screens.open(1, 1, "localhost:5555")
    adapter = MagicMock(spec=RedroidRuntimeAdapter)
    manager = host_manager(
        factory,
        adapter=adapter,
        screens=screens,
        stop_managed_devices_on_shutdown=False,
    )

    with caplog.at_level(logging.INFO):
        manager.shutdown()

    process.terminate.assert_called_once_with()
    assert screens.status(1, 1, "localhost:5555").is_open is False
    assert adapter.method_calls == []
    assert (
        "Managed-device shutdown skipped because "
        "STOP_MANAGED_DEVICES_ON_SHUTDOWN=false" in caplog.text
    )
    with factory() as session:
        runtime = session.scalar(select(Runtime))
        device = session.scalar(select(Device))
        assert runtime is not None and runtime.status == "running"
        assert device is not None and device.status == "online"

    engine.dispose()


def test_shutdown_stops_redroid_containers_and_continues_after_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    factory, engine = session_factory(tmp_path)
    with factory() as session:
        devices = [
            Device(
                name=f"Device {index}",
                device_type="virtual",
                platform="android",
                os_version="14",
                status="online",
            )
            for index in range(1, 6)
        ]
        session.add_all(devices)
        session.flush()
        session.add_all(
            [
                Runtime(
                    device_id=devices[0].id,
                    name="Redroid 1",
                    runtime_type="redroid",
                    docker_container_name="redroid-device-01",
                    adb_serial="localhost:5555",
                    status="running",
                ),
                Runtime(
                    device_id=devices[1].id,
                    name="Redroid 2",
                    runtime_type="redroid",
                    docker_container_name="redroid-device-02",
                    adb_serial="localhost:5556",
                    status="running",
                ),
                Runtime(
                    device_id=devices[2].id,
                    name="Redroid 3",
                    runtime_type="redroid",
                    docker_container_name="redroid-device-03",
                    adb_serial="localhost:5557",
                    status="running",
                ),
                Runtime(
                    device_id=devices[3].id,
                    name="Unconfigured Redroid",
                    runtime_type="redroid",
                    docker_container_name=None,
                    adb_serial=None,
                    status="unknown",
                ),
                Runtime(
                    device_id=devices[4].id,
                    name="Other Runtime",
                    runtime_type="emulator",
                    docker_container_name="other-container",
                    adb_serial="localhost:5560",
                    status="running",
                ),
            ]
        )
        session.commit()

    adapter = MagicMock(spec=RedroidRuntimeAdapter)
    adapter.stop_container.side_effect = [
        "redroid-device-01",
        RedroidCommandError(
            ["docker", "stop", "redroid-device-02"],
            returncode=1,
            stderr="stop failed",
        ),
        "redroid-device-03",
    ]
    screens = MagicMock(spec=ScreenProcessManager)
    screens.close_all.return_value = ScreenCleanupResult((), ())
    manager = host_manager(factory, adapter=adapter, screens=screens)

    with patch.object(Session, "delete", autospec=True) as mock_delete:
        with caplog.at_level(logging.INFO):
            manager.shutdown()

    assert adapter.method_calls == [
        call.stop_container("redroid-device-01"),
        call.stop_container("redroid-device-02"),
        call.stop_container("redroid-device-03"),
    ]
    mock_delete.assert_not_called()
    assert "stopped=2 failed=1 skipped=1" in caplog.text

    with factory() as session:
        runtimes = {
            runtime.name: runtime
            for runtime in session.scalars(select(Runtime).order_by(Runtime.id))
        }
        assert runtimes["Redroid 1"].status == "stopped"
        assert runtimes["Redroid 1"].device.status == "offline"
        assert runtimes["Redroid 2"].status == "running"
        assert runtimes["Redroid 2"].device.status == "online"
        assert runtimes["Redroid 3"].status == "stopped"
        assert runtimes["Redroid 3"].device.status == "offline"
        assert runtimes["Unconfigured Redroid"].status == "unknown"
        assert runtimes["Other Runtime"].status == "running"
        assert session.scalar(select(func.count()).select_from(Device)) == 5
        assert session.scalar(select(func.count()).select_from(Runtime)) == 5

    engine.dispose()
