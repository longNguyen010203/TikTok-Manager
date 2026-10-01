"""Local Docker and ADB adapter for Redroid runtimes."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Sequence
from enum import Enum


class _AdbTransportState(Enum):
    DEVICE = "device"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"


class RedroidRuntimeError(RuntimeError):
    """Base exception for Redroid runtime adapter failures."""


class RedroidConfigurationError(RedroidRuntimeError, ValueError):
    """Raised when adapter input or polling configuration is invalid."""


class RedroidCommandError(RedroidRuntimeError):
    """Raised when a Docker or ADB command cannot be completed."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        returncode: int | None = None,
        stdout: str = "",
        stderr: str = "",
        cause: BaseException | None = None,
    ) -> None:
        self.command = tuple(command)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

        command_name = self.command[0]
        if returncode is None:
            message = f"Unable to execute {command_name!r}"
        else:
            detail = stderr.strip() or stdout.strip() or "no command output"
            message = (
                f"{command_name!r} command failed with exit code "
                f"{returncode}: {detail}"
            )
        super().__init__(message)
        self.__cause__ = cause


class RedroidBootTimeoutError(RedroidRuntimeError, TimeoutError):
    """Raised when Android does not finish booting before the deadline."""

    def __init__(
        self,
        container_name: str,
        timeout: float,
        *,
        last_error: RedroidCommandError | None = None,
    ) -> None:
        self.container_name = container_name
        self.timeout = timeout
        self.last_error = last_error
        message = (
            f"Redroid container {container_name!r} did not complete boot "
            f"within {timeout:g} seconds"
        )
        if last_error is not None:
            message = f"{message}; last check failed: {last_error}"
        super().__init__(message)


class RedroidAdbTimeoutError(RedroidRuntimeError, TimeoutError):
    """Raised when ADB does not reach the device state before the deadline."""

    def __init__(self, adb_serial: str, timeout: float) -> None:
        self.adb_serial = adb_serial
        self.timeout = timeout
        super().__init__(
            f"ADB target {adb_serial!r} did not reach device state "
            f"within {timeout:g} seconds"
        )


class RedroidRuntimeAdapter:
    """Control a Redroid container and check its Android/ADB readiness."""

    def __init__(self, *, boot_poll_interval: float = 1.0) -> None:
        if boot_poll_interval <= 0:
            raise RedroidConfigurationError(
                "boot_poll_interval must be greater than zero"
            )
        self.boot_poll_interval = boot_poll_interval

    def get_container_status(self, container_name: str) -> str:
        """Return the Docker container state, such as ``running`` or ``exited``."""
        container_name = self._require_value(container_name, "container_name")
        result = self._run(
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.Status}}",
                container_name,
            ]
        )
        return result.stdout.strip()

    def start_container(self, container_name: str) -> str:
        """Start a Redroid container and return Docker's output."""
        return self._container_action("start", container_name)

    def stop_container(self, container_name: str) -> str:
        """Stop a Redroid container and return Docker's output."""
        return self._container_action("stop", container_name)

    def restart_container(self, container_name: str) -> str:
        """Restart a Redroid container and return Docker's output."""
        return self._container_action("restart", container_name)

    def check_boot(self, container_name: str) -> bool:
        """Return whether Android currently reports a completed boot."""
        container_name = self._require_value(container_name, "container_name")
        result = self._run(
            [
                "docker",
                "exec",
                container_name,
                "getprop",
                "sys.boot_completed",
            ],
            raise_on_nonzero=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "1"

    def wait_for_boot(self, container_name: str, timeout: float) -> bool:
        """Wait until Android reports ``sys.boot_completed=1``.

        A failed ``docker exec`` is treated as a transient not-ready result because
        Docker may accept a start request before the container can execute commands.
        The last command failure is retained on the timeout exception for diagnosis.
        """
        container_name = self._require_value(container_name, "container_name")
        if timeout < 0:
            raise RedroidConfigurationError(
                "timeout must be greater than or equal to zero"
            )

        deadline = time.monotonic() + timeout
        last_error: RedroidCommandError | None = None

        while True:
            try:
                result = self._run(
                    [
                        "docker",
                        "exec",
                        container_name,
                        "getprop",
                        "sys.boot_completed",
                    ]
                )
                last_error = None
                if result.stdout.strip() == "1":
                    return True
            except RedroidCommandError as error:
                last_error = error

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RedroidBootTimeoutError(
                    container_name, timeout, last_error=last_error
                )
            time.sleep(min(self.boot_poll_interval, remaining))

    def check_adb(self, adb_serial: str) -> bool:
        """Return whether ADB reports the target serial in the ``device`` state."""
        adb_serial = self._require_value(adb_serial, "adb_serial")
        return self._get_adb_transport_state(adb_serial) is _AdbTransportState.DEVICE

    def connect_adb(self, adb_serial: str) -> str:
        """Ask the local ADB server to connect to a Redroid target."""
        adb_serial = self._require_value(adb_serial, "adb_serial")
        result = self._run(["adb", "connect", adb_serial])
        return result.stdout.strip()

    def disconnect_adb(self, adb_serial: str) -> str:
        """Remove a possibly stale ADB transport for a Redroid target."""
        adb_serial = self._require_value(adb_serial, "adb_serial")
        result = self._run(["adb", "disconnect", adb_serial])
        return result.stdout.strip()

    def wait_for_adb(self, adb_serial: str, timeout: float) -> bool:
        """Reconnect and wait until ADB reports the target as a device."""
        adb_serial = self._require_value(adb_serial, "adb_serial")
        if timeout < 0:
            raise RedroidConfigurationError(
                "timeout must be greater than or equal to zero"
            )
        transport_state = self._get_adb_transport_state(adb_serial)
        if transport_state is _AdbTransportState.DEVICE:
            return True

        if transport_state is not _AdbTransportState.MISSING:
            self.disconnect_adb(adb_serial)
        self.connect_adb(adb_serial)
        deadline = time.monotonic() + timeout
        while True:
            if self.check_adb(adb_serial):
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RedroidAdbTimeoutError(adb_serial, timeout)
            time.sleep(min(self.boot_poll_interval, remaining))

    def _get_adb_transport_state(self, adb_serial: str) -> _AdbTransportState:
        result = self._run(
            ["adb", "-s", adb_serial, "get-state"], raise_on_nonzero=False
        )
        if result.returncode == 0 and result.stdout.strip() == "device":
            return _AdbTransportState.DEVICE

        output = f"{result.stdout}\n{result.stderr}".lower()
        if "no such device" in output or "not found" in output:
            return _AdbTransportState.MISSING
        return _AdbTransportState.UNAVAILABLE

    def _container_action(self, action: str, container_name: str) -> str:
        container_name = self._require_value(container_name, "container_name")
        result = self._run(["docker", action, container_name])
        return result.stdout.strip()

    @staticmethod
    def _require_value(value: str, name: str) -> str:
        if not value or not value.strip():
            raise RedroidConfigurationError(f"{name} must not be empty")
        return value

    @staticmethod
    def _run(
        command: Sequence[str], *, raise_on_nonzero: bool = True
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                list(command),
                shell=False,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            raise RedroidCommandError(command, cause=error) from error

        if raise_on_nonzero and result.returncode != 0:
            raise RedroidCommandError(
                command,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        return result
