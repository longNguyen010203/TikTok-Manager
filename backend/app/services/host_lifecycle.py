"""TikTok Manager host startup checks and shutdown cleanup."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Runtime
from app.services.device_lifecycle import DeviceLifecycleService
from app.services.device_screen import ScreenProcessManager
from app.services.redroid_runtime import RedroidRuntimeAdapter

logger = logging.getLogger(__name__)
STOP_MANAGED_DEVICES_ON_SHUTDOWN = "STOP_MANAGED_DEVICES_ON_SHUTDOWN"


class ApplicationLifecycle(Protocol):
    """Startup and shutdown operations owned by the FastAPI lifespan."""

    def startup(self) -> None: ...

    def shutdown(self) -> None: ...


class HostDependencyError(RuntimeError):
    """Raised when a required host capability is unavailable."""


class HostConfigurationError(ValueError):
    """Raised when host lifecycle configuration is invalid."""


@dataclass(frozen=True)
class HostCapabilities:
    """Host executables and Docker connectivity observed at startup."""

    docker_server_version: str
    adb_path: str
    scrcpy_path: str


class HostLifecycleManager:
    """Validate host dependencies and clean up managed runtime processes."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        runtime_adapter: RedroidRuntimeAdapter,
        screen_manager: ScreenProcessManager,
        *,
        stop_managed_devices_on_shutdown: bool = True,
    ) -> None:
        self.session_factory = session_factory
        self.runtime_adapter = runtime_adapter
        self.screen_manager = screen_manager
        self.stop_managed_devices_on_shutdown = stop_managed_devices_on_shutdown

    def startup(self) -> HostCapabilities:
        """Validate host dependencies and reconcile managed runtime state."""
        failures: list[str] = []

        docker_version = self._check_docker(failures)
        adb_path = self._check_executable("adb", failures)
        scrcpy_path = self._check_executable("scrcpy", failures)

        if failures:
            message = "Required host dependencies unavailable: " + "; ".join(failures)
            logger.critical(message)
            raise HostDependencyError(message)

        capabilities = HostCapabilities(
            docker_server_version=docker_version,
            adb_path=adb_path,
            scrcpy_path=scrcpy_path,
        )
        logger.info(
            "Host capabilities ready: Docker server=%s, ADB=%s, scrcpy=%s",
            capabilities.docker_server_version,
            capabilities.adb_path,
            capabilities.scrcpy_path,
        )
        logger.info(
            "Managed-device shutdown policy: %s",
            "enabled" if self.stop_managed_devices_on_shutdown else "disabled",
        )
        self._reconcile_redroid_runtimes()
        logger.info(
            "Startup reconciliation leaves Redroid containers and screens unchanged"
        )
        return capabilities

    def shutdown(self) -> None:
        """Close screens and stop configured Redroid containers without deletion."""
        self._close_screens()
        if self.stop_managed_devices_on_shutdown:
            self._stop_redroid_containers()
        else:
            logger.info(
                "Managed-device shutdown skipped because %s=false",
                STOP_MANAGED_DEVICES_ON_SHUTDOWN,
            )

    @staticmethod
    def _check_docker(failures: list[str]) -> str:
        command = ["docker", "info", "--format", "{{.ServerVersion}}"]
        try:
            result = subprocess.run(
                command,
                shell=False,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            failures.append(f"Docker is unavailable ({error})")
            logger.error("Host capability Docker: unavailable (%s)", error)
            return ""

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            failures.append(f"Docker daemon is unreachable ({detail})")
            logger.error("Host capability Docker daemon: unreachable (%s)", detail)
            return ""

        version = result.stdout.strip() or "unknown"
        logger.info("Host capability Docker daemon: available (server %s)", version)
        return version

    @staticmethod
    def _check_executable(name: str, failures: list[str]) -> str:
        path = shutil.which(name)
        if path is None:
            failures.append(f"{name} executable was not found")
            logger.error("Host capability %s: unavailable", name)
            return ""
        logger.info("Host capability %s: available (%s)", name, path)
        return path

    def _close_screens(self) -> None:
        try:
            result = self.screen_manager.close_all()
        except Exception:
            logger.exception("Shutdown screen cleanup failed unexpectedly")
            return
        for device_id in result.closed_device_ids:
            logger.info("Shutdown closed scrcpy session for Device %s", device_id)
        for failure in result.failures:
            logger.error(
                "Shutdown failed to close scrcpy for Device %s: %s",
                failure.device_id,
                failure.error,
            )
        logger.info(
            "Shutdown screen cleanup complete: closed=%s failed=%s",
            len(result.closed_device_ids),
            len(result.failures),
        )

    def _reconcile_redroid_runtimes(self) -> None:
        """Persist observed Docker/Android/ADB state for managed runtimes."""
        try:
            with self.session_factory() as session:
                runtime_ids = session.scalars(
                    select(Runtime.id)
                    .where(Runtime.runtime_type == "redroid")
                    .order_by(Runtime.id)
                ).all()
        except SQLAlchemyError:
            logger.exception("Startup could not load managed Redroid runtimes")
            return

        reconciled = 0
        failed = 0
        skipped = 0
        for runtime_id in runtime_ids:
            try:
                with self.session_factory() as session:
                    runtime = session.get(Runtime, runtime_id)
                    if runtime is None:
                        skipped += 1
                        logger.warning(
                            "Startup skipped Redroid Runtime %s: record no longer exists",
                            runtime_id,
                        )
                        continue
                    if not runtime.docker_container_name or not runtime.adb_serial:
                        skipped += 1
                        logger.warning(
                            "Startup skipped Redroid Runtime %s: incomplete "
                            "docker_container_name/adb_serial configuration",
                            runtime.id,
                        )
                        continue

                    status = DeviceLifecycleService(
                        session, self.runtime_adapter
                    ).status(runtime.device)
                    reconciled += 1
                    logger.info(
                        "Startup reconciled Redroid Runtime %s container=%s "
                        "runtime_status=%s device_status=%s",
                        runtime.id,
                        status.container_status,
                        status.runtime_status,
                        status.device_status,
                    )
            except Exception as error:
                failed += 1
                logger.error(
                    "Startup failed to reconcile Redroid Runtime %s: %s",
                    runtime_id,
                    error,
                )

        logger.info(
            "Startup Redroid reconciliation complete: reconciled=%s failed=%s "
            "skipped=%s",
            reconciled,
            failed,
            skipped,
        )

    def _stop_redroid_containers(self) -> None:
        stopped_runtime_ids: set[int] = set()
        try:
            with self.session_factory() as session:
                runtimes = session.scalars(
                    select(Runtime)
                    .where(Runtime.runtime_type == "redroid")
                    .order_by(Runtime.id)
                ).all()

                attempted = 0
                failed = 0
                skipped = 0
                affected_device_ids: set[int] = set()
                for runtime in runtimes:
                    if not runtime.docker_container_name:
                        skipped += 1
                        logger.warning(
                            "Shutdown skipped Redroid Runtime %s: "
                            "docker_container_name is not configured",
                            runtime.id,
                        )
                        continue

                    attempted += 1
                    try:
                        self.runtime_adapter.stop_container(
                            runtime.docker_container_name
                        )
                    except Exception as error:
                        failed += 1
                        logger.error(
                            "Shutdown failed to stop Redroid Runtime %s "
                            "container %s: %s",
                            runtime.id,
                            runtime.docker_container_name,
                            error,
                        )
                        continue

                    runtime.status = "stopped"
                    stopped_runtime_ids.add(runtime.id)
                    affected_device_ids.add(runtime.device_id)
                    logger.info(
                        "Shutdown stopped Redroid Runtime %s container %s",
                        runtime.id,
                        runtime.docker_container_name,
                    )

                for device_id in affected_device_ids:
                    device_runtimes = [
                        runtime
                        for runtime in runtimes
                        if runtime.device_id == device_id
                    ]
                    if device_runtimes:
                        device = device_runtimes[0].device
                        if all(
                            runtime.status == "stopped"
                            for runtime in device.runtimes
                        ):
                            device.status = "offline"

                session.commit()
                logger.info(
                    "Shutdown Redroid cleanup complete: stopped=%s failed=%s "
                    "skipped=%s",
                    len(stopped_runtime_ids),
                    failed,
                    skipped,
                )
        except SQLAlchemyError:
            logger.exception(
                "Shutdown database reconciliation failed after stopping containers"
            )


def stop_managed_devices_on_shutdown_from_environment() -> bool:
    """Read the managed-device shutdown policy, defaulting to enabled."""
    raw_value = os.getenv(STOP_MANAGED_DEVICES_ON_SHUTDOWN, "true")
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise HostConfigurationError(
        f"{STOP_MANAGED_DEVICES_ON_SHUTDOWN} must be a boolean value; "
        f"received {raw_value!r}"
    )
