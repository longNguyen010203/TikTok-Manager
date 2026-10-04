"""Device lifecycle orchestration for Redroid-backed runtimes."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from typing import Iterator

from sqlalchemy.orm import Session

from app.models import Device, Runtime
from app.models.timestamps import utc_now
from app.schemas.device import DeviceLifecycleStatus
from app.services.redroid_runtime import RedroidRuntimeAdapter
from app.services.runtime_operation_lock import (
    RuntimeOperationGuard,
    RuntimeOperationLockBusy,
)


class DeviceLifecycleError(RuntimeError):
    """Base exception for invalid or unsuccessful lifecycle operations."""


class RuntimeAssignmentError(DeviceLifecycleError):
    """Raised when a Device does not have exactly one assigned Runtime."""


class UnsupportedRuntimeError(DeviceLifecycleError):
    """Raised when the assigned Runtime is not Redroid-backed."""


class RuntimeConfigurationError(DeviceLifecycleError):
    """Raised when required Redroid connection settings are missing."""


class RuntimeLifecycleBusyError(DeviceLifecycleError):
    """Raised when another operation currently owns the Runtime."""


@dataclass(frozen=True)
class RedroidTarget:
    """Validated Redroid configuration associated with a Device."""

    runtime: Runtime
    container_name: str
    adb_serial: str


class DeviceLifecycleService:
    """Run lifecycle operations and persist state observed from Docker/ADB."""

    def __init__(
        self,
        session: Session,
        adapter: RedroidRuntimeAdapter,
        *,
        boot_timeout: float = 120,
        adb_timeout: float = 30,
        operation_guard: RuntimeOperationGuard | None = None,
        operation_lock_timeout: float = 0,
    ) -> None:
        self.session = session
        self.adapter = adapter
        self.boot_timeout = boot_timeout
        self.adb_timeout = adb_timeout
        self.operation_guard = operation_guard
        self.operation_lock_timeout = operation_lock_timeout

    def status(self, device: Device) -> DeviceLifecycleStatus:
        """Inspect external state and reconcile it into the database."""
        target = get_redroid_target(device)
        return self._observe_and_reconcile(device, target)

    def start(self, device: Device) -> DeviceLifecycleStatus:
        """Start the container and wait until Android and ADB are ready."""
        target = get_redroid_target(device)
        with self._runtime_operation(target.runtime.id):
            self.adapter.start_container(target.container_name)
            self._wait_for_readiness(target)
            return self._reconcile(
                device,
                target,
                container_status="running",
                boot_completed=True,
                adb_connected=True,
            )

    def stop(self, device: Device) -> DeviceLifecycleStatus:
        """Stop the container without deleting its persistent state."""
        target = get_redroid_target(device)
        with self._runtime_operation(target.runtime.id):
            self.adapter.stop_container(target.container_name)
            return self._observe_and_reconcile(device, target)

    def restart(self, device: Device) -> DeviceLifecycleStatus:
        """Restart the container and wait until Android and ADB are ready."""
        target = get_redroid_target(device)
        with self._runtime_operation(target.runtime.id):
            self.adapter.restart_container(target.container_name)
            self._wait_for_readiness(target)
            return self._reconcile(
                device,
                target,
                container_status="running",
                boot_completed=True,
                adb_connected=True,
            )

    def _wait_for_readiness(self, target: RedroidTarget) -> None:
        self.adapter.wait_for_boot(target.container_name, self.boot_timeout)
        self.adapter.wait_for_adb(target.adb_serial, self.adb_timeout)

    def _observe_and_reconcile(
        self, device: Device, target: RedroidTarget
    ) -> DeviceLifecycleStatus:
        container_status = self.adapter.get_container_status(target.container_name)
        boot_completed = False
        if container_status == "running":
            boot_completed = self.adapter.check_boot(target.container_name)
        adb_connected = self.adapter.check_adb(target.adb_serial)
        return self._reconcile(
            device,
            target,
            container_status=container_status,
            boot_completed=boot_completed,
            adb_connected=adb_connected,
        )

    def _reconcile(
        self,
        device: Device,
        target: RedroidTarget,
        *,
        container_status: str,
        boot_completed: bool,
        adb_connected: bool,
    ) -> DeviceLifecycleStatus:
        ready = container_status == "running" and boot_completed and adb_connected
        if ready:
            runtime_status = "running"
        elif container_status == "running":
            runtime_status = "starting" if not boot_completed else "degraded"
        elif container_status in {"dead", "exited"}:
            runtime_status = "stopped"
        else:
            runtime_status = container_status

        device_status = "online" if ready else "offline"
        target.runtime.status = runtime_status
        device.status = device_status
        if ready:
            target.runtime.last_seen_at = utc_now()
        self.session.commit()

        return DeviceLifecycleStatus(
            device_id=device.id,
            runtime_id=target.runtime.id,
            docker_container_name=target.container_name,
            adb_serial=target.adb_serial,
            container_status=container_status,
            boot_completed=boot_completed,
            adb_state="device" if adb_connected else "unavailable",
            ready=ready,
            runtime_status=runtime_status,
            device_status=device_status,
        )

    @contextmanager
    def _runtime_operation(self, runtime_id: int) -> Iterator[None]:
        if self.operation_guard is None:
            with nullcontext():
                yield
            return
        try:
            with self.operation_guard.acquire_runtime(
                runtime_id, timeout=self.operation_lock_timeout
            ):
                yield
        except RuntimeOperationLockBusy as error:
            raise RuntimeLifecycleBusyError(
                "Runtime is busy with another operation"
            ) from error



def get_redroid_target(device: Device) -> RedroidTarget:
    """Return the Device's single, fully configured Redroid target."""
    if not device.runtimes:
        raise RuntimeAssignmentError("Device has no assigned Runtime")
    if len(device.runtimes) > 1:
        raise RuntimeAssignmentError(
            "Device lifecycle requires exactly one assigned Runtime"
        )

    runtime = device.runtimes[0]
    if runtime.runtime_type != "redroid":
        raise UnsupportedRuntimeError("Assigned Runtime is not Redroid-backed")
    if not runtime.docker_container_name:
        raise RuntimeConfigurationError(
            "Assigned Runtime is missing docker_container_name"
        )
    if not runtime.adb_serial:
        raise RuntimeConfigurationError("Assigned Runtime is missing adb_serial")

    return RedroidTarget(
        runtime=runtime,
        container_name=runtime.docker_container_name,
        adb_serial=runtime.adb_serial,
    )
