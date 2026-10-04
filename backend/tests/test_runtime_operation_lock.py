"""Shared Runtime operation-lock tests."""

from pathlib import Path
from multiprocessing import Event, Process
from unittest.mock import MagicMock

import pytest

from app.models import Device, Runtime
from app.services.device_lifecycle import (
    DeviceLifecycleService,
    RuntimeLifecycleBusyError,
)
from app.services.network_operation_lock import RuntimeNetworkOperationGuard
from app.services.runtime_operation_lock import (
    RuntimeOperationGuard,
    RuntimeOperationLockBusy,
    RuntimeOperationLockError,
)


def _hold_runtime_lock(lock_directory: str, ready) -> None:
    guard = RuntimeOperationGuard(Path(lock_directory))
    with guard.acquire_runtime(17):
        ready.set()
        Event().wait(30)


def test_network_and_automation_use_the_same_runtime_lock(tmp_path: Path) -> None:
    network = RuntimeNetworkOperationGuard(tmp_path / "locks")
    automation = RuntimeOperationGuard(tmp_path / "locks")
    with network.acquire_runtime(7):
        with pytest.raises(RuntimeOperationLockBusy):
            with automation.acquire_runtime(7, blocking=False):
                pass


def test_lifecycle_contends_with_automation_lock(tmp_path: Path) -> None:
    automation = RuntimeOperationGuard(tmp_path / "locks")
    lifecycle_guard = RuntimeOperationGuard(tmp_path / "locks")
    adapter = MagicMock()
    device = Device(
        id=1,
        name="Device",
        device_type="emulator",
        platform="android",
        os_version="12",
        status="online",
    )
    device.runtimes.append(
        Runtime(
            id=8,
            name="Runtime",
            runtime_type="redroid",
            docker_container_name="redroid-08",
            adb_serial="localhost:5562",
            status="running",
        )
    )
    service = DeviceLifecycleService(
        MagicMock(), adapter, operation_guard=lifecycle_guard
    )
    with automation.acquire_runtime(8):
        with pytest.raises(RuntimeLifecycleBusyError):
            service.stop(device)
    adapter.stop_container.assert_not_called()


def test_lock_releases_and_different_runtimes_do_not_contend(tmp_path: Path) -> None:
    first = RuntimeOperationGuard(tmp_path / "locks")
    second = RuntimeOperationGuard(tmp_path / "locks")
    with first.acquire_runtime(1):
        with second.acquire_runtime(2, blocking=False):
            pass
    with second.acquire_runtime(1, blocking=False):
        pass


def test_lock_is_released_when_owner_process_dies(tmp_path: Path) -> None:
    lock_directory = tmp_path / "locks"
    ready = Event()
    process = Process(
        target=_hold_runtime_lock,
        args=(str(lock_directory), ready),
    )
    process.start()
    assert ready.wait(5)
    contender = RuntimeOperationGuard(lock_directory)
    with pytest.raises(RuntimeOperationLockBusy):
        with contender.acquire_runtime(17, blocking=False):
            pass

    process.terminate()
    process.join(5)
    assert not process.is_alive()
    with contender.acquire_runtime(17, blocking=False):
        pass


def test_bounded_wait_reports_contention(tmp_path: Path) -> None:
    first = RuntimeOperationGuard(tmp_path / "locks")
    second = RuntimeOperationGuard(tmp_path / "locks", poll_interval=0.001)
    with first.acquire_runtime(3):
        with pytest.raises(RuntimeOperationLockBusy):
            with second.acquire_runtime(3, timeout=0.005):
                pass


def test_lock_directory_symlink_is_rejected(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "locks"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(RuntimeOperationLockError):
        with RuntimeOperationGuard(link).acquire_runtime(1):
            pass


@pytest.mark.parametrize("runtime_id", [0, -1, True, "1"])
def test_runtime_id_must_be_positive_integer(tmp_path: Path, runtime_id) -> None:
    with pytest.raises(ValueError):
        with RuntimeOperationGuard(tmp_path / "locks").acquire_runtime(runtime_id):
            pass
