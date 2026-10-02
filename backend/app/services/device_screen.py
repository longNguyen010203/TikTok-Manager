"""In-process scrcpy session management for Redroid devices."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from threading import Lock


class DeviceScreenError(RuntimeError):
    """Base exception for scrcpy screen session failures."""


class DeviceScreenCommandError(DeviceScreenError):
    """Raised when scrcpy cannot be launched or terminated."""


@dataclass(frozen=True)
class ScreenProcessState:
    """Current state of a tracked scrcpy child process."""

    device_id: int
    runtime_id: int
    adb_serial: str
    is_open: bool
    process_id: int | None


@dataclass(frozen=True)
class ScreenCleanupFailure:
    """Failure encountered while closing one tracked screen session."""

    device_id: int
    error: str


@dataclass(frozen=True)
class ScreenCleanupResult:
    """Aggregate result from closing every tracked screen session."""

    closed_device_ids: tuple[int, ...]
    failures: tuple[ScreenCleanupFailure, ...]


@dataclass
class _ScreenProcess:
    runtime_id: int
    adb_serial: str
    process: subprocess.Popen[bytes]


class ScreenProcessManager:
    """Launch and track at most one scrcpy process for each Device."""

    def __init__(self, *, terminate_timeout: float = 5.0) -> None:
        self.terminate_timeout = terminate_timeout
        self._processes: dict[int, _ScreenProcess] = {}
        self._lock = Lock()

    def open(
        self, device_id: int, runtime_id: int, adb_serial: str
    ) -> ScreenProcessState:
        """Return an existing live session or launch scrcpy without waiting."""
        with self._lock:
            current = self._get_live_process(device_id)
            if current is not None:
                return self._open_state(device_id, current)

            command = ["scrcpy", "--serial", adb_serial]
            try:
                process = subprocess.Popen(
                    command,
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError as error:
                raise DeviceScreenCommandError(
                    f"Unable to launch scrcpy for ADB target {adb_serial!r}: {error}"
                ) from error

            tracked = _ScreenProcess(
                runtime_id=runtime_id,
                adb_serial=adb_serial,
                process=process,
            )
            self._processes[device_id] = tracked
            return self._open_state(device_id, tracked)

    def close(
        self, device_id: int, runtime_id: int, adb_serial: str
    ) -> ScreenProcessState:
        """Terminate only the tracked scrcpy process for a Device."""
        with self._lock:
            current = self._get_live_process(device_id)
            if current is None:
                return self._closed_state(device_id, runtime_id, adb_serial)

            try:
                current.process.terminate()
                current.process.wait(timeout=self.terminate_timeout)
            except subprocess.TimeoutExpired:
                try:
                    current.process.kill()
                    current.process.wait()
                except OSError as error:
                    raise DeviceScreenCommandError(
                        f"Unable to close scrcpy for Device {device_id}: {error}"
                    ) from error
            except ProcessLookupError:
                pass
            except OSError as error:
                raise DeviceScreenCommandError(
                    f"Unable to close scrcpy for Device {device_id}: {error}"
                ) from error

            self._processes.pop(device_id, None)
            return self._closed_state(device_id, runtime_id, adb_serial)

    def status(
        self, device_id: int, runtime_id: int, adb_serial: str
    ) -> ScreenProcessState:
        """Report whether the Device has a live tracked scrcpy process."""
        with self._lock:
            current = self._get_live_process(device_id)
            if current is None:
                return self._closed_state(device_id, runtime_id, adb_serial)
            return self._open_state(device_id, current)

    def close_all(self) -> ScreenCleanupResult:
        """Close every tracked scrcpy process, continuing after failures."""
        with self._lock:
            tracked_sessions = [
                (device_id, tracked.runtime_id, tracked.adb_serial)
                for device_id, tracked in self._processes.items()
            ]

        closed: list[int] = []
        failures: list[ScreenCleanupFailure] = []
        for device_id, runtime_id, adb_serial in tracked_sessions:
            try:
                self.close(device_id, runtime_id, adb_serial)
                closed.append(device_id)
            except Exception as error:
                failures.append(
                    ScreenCleanupFailure(device_id=device_id, error=str(error))
                )
        return ScreenCleanupResult(
            closed_device_ids=tuple(closed), failures=tuple(failures)
        )

    def _get_live_process(self, device_id: int) -> _ScreenProcess | None:
        tracked = self._processes.get(device_id)
        if tracked is None:
            return None
        if tracked.process.poll() is None:
            return tracked
        self._processes.pop(device_id, None)
        return None

    @staticmethod
    def _open_state(device_id: int, tracked: _ScreenProcess) -> ScreenProcessState:
        return ScreenProcessState(
            device_id=device_id,
            runtime_id=tracked.runtime_id,
            adb_serial=tracked.adb_serial,
            is_open=True,
            process_id=tracked.process.pid,
        )

    @staticmethod
    def _closed_state(
        device_id: int, runtime_id: int, adb_serial: str
    ) -> ScreenProcessState:
        return ScreenProcessState(
            device_id=device_id,
            runtime_id=runtime_id,
            adb_serial=adb_serial,
            is_open=False,
            process_id=None,
        )
