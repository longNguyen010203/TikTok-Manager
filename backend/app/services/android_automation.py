"""Safe, typed Android automation primitives for exact Redroid Runtimes."""

from __future__ import annotations

import mimetypes
import re
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Protocol, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    RedroidProvisioning,
    Runtime,
    RuntimeNetworkConfig,
    RuntimeNetworkState,
)
from app.schemas.device_automation import (
    ArtifactResult,
    DeviceStateResult,
    FileTransferResult,
    InputActionResult,
    MediaImportResult,
    PackageStateResult,
    ScreenshotResult,
)
from app.services.adb_executor import AdbExecutor, AdbExecutorError
from app.services.automation_artifacts import AutomationArtifactStore
from app.services.automation_errors import AutomationError, automation_error
from app.services.redroid_runtime import RedroidRuntimeAdapter, RedroidRuntimeError
from app.services.runtime_operation_lock import (
    RuntimeOperationGuard,
    RuntimeOperationLockBusy,
)


_PACKAGE_NAME = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$"
)
_INPUT_TEXT = re.compile(r"^[A-Za-z0-9 .,!?@_+\-]{1,256}$")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_REMOTE_ROOT = PurePosixPath("/sdcard/Download/TikTokManager")
_DEPROVISIONING_STATES = {
    "deprovisioning",
    "deprovisioned",
    "deprovision_failed",
}
_KEYEVENTS = {
    "HOME": 3,
    "BACK": 4,
    "ENTER": 66,
    "MENU": 82,
    "APP_SWITCH": 187,
    "DPAD_UP": 19,
    "DPAD_DOWN": 20,
    "DPAD_LEFT": 21,
    "DPAD_RIGHT": 22,
    "DPAD_CENTER": 23,
}


@dataclass(frozen=True)
class RuntimeTarget:
    runtime_id: int
    device_id: int
    adb_serial: str
    docker_container_name: str


@dataclass(frozen=True)
class ManagedFileSource:
    """Backend-resolved file identity; never constructed from request paths."""

    path: Path
    size_bytes: int
    sha256: str
    mime_type: str


class ScreenSessionInspector(Protocol):
    def is_runtime_active(self, runtime_id: int) -> bool: ...


class RuntimeTargetResolver:
    """Reload and validate the trusted DB mapping for an automation target."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def resolve(self, runtime_id: int) -> RuntimeTarget:
        if isinstance(runtime_id, bool) or not isinstance(runtime_id, int) or runtime_id <= 0:
            raise automation_error("RUNTIME_NOT_FOUND")
        self.session.expire_all()
        runtime = self.session.get(Runtime, runtime_id)
        if runtime is None:
            raise automation_error("RUNTIME_NOT_FOUND")
        if (
            runtime.runtime_type != "redroid"
            or not runtime.adb_serial
            or not runtime.docker_container_name
        ):
            raise automation_error("DEVICE_NOT_READY")
        provisioning_state = self.session.scalar(
            select(RedroidProvisioning.state).where(
                RedroidProvisioning.runtime_id == runtime_id
            )
        )
        if provisioning_state in _DEPROVISIONING_STATES:
            raise automation_error("RUNTIME_DEPROVISIONING")
        return RuntimeTarget(
            runtime_id=runtime.id,
            device_id=runtime.device_id,
            adb_serial=runtime.adb_serial,
            docker_container_name=runtime.docker_container_name,
        )


class AutomationReadinessService:
    """Inspect container, boot, ADB, provisioning, and screen readiness."""

    def __init__(
        self,
        runtime_adapter: RedroidRuntimeAdapter,
        adb: AdbExecutor,
        *,
        screen_inspector: ScreenSessionInspector | None = None,
        wait_timeout: float = 30.0,
        poll_interval: float = 0.5,
        event_callback: Callable[[str], None] | None = None,
    ) -> None:
        if wait_timeout < 0 or poll_interval <= 0:
            raise ValueError("readiness timing values are invalid")
        self.runtime_adapter = runtime_adapter
        self.adb = adb
        self.screen_inspector = screen_inspector
        self.wait_timeout = wait_timeout
        self.poll_interval = poll_interval
        self.event_callback = event_callback

    def wait_until_ready(self, target: RuntimeTarget) -> DeviceStateResult:
        if self.screen_inspector is not None and self.screen_inspector.is_runtime_active(
            target.runtime_id
        ):
            raise automation_error("RUNTIME_SCREEN_ACTIVE")
        try:
            container_status = self.runtime_adapter.get_container_status(
                target.docker_container_name
            )
        except RedroidRuntimeError as error:
            raise automation_error("DEVICE_NOT_READY", retryable=True) from error
        if container_status != "running":
            if container_status in {"created", "dead", "exited", "removing", "stopped"}:
                raise automation_error("RUNTIME_STOPPED")
            raise automation_error("DEVICE_NOT_READY", retryable=True)

        deadline = time.monotonic() + self.wait_timeout
        boot_completed = False
        adb_state = "unavailable"
        last_adb_error: AdbExecutorError | None = None
        connect_attempted = False
        while True:
            try:
                boot_completed = self.adb.get_boot_completed(target.adb_serial)
                adb_state = self.adb.get_state(target.adb_serial)
                last_adb_error = None
                if boot_completed and adb_state == "device":
                    return DeviceStateResult(
                        runtime_id=target.runtime_id,
                        container_status=container_status,
                        boot_completed=True,
                        adb_state="device",
                        ready=True,
                    )
            except AdbExecutorError as error:
                if error.kind == "cancelled":
                    raise automation_error("AUTOMATION_CANCELLED") from error
                last_adb_error = error
                if not connect_attempted:
                    connect_attempted = True
                    try:
                        self.runtime_adapter.connect_adb(target.adb_serial)
                    except RedroidRuntimeError:
                        pass
                    else:
                        continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if last_adb_error is not None or adb_state != "device":
                    raise automation_error("ADB_UNAVAILABLE", retryable=True)
                raise automation_error("DEVICE_NOT_READY", retryable=True)
            time.sleep(min(self.poll_interval, remaining))


def require_network_ready(
    session: Session,
    runtime_id: int,
    *,
    requires_network: bool,
    allow_unmanaged_direct: bool = False,
) -> None:
    """Validate network intent only for handlers that explicitly require it."""
    if not requires_network:
        return
    config = session.scalar(
        select(RuntimeNetworkConfig).where(RuntimeNetworkConfig.runtime_id == runtime_id)
    )
    if config is None:
        if allow_unmanaged_direct:
            return
        raise automation_error("DEVICE_NOT_READY", retryable=True)
    state = session.get(RuntimeNetworkState, runtime_id)
    if state is None or state.desired_revision != config.desired_revision:
        raise automation_error("DEVICE_NOT_READY", retryable=True)
    if config.mode == "direct":
        if state.status == "disabled" and state.applied_revision == config.desired_revision:
            return
    elif (
        config.mode == "http_proxy"
        and state.status == "ready"
        and state.applied_revision == config.desired_revision
    ):
        return
    raise automation_error("DEVICE_NOT_READY", retryable=True)


ResultT = TypeVar("ResultT")


class AndroidAutomationService:
    """Execute validated primitives without exposing arbitrary ADB or shell access."""

    def __init__(
        self,
        session: Session,
        *,
        adb: AdbExecutor,
        runtime_adapter: RedroidRuntimeAdapter,
        guard: RuntimeOperationGuard,
        artifacts: AutomationArtifactStore,
        screen_inspector: ScreenSessionInspector | None = None,
        readiness_timeout: float = 30.0,
        lock_timeout: float = 0,
        media_poll_timeout: float = 10.0,
        launch_observation_timeout: float = 2.0,
        poll_interval: float = 0.5,
        event_callback: Callable[[str], None] | None = None,
    ) -> None:
        if lock_timeout < 0 or media_poll_timeout < 0 or launch_observation_timeout < 0:
            raise ValueError("automation timeout values are invalid")
        self.session = session
        self.adb = adb
        self.guard = guard
        self.artifacts = artifacts
        self.resolver = RuntimeTargetResolver(session)
        self.readiness = AutomationReadinessService(
            runtime_adapter,
            adb,
            screen_inspector=screen_inspector,
            wait_timeout=readiness_timeout,
            poll_interval=poll_interval,
        )
        self.lock_timeout = lock_timeout
        self.media_poll_timeout = media_poll_timeout
        self.launch_observation_timeout = launch_observation_timeout
        self.poll_interval = poll_interval
        self.event_callback = event_callback

    def get_device_state(self, runtime_id: int) -> DeviceStateResult:
        return self._with_ready_target(runtime_id, lambda _target, state: state)

    def get_package_state(self, runtime_id: int, package_name: str) -> PackageStateResult:
        package = self._validate_package_name(package_name)

        def operation(target: RuntimeTarget, _state: DeviceStateResult) -> PackageStateResult:
            installed = self.adb.package_path(target.adb_serial, package) is not None
            pid = self.adb.package_pid(target.adb_serial, package) if installed else None
            return PackageStateResult(
                runtime_id=target.runtime_id,
                package_name=package,
                installed=installed,
                running=pid is not None,
                pid=pid,
            )

        return self._with_ready_target(runtime_id, operation)

    def launch_package(self, runtime_id: int, package_name: str) -> PackageStateResult:
        package = self._validate_package_name(package_name)

        def operation(target: RuntimeTarget, _state: DeviceStateResult) -> PackageStateResult:
            self._require_installed(target, package)
            self.adb.launch_package(target.adb_serial, package)
            pid = self._wait_for_package_pid(target.adb_serial, package)
            return PackageStateResult(
                runtime_id=target.runtime_id,
                package_name=package,
                installed=True,
                running=pid is not None,
                pid=pid,
            )

        return self._with_ready_target(runtime_id, operation)

    def _wait_for_package_pid(self, serial: str, package_name: str) -> int | None:
        deadline = time.monotonic() + self.launch_observation_timeout
        while True:
            pid = self.adb.package_pid(serial, package_name)
            if pid is not None:
                return pid
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            time.sleep(min(self.poll_interval, remaining))

    def force_stop_package(self, runtime_id: int, package_name: str) -> PackageStateResult:
        package = self._validate_package_name(package_name)

        def operation(target: RuntimeTarget, _state: DeviceStateResult) -> PackageStateResult:
            self._require_installed(target, package)
            self.adb.force_stop_package(target.adb_serial, package)
            pid = self.adb.package_pid(target.adb_serial, package)
            return PackageStateResult(
                runtime_id=target.runtime_id,
                package_name=package,
                installed=True,
                running=pid is not None,
                pid=pid,
            )

        return self._with_ready_target(runtime_id, operation)

    def capture_screenshot(
        self, runtime_id: int, *, job_id: int | None = None
    ) -> ScreenshotResult:
        def operation(target: RuntimeTarget, _state: DeviceStateResult) -> ScreenshotResult:
            data = self.adb.capture_screenshot(target.adb_serial)
            width, height = self._parse_png_dimensions(data)
            artifact = self.artifacts.store_bytes(
                self.session,
                data=data,
                kind="screenshot",
                original_filename=f"runtime-{target.runtime_id}-screenshot.png",
                mime_type="image/png",
                job_id=job_id,
            )
            return ScreenshotResult(
                runtime_id=target.runtime_id,
                artifact_id=artifact.id,
                kind=artifact.kind,
                filename=artifact.original_filename,
                mime_type=artifact.mime_type,
                size_bytes=artifact.size_bytes,
                sha256=artifact.sha256,
                width=width,
                height=height,
            )

        return self._with_ready_target(runtime_id, operation)

    def push_artifact(
        self,
        runtime_id: int,
        artifact_id: int,
        *,
        filename: str | None = None,
    ) -> FileTransferResult:
        def operation(target: RuntimeTarget, _state: DeviceStateResult) -> FileTransferResult:
            artifact = self.artifacts.get(self.session, artifact_id)
            local_path = self.artifacts.path_for(artifact)
            remote_name = self.artifacts.normalize_filename(
                filename or artifact.original_filename
            )
            remote_path = str(_REMOTE_ROOT / remote_name)
            try:
                self.adb.ensure_managed_remote_directory(target.adb_serial)
                self.adb.push(target.adb_serial, local_path, remote_path)
                remote_size = self.adb.remote_file_size(target.adb_serial, remote_path)
            except AdbExecutorError as error:
                if error.kind == "cancelled":
                    raise automation_error("AUTOMATION_CANCELLED") from error
                raise automation_error("FILE_TRANSFER_FAILED", retryable=True) from error
            if remote_size != artifact.size_bytes:
                raise automation_error("FILE_TRANSFER_FAILED", retryable=True)
            return FileTransferResult(
                runtime_id=target.runtime_id,
                artifact_id=artifact.id,
                remote_path=remote_path,
                filename=remote_name,
                size_bytes=artifact.size_bytes,
                sha256=artifact.sha256,
            )

        return self._with_ready_target(runtime_id, operation)

    def pull_file(
        self,
        runtime_id: int,
        remote_path: str,
        *,
        job_id: int | None = None,
    ) -> ArtifactResult:
        safe_path = self._validate_remote_path(remote_path)

        def operation(target: RuntimeTarget, _state: DeviceStateResult) -> ArtifactResult:
            try:
                with self.artifacts.staging_path() as staging:
                    self.adb.pull(target.adb_serial, safe_path, staging)
                    data = self.artifacts.read_staged(staging)
            except AutomationError:
                raise
            except AdbExecutorError as error:
                if error.kind == "cancelled":
                    raise automation_error("AUTOMATION_CANCELLED") from error
                raise automation_error("FILE_TRANSFER_FAILED", retryable=True) from error
            mime_type = mimetypes.guess_type(PurePosixPath(safe_path).name)[0] or "application/octet-stream"
            artifact = self.artifacts.store_bytes(
                self.session,
                data=data,
                kind="device_file",
                original_filename=PurePosixPath(safe_path).name,
                mime_type=mime_type,
                job_id=job_id,
            )
            return ArtifactResult(
                runtime_id=target.runtime_id,
                artifact_id=artifact.id,
                kind=artifact.kind,
                filename=artifact.original_filename,
                mime_type=artifact.mime_type,
                size_bytes=artifact.size_bytes,
                sha256=artifact.sha256,
            )

        return self._with_ready_target(runtime_id, operation)

    def import_media(
        self,
        runtime_id: int,
        artifact_id: int,
        *,
        filename: str | None = None,
    ) -> MediaImportResult:
        def operation(target: RuntimeTarget, _state: DeviceStateResult) -> MediaImportResult:
            artifact = self.artifacts.get(self.session, artifact_id)
            if not (
                artifact.mime_type.startswith("image/")
                or artifact.mime_type.startswith("video/")
            ):
                raise automation_error("ARTIFACT_POLICY_VIOLATION")
            local_path = self.artifacts.path_for(artifact)
            remote_name = self.artifacts.normalize_filename(
                filename or artifact.original_filename
            )
            remote_path = str(_REMOTE_ROOT / remote_name)
            try:
                self.adb.ensure_managed_remote_directory(target.adb_serial)
                self.adb.push(target.adb_serial, local_path, remote_path)
                if self.adb.remote_file_size(target.adb_serial, remote_path) != artifact.size_bytes:
                    raise automation_error("MEDIA_IMPORT_FAILED", retryable=True)
                self.adb.scan_media(target.adb_serial, remote_path)
                media_id = self._wait_for_media(target.adb_serial, remote_name)
            except AutomationError:
                raise
            except AdbExecutorError as error:
                if error.kind == "cancelled":
                    raise automation_error("AUTOMATION_CANCELLED") from error
                raise automation_error("MEDIA_IMPORT_FAILED", retryable=True) from error
            if media_id is None:
                raise automation_error("MEDIA_IMPORT_FAILED", retryable=True)
            return MediaImportResult(
                runtime_id=target.runtime_id,
                artifact_id=artifact.id,
                remote_path=remote_path,
                filename=remote_name,
                size_bytes=artifact.size_bytes,
                sha256=artifact.sha256,
                media_imported=True,
                media_uri=f"content://media/external/file/{media_id}",
            )

        return self._with_ready_target(runtime_id, operation)

    def deliver_managed_file(
        self,
        runtime_id: int,
        source: ManagedFileSource,
        *,
        filename: str,
        import_media: bool,
    ) -> dict[str, object]:
        """Push one trusted managed source to the fixed manager directory."""
        remote_name = self.artifacts.normalize_filename(filename)
        remote_path = str(_REMOTE_ROOT / remote_name)
        if source.size_bytes <= 0 or len(source.sha256) != 64:
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        if import_media and not source.mime_type.startswith(("image/", "video/", "audio/")):
            raise automation_error("ARTIFACT_POLICY_VIOLATION")

        def operation(target: RuntimeTarget, _state: DeviceStateResult) -> dict[str, object]:
            try:
                self.adb.ensure_managed_remote_directory(target.adb_serial)
                self.adb.push(target.adb_serial, source.path, remote_path)
                remote_size = self.adb.remote_file_size(target.adb_serial, remote_path)
                if remote_size != source.size_bytes:
                    raise automation_error("FILE_TRANSFER_FAILED", retryable=True)
                media_uri = None
                if import_media:
                    self.adb.scan_media(target.adb_serial, remote_path)
                    media_id = self._wait_for_media(target.adb_serial, remote_name)
                    if media_id is None:
                        raise automation_error("MEDIA_IMPORT_FAILED", retryable=True)
                    media_uri = f"content://media/external/file/{media_id}"
            except AutomationError:
                raise
            except AdbExecutorError as error:
                if error.kind == "cancelled":
                    raise automation_error("AUTOMATION_CANCELLED") from error
                raise automation_error(
                    "MEDIA_IMPORT_FAILED" if import_media else "FILE_TRANSFER_FAILED",
                    retryable=True,
                ) from error
            return {
                "runtime_id": target.runtime_id,
                "remote_path": remote_path,
                "filename": remote_name,
                "size_bytes": source.size_bytes,
                "sha256": source.sha256,
                "media_imported": import_media,
                "media_uri": media_uri,
            }

        return self._with_ready_target(runtime_id, operation)

    def tap(self, runtime_id: int, x: int, y: int) -> InputActionResult:
        def operation(target: RuntimeTarget, _state: DeviceStateResult) -> InputActionResult:
            self._validate_coordinates(target, ((x, y),))
            self.adb.tap(target.adb_serial, x, y)
            return InputActionResult(runtime_id=target.runtime_id, action="tap")

        return self._with_ready_target(runtime_id, operation)

    def swipe(
        self,
        runtime_id: int,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int,
    ) -> InputActionResult:
        if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or not 50 <= duration_ms <= 5000:
            raise automation_error("INVALID_AUTOMATION_PAYLOAD")

        def operation(target: RuntimeTarget, _state: DeviceStateResult) -> InputActionResult:
            self._validate_coordinates(target, ((x1, y1), (x2, y2)))
            self.adb.swipe(target.adb_serial, x1, y1, x2, y2, duration_ms)
            return InputActionResult(runtime_id=target.runtime_id, action="swipe")

        return self._with_ready_target(runtime_id, operation)

    def input_text(self, runtime_id: int, text: str) -> InputActionResult:
        if not isinstance(text, str) or not _INPUT_TEXT.fullmatch(text):
            raise automation_error("INVALID_AUTOMATION_PAYLOAD")
        encoded = text.replace(" ", "%s")

        def operation(target: RuntimeTarget, _state: DeviceStateResult) -> InputActionResult:
            self.adb.input_text(target.adb_serial, encoded)
            return InputActionResult(runtime_id=target.runtime_id, action="input_text")

        return self._with_ready_target(runtime_id, operation)

    def keyevent(self, runtime_id: int, key: str) -> InputActionResult:
        if not isinstance(key, str) or key not in _KEYEVENTS:
            raise automation_error("INVALID_AUTOMATION_PAYLOAD")

        def operation(target: RuntimeTarget, _state: DeviceStateResult) -> InputActionResult:
            self.adb.keyevent(target.adb_serial, _KEYEVENTS[key])
            return InputActionResult(runtime_id=target.runtime_id, action="keyevent")

        return self._with_ready_target(runtime_id, operation)

    def _with_ready_target(self, runtime_id: int, operation):
        try:
            with self.guard.acquire_runtime(runtime_id, timeout=self.lock_timeout):
                if self.event_callback:
                    self.event_callback("runtime_lock_acquired")
                target = self.resolver.resolve(runtime_id)
                if self.event_callback:
                    self.event_callback("runtime_validated")
                state = self.readiness.wait_until_ready(target)
                if self.event_callback:
                    self.event_callback("adb_ready")
                try:
                    return operation(target, state)
                except AdbExecutorError as error:
                    raise self._translate_adb_error(error) from error
        except RuntimeOperationLockBusy as error:
            raise automation_error("RUNTIME_BUSY", retryable=True) from error
        except ValueError as error:
            raise automation_error("INVALID_AUTOMATION_PAYLOAD") from error

    def _require_installed(self, target: RuntimeTarget, package_name: str) -> None:
        if self.adb.package_path(target.adb_serial, package_name) is None:
            raise automation_error("PACKAGE_NOT_FOUND")

    def _validate_coordinates(
        self, target: RuntimeTarget, coordinates: tuple[tuple[int, int], ...]
    ) -> None:
        width, height = self.adb.display_size(target.adb_serial)
        for x, y in coordinates:
            if (
                isinstance(x, bool)
                or isinstance(y, bool)
                or not isinstance(x, int)
                or not isinstance(y, int)
                or not 0 <= x < width
                or not 0 <= y < height
            ):
                raise automation_error("INVALID_AUTOMATION_PAYLOAD")

    def _wait_for_media(self, serial: str, display_name: str) -> int | None:
        deadline = time.monotonic() + self.media_poll_timeout
        while True:
            media_id = self.adb.find_media_id(serial, display_name)
            if media_id is not None:
                return media_id
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            time.sleep(min(self.poll_interval, remaining))

    @staticmethod
    def _validate_package_name(package_name: str) -> str:
        if (
            not isinstance(package_name, str)
            or len(package_name) > 255
            or not _PACKAGE_NAME.fullmatch(package_name)
        ):
            raise automation_error("INVALID_AUTOMATION_PAYLOAD")
        return package_name

    @staticmethod
    def _validate_remote_path(remote_path: str) -> str:
        if not isinstance(remote_path, str) or "\\" in remote_path or "\x00" in remote_path:
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        candidate = PurePosixPath(remote_path)
        if (
            not candidate.is_absolute()
            or ".." in candidate.parts
            or candidate.parent != _REMOTE_ROOT
            or candidate.name in {"", ".", ".."}
        ):
            raise automation_error("ARTIFACT_POLICY_VIOLATION")
        AutomationArtifactStore.normalize_filename(candidate.name)
        return str(candidate)

    @staticmethod
    def _parse_png_dimensions(data: bytes) -> tuple[int, int]:
        if (
            len(data) < 24
            or not data.startswith(_PNG_SIGNATURE)
            or data[12:16] != b"IHDR"
            or int.from_bytes(data[8:12], "big") != 13
        ):
            raise automation_error("ADB_COMMAND_FAILED", retryable=True)
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        if width <= 0 or height <= 0 or width > 32768 or height > 32768:
            raise automation_error("ADB_COMMAND_FAILED", retryable=True)
        return width, height

    @staticmethod
    def _translate_adb_error(error: AdbExecutorError) -> AutomationError:
        if error.kind == "timeout":
            return automation_error("AUTOMATION_TIMEOUT", retryable=True)
        if error.kind == "unavailable":
            return automation_error("ADB_UNAVAILABLE", retryable=True)
        if error.kind == "cancelled":
            return automation_error("AUTOMATION_CANCELLED")
        return automation_error("ADB_COMMAND_FAILED", retryable=True)


class RuntimeAutomationOwnershipProbe:
    """Read-only helper for later deprovision orchestration integration."""

    def __init__(self, guard: RuntimeOperationGuard) -> None:
        self.guard = guard

    def is_busy(self, runtime_id: int) -> bool:
        return self.guard.is_runtime_busy(runtime_id)
