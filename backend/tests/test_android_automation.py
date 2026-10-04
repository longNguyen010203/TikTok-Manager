"""Android automation service, artifact, readiness, and isolation tests."""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.database import init_db
from app.models import (
    Device,
    RedroidProvisioning,
    Runtime,
    RuntimeNetworkConfig,
    RuntimeNetworkState,
)
from app.services.android_automation import (
    AndroidAutomationService,
    ManagedFileSource,
    RuntimeAutomationOwnershipProbe,
    require_network_ready,
)
from app.services.automation_artifacts import AutomationArtifactStore
from app.services.automation_artifacts import ArtifactConfigurationError
from app.services.automation_errors import AutomationError
from app.services.adb_executor import AdbExecutorError
from app.services.runtime_operation_lock import RuntimeOperationGuard


PNG = (
    b"\x89PNG\r\n\x1a\n"
    + (13).to_bytes(4, "big")
    + b"IHDR"
    + (1080).to_bytes(4, "big")
    + (1920).to_bytes(4, "big")
)


class FakeRuntimeAdapter:
    def __init__(self, status: str = "running") -> None:
        self.status = status
        self.containers: list[str] = []
        self.connected: list[str] = []

    def get_container_status(self, container_name: str) -> str:
        self.containers.append(container_name)
        return self.status

    def connect_adb(self, adb_serial: str) -> str:
        self.connected.append(adb_serial)
        return "connected"


class FakeAdb:
    def __init__(self) -> None:
        self.serials: list[str] = []
        self.installed: set[str] = {"com.android.settings"}
        self.pid: int | None = None
        self.remote_size: int | None = None
        self.commands: list[tuple] = []
        self.boot_completed = True
        self.adb_state = "device"

    def _serial(self, serial: str) -> None:
        self.serials.append(serial)

    def get_boot_completed(self, serial: str) -> bool:
        self._serial(serial)
        return self.boot_completed

    def get_state(self, serial: str) -> str:
        self._serial(serial)
        return self.adb_state

    def package_path(self, serial: str, package: str) -> str | None:
        self._serial(serial)
        return f"/data/app/{package}.apk" if package in self.installed else None

    def package_pid(self, serial: str, package: str) -> int | None:
        self._serial(serial)
        return self.pid

    def launch_package(self, serial: str, package: str) -> None:
        self._serial(serial)
        self.commands.append(("launch", package))
        self.pid = 4321

    def force_stop_package(self, serial: str, package: str) -> None:
        self._serial(serial)
        self.commands.append(("stop", package))
        self.pid = None

    def capture_screenshot(self, serial: str) -> bytes:
        self._serial(serial)
        return PNG

    def ensure_managed_remote_directory(self, serial: str) -> None:
        self._serial(serial)

    def push(self, serial: str, local_path: Path, remote_path: str) -> None:
        self._serial(serial)
        self.commands.append(("push", remote_path))
        self.remote_size = local_path.stat().st_size

    def pull(self, serial: str, remote_path: str, local_path: Path) -> None:
        self._serial(serial)
        self.commands.append(("pull", remote_path))
        local_path.write_bytes(b"pulled")

    def remote_file_size(self, serial: str, remote_path: str) -> int | None:
        self._serial(serial)
        return self.remote_size

    def scan_media(self, serial: str, remote_path: str) -> None:
        self._serial(serial)
        self.commands.append(("scan", remote_path))

    def find_media_id(self, serial: str, display_name: str) -> int | None:
        self._serial(serial)
        return 71

    def display_size(self, serial: str) -> tuple[int, int]:
        self._serial(serial)
        return 1080, 1920

    def tap(self, serial: str, x: int, y: int) -> None:
        self._serial(serial)
        self.commands.append(("tap", x, y))

    def swipe(self, serial: str, *values: int) -> None:
        self._serial(serial)
        self.commands.append(("swipe", *values))

    def input_text(self, serial: str, text: str) -> None:
        self._serial(serial)
        self.commands.append(("text", text))

    def keyevent(self, serial: str, keycode: int) -> None:
        self._serial(serial)
        self.commands.append(("key", keycode))


class FakeScreen:
    def __init__(self, active: bool = False) -> None:
        self.active = active

    def is_runtime_active(self, runtime_id: int) -> bool:
        return self.active


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    result = create_engine(f"sqlite:///{tmp_path / 'automation.db'}")
    init_db(result)
    yield result
    result.dispose()


def add_runtime(session: Session, suffix: str = "01") -> Runtime:
    device = Device(
        name=f"Device {suffix}",
        device_type="emulator",
        platform="android",
        os_version="12",
        status="online",
    )
    runtime = Runtime(
        name=f"Runtime {suffix}",
        runtime_type="redroid",
        docker_container_name=f"redroid-{suffix}",
        adb_serial=f"localhost:55{suffix}",
        status="running",
    )
    device.runtimes.append(runtime)
    session.add(device)
    session.commit()
    return runtime


def make_service(
    session: Session,
    tmp_path: Path,
    *,
    adb: FakeAdb | None = None,
    adapter: FakeRuntimeAdapter | None = None,
    screen: FakeScreen | None = None,
    guard: RuntimeOperationGuard | None = None,
) -> tuple[AndroidAutomationService, FakeAdb, AutomationArtifactStore]:
    fake_adb = adb or FakeAdb()
    store = AutomationArtifactStore(tmp_path / "artifacts", max_size_bytes=1024 * 1024)
    service = AndroidAutomationService(
        session,
        adb=fake_adb,
        runtime_adapter=adapter or FakeRuntimeAdapter(),
        guard=guard or RuntimeOperationGuard(tmp_path / "locks"),
        artifacts=store,
        screen_inspector=screen,
        readiness_timeout=0,
        lock_timeout=0,
        media_poll_timeout=0,
        poll_interval=0.001,
    )
    return service, fake_adb, store


def assert_code(error: pytest.ExceptionInfo[AutomationError], code: str) -> None:
    assert error.value.code == code
    assert str(error.value) == error.value.safe_message


def test_package_state_launch_stop_and_exact_runtime_isolation(
    engine: Engine, tmp_path: Path
) -> None:
    with Session(engine, expire_on_commit=False) as session:
        target = add_runtime(session, "01")
        control = add_runtime(session, "02")
        service, adb, _ = make_service(session, tmp_path)
        state = service.get_package_state(target.id, "com.android.settings")
        launched = service.launch_package(target.id, "com.android.settings")
        stopped = service.force_stop_package(target.id, "com.android.settings")
        assert state.installed and not state.running
        assert launched.running and launched.pid == 4321
        assert not stopped.running
        assert set(adb.serials) == {target.adb_serial}
        assert control.adb_serial not in adb.serials


def test_managed_content_source_push_and_media_import_use_exact_runtime(
    engine: Engine, tmp_path: Path
) -> None:
    with Session(engine, expire_on_commit=False) as session:
        target = add_runtime(session, "21")
        control = add_runtime(session, "22")
        source_path = tmp_path / "managed-content"
        source_path.write_bytes(b"safe-content")
        source = ManagedFileSource(
            path=source_path,
            size_bytes=len(b"safe-content"),
            sha256="a" * 64,
            mime_type="image/png",
        )
        service, adb, _ = make_service(session, tmp_path)
        result = service.deliver_managed_file(
            target.id, source, filename="asset-d1.png", import_media=True
        )
        assert result["remote_path"] == "/sdcard/Download/TikTokManager/asset-d1.png"
        assert result["media_uri"] == "content://media/external/file/71"
        assert ("push", result["remote_path"]) in adb.commands
        assert ("scan", result["remote_path"]) in adb.commands
        assert set(adb.serials) == {target.adb_serial}
        assert control.adb_serial not in adb.serials


@pytest.mark.parametrize(
    "package",
    ["", "settings", "com.android.settings;id", "com.android.$unsafe"],
)
def test_package_name_validation(engine: Engine, tmp_path: Path, package: str) -> None:
    with Session(engine) as session:
        runtime = add_runtime(session)
        service, _, _ = make_service(session, tmp_path)
        with pytest.raises(AutomationError) as raised:
            service.get_package_state(runtime.id, package)
        assert_code(raised, "INVALID_AUTOMATION_PAYLOAD")


def test_missing_package_is_typed(engine: Engine, tmp_path: Path) -> None:
    with Session(engine) as session:
        runtime = add_runtime(session)
        service, _, _ = make_service(session, tmp_path)
        with pytest.raises(AutomationError) as raised:
            service.launch_package(runtime.id, "com.example.missing")
        assert_code(raised, "PACKAGE_NOT_FOUND")


def test_screenshot_validates_png_and_creates_private_artifact(
    engine: Engine, tmp_path: Path
) -> None:
    with Session(engine) as session:
        runtime = add_runtime(session)
        service, _, store = make_service(session, tmp_path)
        result = service.capture_screenshot(runtime.id)
        artifact = store.get(session, result.artifact_id)
        path = store.path_for(artifact)
        assert (result.width, result.height) == (1080, 1920)
        assert path.read_bytes() == PNG
        assert stat.S_IMODE(store.root.stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_invalid_screenshot_is_rejected_without_artifact(
    engine: Engine, tmp_path: Path
) -> None:
    with Session(engine) as session:
        runtime = add_runtime(session)
        adb = FakeAdb()
        adb.capture_screenshot = lambda serial: b"not-png"
        service, _, _ = make_service(session, tmp_path, adb=adb)
        with pytest.raises(AutomationError) as raised:
            service.capture_screenshot(runtime.id)
        assert_code(raised, "ADB_COMMAND_FAILED")


def test_artifact_size_path_and_symlink_policies(engine: Engine, tmp_path: Path) -> None:
    with Session(engine) as session:
        store = AutomationArtifactStore(tmp_path / "artifacts", max_size_bytes=4)
        with pytest.raises(AutomationError) as raised:
            store.store_bytes(
                session,
                data=b"12345",
                kind="file",
                original_filename="large.bin",
                mime_type="application/octet-stream",
            )
        assert_code(raised, "ARTIFACT_POLICY_VIOLATION")
        with pytest.raises(AutomationError):
            store.normalize_filename("../escape.txt")
        artifact = store.store_bytes(
            session,
            data=b"1234",
            kind="file",
            original_filename="safe.txt",
            mime_type="text/plain",
        )
        path = store.path_for(artifact)
        path.unlink()
        path.symlink_to(tmp_path / "foreign")
        with pytest.raises(AutomationError) as symlink_error:
            store.path_for(artifact)
        assert_code(symlink_error, "ARTIFACT_POLICY_VIOLATION")

        real_root = tmp_path / "real-root"
        real_root.mkdir()
        linked_root = tmp_path / "linked-root"
        linked_root.symlink_to(real_root, target_is_directory=True)
        unsafe_store = AutomationArtifactStore(linked_root, max_size_bytes=4)
        with pytest.raises(ArtifactConfigurationError):
            unsafe_store.store_bytes(
                session,
                data=b"1",
                kind="file",
                original_filename="unsafe.txt",
                mime_type="text/plain",
            )


def test_push_requires_artifact_and_restricts_remote_destination(
    engine: Engine, tmp_path: Path
) -> None:
    with Session(engine) as session:
        runtime = add_runtime(session)
        service, adb, store = make_service(session, tmp_path)
        artifact = store.store_bytes(
            session,
            data=b"hello",
            kind="upload",
            original_filename="hello.txt",
            mime_type="text/plain",
        )
        result = service.push_artifact(runtime.id, artifact.id)
        assert result.remote_path == "/sdcard/Download/TikTokManager/hello.txt"
        assert ("push", result.remote_path) in adb.commands
        with pytest.raises(AutomationError) as missing:
            service.push_artifact(runtime.id, 9999)
        assert_code(missing, "ARTIFACT_NOT_FOUND")
        with pytest.raises(AutomationError) as traversal:
            service.push_artifact(runtime.id, artifact.id, filename="../escape")
        assert_code(traversal, "ARTIFACT_POLICY_VIOLATION")


def test_pull_is_restricted_and_becomes_artifact(engine: Engine, tmp_path: Path) -> None:
    with Session(engine) as session:
        runtime = add_runtime(session)
        service, _, store = make_service(session, tmp_path)
        result = service.pull_file(
            runtime.id, "/sdcard/Download/TikTokManager/result.txt"
        )
        assert store.path_for(store.get(session, result.artifact_id)).read_bytes() == b"pulled"
        for unsafe in ("/data/local/tmp/file", "/proc/version", "../result.txt"):
            with pytest.raises(AutomationError) as raised:
                service.pull_file(runtime.id, unsafe)
            assert_code(raised, "ARTIFACT_POLICY_VIOLATION")


def test_media_import_pushes_scans_and_verifies(engine: Engine, tmp_path: Path) -> None:
    with Session(engine) as session:
        runtime = add_runtime(session)
        service, adb, store = make_service(session, tmp_path)
        artifact = store.store_bytes(
            session,
            data=PNG,
            kind="upload",
            original_filename="image.png",
            mime_type="image/png",
        )
        result = service.import_media(runtime.id, artifact.id)
        assert result.media_imported is True
        assert result.media_uri == "content://media/external/file/71"
        assert ("scan", result.remote_path) in adb.commands


def test_runtime_stopped_deprovisioning_busy_and_screen_active(
    engine: Engine, tmp_path: Path
) -> None:
    with Session(engine, expire_on_commit=False) as session:
        runtime = add_runtime(session)
        stopped, _, _ = make_service(
            session, tmp_path / "stopped", adapter=FakeRuntimeAdapter("exited")
        )
        with pytest.raises(AutomationError) as stopped_error:
            stopped.get_device_state(runtime.id)
        assert_code(stopped_error, "RUNTIME_STOPPED")

        provisioning = RedroidProvisioning(
            id="11111111-1111-1111-1111-111111111111",
            idempotency_key="automation-test",
            request_fingerprint="a" * 64,
            ownership_token="22222222-2222-2222-2222-222222222222",
            installation_id="test",
            state="deprovisioning",
            image_reference="redroid:test",
            runtime_id=runtime.id,
        )
        session.add(provisioning)
        session.commit()
        deprovisioning, _, _ = make_service(session, tmp_path / "deprovision")
        with pytest.raises(AutomationError) as deprovision_error:
            deprovisioning.get_device_state(runtime.id)
        assert_code(deprovision_error, "RUNTIME_DEPROVISIONING")
        session.delete(provisioning)
        session.commit()

        active_screen, _, _ = make_service(
            session, tmp_path / "screen", screen=FakeScreen(True)
        )
        with pytest.raises(AutomationError) as screen_error:
            active_screen.get_device_state(runtime.id)
        assert_code(screen_error, "RUNTIME_SCREEN_ACTIVE")

        owner = RuntimeOperationGuard(tmp_path / "busy-lock")
        contender = RuntimeOperationGuard(tmp_path / "busy-lock")
        busy, _, _ = make_service(session, tmp_path / "busy", guard=contender)
        with owner.acquire_runtime(runtime.id):
            assert RuntimeAutomationOwnershipProbe(contender).is_busy(runtime.id)
            with pytest.raises(AutomationError) as busy_error:
                busy.get_device_state(runtime.id)
        assert_code(busy_error, "RUNTIME_BUSY")


def test_temporary_boot_and_adb_readiness_are_typed(
    engine: Engine, tmp_path: Path
) -> None:
    with Session(engine) as session:
        runtime = add_runtime(session)
        booting_adb = FakeAdb()
        booting_adb.boot_completed = False
        booting, _, _ = make_service(session, tmp_path / "booting", adb=booting_adb)
        with pytest.raises(AutomationError) as boot_error:
            booting.get_device_state(runtime.id)
        assert_code(boot_error, "DEVICE_NOT_READY")
        assert boot_error.value.retryable is True

        offline_adb = FakeAdb()
        offline_adb.adb_state = "offline"
        offline, _, _ = make_service(session, tmp_path / "offline", adb=offline_adb)
        with pytest.raises(AutomationError) as adb_error:
            offline.get_device_state(runtime.id)
        assert_code(adb_error, "ADB_UNAVAILABLE")
        assert adb_error.value.retryable is True


def test_readiness_reconnects_exact_serial_after_temporary_adb_loss(
    engine: Engine, tmp_path: Path
) -> None:
    class ReconnectingAdb(FakeAdb):
        def __init__(self) -> None:
            super().__init__()
            self.first = True

        def get_boot_completed(self, serial: str) -> bool:
            self._serial(serial)
            if self.first:
                self.first = False
                raise AdbExecutorError("failed", "ADB automation command failed")
            return True

    with Session(engine) as session:
        runtime = add_runtime(session)
        adapter = FakeRuntimeAdapter()
        service, _, _ = make_service(
            session, tmp_path, adb=ReconnectingAdb(), adapter=adapter
        )
        assert service.get_device_state(runtime.id).ready is True
        assert adapter.connected == [runtime.adb_serial]


def test_cancellation_during_readiness_is_not_retried_as_adb_unavailable(
    engine: Engine, tmp_path: Path
) -> None:
    class CancelledAdb(FakeAdb):
        def get_boot_completed(self, serial: str) -> bool:
            self._serial(serial)
            raise AdbExecutorError("cancelled", "ADB automation command was cancelled")

    with Session(engine) as session:
        runtime = add_runtime(session)
        adapter = FakeRuntimeAdapter()
        service, _, _ = make_service(
            session, tmp_path, adb=CancelledAdb(), adapter=adapter
        )
        with pytest.raises(AutomationError) as cancelled:
            service.get_device_state(runtime.id)
        assert_code(cancelled, "AUTOMATION_CANCELLED")
        assert adapter.connected == []


def test_file_transfer_preserves_cancellation_classification(
    engine: Engine, tmp_path: Path
) -> None:
    class CancelledPushAdb(FakeAdb):
        def push(
            self, serial: str, local_path: Path, remote_path: str
        ) -> None:
            self._serial(serial)
            raise AdbExecutorError("cancelled", "ADB automation command was cancelled")

    with Session(engine) as session:
        runtime = add_runtime(session)
        service, _, store = make_service(session, tmp_path, adb=CancelledPushAdb())
        artifact = store.store_bytes(
            session,
            data=b"test",
            kind="upload",
            original_filename="test.txt",
            mime_type="text/plain",
        )
        with pytest.raises(AutomationError) as cancelled:
            service.push_artifact(runtime.id, artifact.id)
        assert_code(cancelled, "AUTOMATION_CANCELLED")


def test_network_requirement_is_explicit(engine: Engine, tmp_path: Path) -> None:
    with Session(engine) as session:
        runtime = add_runtime(session)
        require_network_ready(session, runtime.id, requires_network=False)
        require_network_ready(
            session,
            runtime.id,
            requires_network=True,
            allow_unmanaged_direct=True,
        )
        with pytest.raises(AutomationError):
            require_network_ready(session, runtime.id, requires_network=True)

        session.add_all(
            [
                RuntimeNetworkConfig(
                    runtime_id=runtime.id, mode="direct", desired_revision=1
                ),
                RuntimeNetworkState(
                    runtime_id=runtime.id,
                    status="disabled",
                    desired_revision=1,
                    applied_revision=1,
                    bridge_status="stopped",
                ),
            ]
        )
        session.commit()
        require_network_ready(session, runtime.id, requires_network=True)

        config = session.get(RuntimeNetworkConfig, 1)
        state = session.get(RuntimeNetworkState, runtime.id)
        assert config is not None and state is not None
        config.mode = "http_proxy"
        config.proxy_host = "proxy.example"
        config.proxy_port = 3128
        config.bridge_host_port = 8800
        config.bridge_device_port = 8888
        state.status = "ready"
        session.commit()
        require_network_ready(session, runtime.id, requires_network=True)
        state.applied_revision = None
        session.commit()
        with pytest.raises(AutomationError):
            require_network_ready(session, runtime.id, requires_network=True)


def test_internal_input_validation_and_commands(engine: Engine, tmp_path: Path) -> None:
    with Session(engine) as session:
        runtime = add_runtime(session)
        service, adb, _ = make_service(session, tmp_path)
        service.tap(runtime.id, 100, 200)
        service.swipe(runtime.id, 100, 200, 300, 400, 250)
        service.input_text(runtime.id, "Hello world-1")
        service.keyevent(runtime.id, "HOME")
        assert ("tap", 100, 200) in adb.commands
        assert ("text", "Hello%sworld-1") in adb.commands
        assert ("key", 3) in adb.commands
        for operation in (
            lambda: service.tap(runtime.id, 1080, 2),
            lambda: service.swipe(runtime.id, 1, 1, 2, 2, 5001),
            lambda: service.input_text(runtime.id, "unsafe;command"),
            lambda: service.keyevent(runtime.id, "POWER"),
        ):
            with pytest.raises(AutomationError) as raised:
                operation()
            assert_code(raised, "INVALID_AUTOMATION_PAYLOAD")
