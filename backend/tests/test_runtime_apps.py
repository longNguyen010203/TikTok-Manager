"""Runtime managed-app desired state, ADB safety, and convergence tests."""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import init_db
from app.database import get_db
from app.models import (
    ContentAsset,
    ContentAssetVersion,
    ContentBlob,
    Device,
    Job,
    ManagedApp,
    ManagedAppVersion,
    Runtime,
    RuntimeAppInstallation,
    RuntimeAppInstallationRun,
)
from app.services.adb_executor import AdbExecutor, AdbExecutorError, AdbInstalledPackage
from app.services.android_app_management import AndroidAppManagementService, AppManagementError
from app.services.content_storage import ContentStorageService
from app.services.runtime_apps import RuntimeAppService
from app.services.runtime_apps import RuntimeAppError
from app.services.runtime_operation_lock import RuntimeOperationGuard
from tests.app_factory import create_test_app


class ReadyAdapter:
    def get_container_status(self, _name: str) -> str:
        return "running"

    def connect_adb(self, _serial: str) -> None:
        return None

    def check_boot(self, _container: str) -> bool:
        return True

    def check_adb(self, _serial: str) -> bool:
        return True


class FakeAdb:
    def __init__(self, observed: AdbInstalledPackage | None) -> None:
        self.observed = observed
        self.installs: list[tuple[str, Path]] = []

    def get_boot_completed(self, serial: str) -> bool:
        assert serial == "localhost:7101"
        return True

    def get_state(self, serial: str) -> str:
        assert serial == "localhost:7101"
        return "device"

    def installed_package(self, serial: str, package: str):
        assert serial == "localhost:7101"
        assert package == "com.example.safe"
        return self.observed

    def install_package(self, serial: str, path: Path, *, timeout: float) -> None:
        assert serial == "localhost:7101"
        assert timeout > 0
        assert path.suffix == ".apk"
        assert path.is_file()
        self.installs.append((serial, path))
        self.observed = AdbInstalledPackage(
            package_name="com.example.safe",
            package_path="/data/app/com.example.safe/base.apk",
            version_name="2.0",
            version_code=2,
            enabled=True,
            signer_fingerprint="ab" * 32,
        )


@pytest.fixture
def runtime_app_db(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime-app.db'}")
    init_db(engine)
    with Session(engine, expire_on_commit=False) as session:
        device = Device(
            name="Disposable", device_type="emulator", platform="android",
            os_version="12", status="offline",
        )
        session.add(device); session.flush()
        runtime = Runtime(
            device_id=device.id, name="runtime", runtime_type="redroid",
            docker_container_name="runtime-app-test", adb_serial="localhost:7101",
            status="stopped",
        )
        session.add(runtime); session.flush()
        app = ManagedApp(
            key="safe", display_name="Safe App",
            android_package_name="com.example.safe", status="active",
            install_policy="required",
        )
        session.add(app); session.flush()
        blob_bytes = b"controlled apk fixture"
        digest = hashlib.sha256(blob_bytes).hexdigest()
        blob = ContentBlob(
            storage_key="1" * 32, sha256=digest, size_bytes=len(blob_bytes),
            detected_mime_type="application/vnd.android.package-archive",
            status="active",
        )
        asset = ContentAsset(
            asset_type="other", display_name="fixture.apk", source="upload",
            purpose="managed_app_package", status="ready",
        )
        session.add_all([blob, asset]); session.flush()
        content_version = ContentAssetVersion(
            content_asset_id=asset.id, version_number=1, blob_id=blob.id,
            original_filename="fixture.apk",
            detected_mime_type="application/vnd.android.package-archive",
            canonical_extension=".apk", processing_status="ready",
        )
        session.add(content_version); session.flush()
        version = ManagedAppVersion(
            managed_app_id=app.id, content_asset_id=asset.id,
            content_asset_version_id=content_version.id, version_name="2.0",
            version_code=2, sha256=digest,
            discovered_package_name="com.example.safe",
            signer_fingerprint="ab" * 32, status="ready",
            inspector_name="fixture", inspection_level="verified",
        )
        session.add(version); session.flush()
        app.current_version_id = version.id
        session.commit()
        yield session, runtime, app, version, blob_bytes
    engine.dispose()


def test_required_row_stays_pending_while_runtime_stopped(runtime_app_db) -> None:
    session, runtime, app, version, _ = runtime_app_db
    rows = RuntimeAppService.converge_required(session, runtime.id, schedule=True)
    session.commit()
    assert len(rows) == 1 and rows[0].status == "pending"
    assert rows[0].desired_managed_app_version_id == version.id
    assert session.scalars(select(Job)).all() == []


def test_running_convergence_is_idempotent_and_readiness_is_separate(runtime_app_db) -> None:
    session, runtime, app, version, _ = runtime_app_db
    runtime.status = "running"
    RuntimeAppService.converge_required(session, runtime.id, schedule=True)
    RuntimeAppService.converge_required(session, runtime.id, schedule=True)
    session.commit()
    jobs = list(session.scalars(select(Job)).all())
    runs = list(session.scalars(select(RuntimeAppInstallationRun)).all())
    assert len(jobs) == len(runs) == 1
    assert jobs[0].job_type == "app.install" and jobs[0].runtime_id == runtime.id
    before = RuntimeAppService.readiness(session, runtime, runtime_ready=True)
    assert not before.required_apps_ready and not before.publishing_ready
    row = session.scalar(select(RuntimeAppInstallation))
    row.status = "installed"
    row.observed_managed_app_version_id = version.id
    after = RuntimeAppService.readiness(session, runtime, runtime_ready=True)
    assert after.required_apps_ready and after.publishing_ready


def test_exact_version_is_verify_first_and_does_not_reinstall(runtime_app_db, tmp_path: Path) -> None:
    session, runtime, app, version, blob_bytes = runtime_app_db
    root = tmp_path / "content"
    storage = ContentStorageService(root, max_upload_bytes=1024, max_total_bytes=4096)
    storage.prepare()
    (storage.blobs / ("1" * 32)).write_bytes(blob_bytes)
    (storage.blobs / ("1" * 32)).chmod(0o600)
    observed = AdbInstalledPackage(
        package_name=app.android_package_name,
        package_path="/data/app/com.example.safe/base.apk",
        version_name="2.0", version_code=2, enabled=True,
        signer_fingerprint="ab" * 32,
    )
    adb = FakeAdb(observed)
    service = AndroidAppManagementService(
        session, adb=adb, runtime_adapter=ReadyAdapter(),
        guard=RuntimeOperationGuard(tmp_path / "locks"), storage=storage,
        readiness_timeout=0,
    )
    result = service.install(runtime.id, version.id)
    assert result.installed and not result.changed and adb.installs == []


def test_basic_approval_is_required_and_absent_package_installs_with_post_verify(
    runtime_app_db, tmp_path: Path
) -> None:
    session, runtime, app, version, blob_bytes = runtime_app_db
    version.inspection_level = "basic"
    version.basic_approved_at = None
    version.discovered_package_name = None
    version.version_name = None
    version.version_code = None
    version.signer_fingerprint = None
    session.commit()
    with pytest.raises(RuntimeAppError) as blocked:
        RuntimeAppService.ensure_desired(
            session, runtime_id=runtime.id, app_id=app.id, version_id=version.id
        )
    assert blocked.value.code == "APP_VERSION_NOT_READY"

    from app.models.timestamps import utc_now
    version.basic_approved_at = utc_now()
    session.commit()
    row = RuntimeAppService.ensure_desired(
        session, runtime_id=runtime.id, app_id=app.id, version_id=version.id
    )
    assert row.desired_managed_app_version_id == version.id

    storage = ContentStorageService(
        tmp_path / "basic-content", max_upload_bytes=1024, max_total_bytes=4096
    )
    storage.prepare()
    (storage.blobs / ("1" * 32)).write_bytes(blob_bytes)
    (storage.blobs / ("1" * 32)).chmod(0o600)
    adb = FakeAdb(None)
    result = AndroidAppManagementService(
        session, adb=adb, runtime_adapter=ReadyAdapter(),
        guard=RuntimeOperationGuard(tmp_path / "basic-locks"), storage=storage,
        readiness_timeout=0,
    ).install(runtime.id, version.id)
    assert result.installed and result.changed
    assert result.package_name == app.android_package_name
    assert result.inspection_level == "basic"
    assert result.package_verification == "post_install"
    assert len(adb.installs) == 1


def test_basic_exact_durable_install_is_verify_only(runtime_app_db, tmp_path: Path) -> None:
    session, runtime, app, version, blob_bytes = runtime_app_db
    from app.models.timestamps import utc_now
    version.inspection_level = "basic"
    version.basic_approved_at = utc_now()
    version.discovered_package_name = None
    version.version_code = None
    version.signer_fingerprint = None
    session.commit()
    storage = ContentStorageService(
        tmp_path / "basic-exact", max_upload_bytes=1024, max_total_bytes=4096
    )
    storage.prepare()
    (storage.blobs / ("1" * 32)).write_bytes(blob_bytes)
    (storage.blobs / ("1" * 32)).chmod(0o600)
    observed = AdbInstalledPackage(
        app.android_package_name, "/data/app/com.example.safe/base.apk",
        "2.0", 2, True, None,
    )
    adb = FakeAdb(observed)
    result = AndroidAppManagementService(
        session, adb=adb, runtime_adapter=ReadyAdapter(),
        guard=RuntimeOperationGuard(tmp_path / "basic-exact-locks"), storage=storage,
        readiness_timeout=0,
    ).install(
        runtime.id,
        version.id,
        known_installed=True,
        known_version_name="2.0",
        known_version_code=2,
    )
    assert result.installed and not result.changed and adb.installs == []

    with pytest.raises(AppManagementError) as ambiguous:
        AndroidAppManagementService(
            session, adb=FakeAdb(observed), runtime_adapter=ReadyAdapter(),
            guard=RuntimeOperationGuard(tmp_path / "basic-update-locks"), storage=storage,
            readiness_timeout=0,
        ).install(runtime.id, version.id)
    assert ambiguous.value.code == "APP_BASIC_UPDATE_REQUIRES_VERIFIED"


def test_basic_install_adb_success_without_expected_package_fails(
    runtime_app_db, tmp_path: Path
) -> None:
    session, runtime, _app, version, blob_bytes = runtime_app_db
    from app.models.timestamps import utc_now
    version.inspection_level = "basic"
    version.basic_approved_at = utc_now()
    version.discovered_package_name = None
    version.version_code = None
    session.commit()
    storage = ContentStorageService(
        tmp_path / "wrong-package", max_upload_bytes=1024, max_total_bytes=4096
    )
    storage.prepare()
    (storage.blobs / ("1" * 32)).write_bytes(blob_bytes)
    (storage.blobs / ("1" * 32)).chmod(0o600)

    class WrongPackageAdb(FakeAdb):
        def install_package(self, serial: str, path: Path, *, timeout: float) -> None:
            self.installs.append((serial, path))
            # The APK command succeeded, but the authoritative expected package
            # is still absent (for example, the APK declared another package).
            self.observed = None

    with pytest.raises(AppManagementError) as failed:
        AndroidAppManagementService(
            session, adb=WrongPackageAdb(None), runtime_adapter=ReadyAdapter(),
            guard=RuntimeOperationGuard(tmp_path / "wrong-package-locks"), storage=storage,
            readiness_timeout=0,
        ).install(runtime.id, version.id)
    assert failed.value.code == "APP_PACKAGE_MISMATCH"

    row = RuntimeAppService.ensure_desired(
        session, runtime_id=runtime.id, app_id=version.managed_app_id,
        version_id=version.id,
    )
    row.status = "failed"
    row.error_code = failed.value.code
    readiness = RuntimeAppService.readiness(session, runtime, runtime_ready=True)
    assert not readiness.required_apps_ready and not readiness.publishing_ready


def test_newer_version_and_signer_mismatch_fail_closed(runtime_app_db, tmp_path: Path) -> None:
    session, runtime, _app, version, blob_bytes = runtime_app_db
    root = tmp_path / "content"
    storage = ContentStorageService(root, max_upload_bytes=1024, max_total_bytes=4096)
    storage.prepare()
    (storage.blobs / ("1" * 32)).write_bytes(blob_bytes)
    (storage.blobs / ("1" * 32)).chmod(0o600)
    for observed, code in (
        (AdbInstalledPackage("com.example.safe", "/data/app/x/base.apk", "3.0", 3, True, "ab" * 32), "APP_DOWNGRADE_BLOCKED"),
        (AdbInstalledPackage("com.example.safe", "/data/app/x/base.apk", "2.0", 2, True, "cd" * 32), "APP_SIGNATURE_MISMATCH"),
    ):
        service = AndroidAppManagementService(
            session, adb=FakeAdb(observed), runtime_adapter=ReadyAdapter(),
            guard=RuntimeOperationGuard(tmp_path / f"locks-{code}"), storage=storage,
            readiness_timeout=0,
        )
        with pytest.raises(AppManagementError) as caught:
            service.install(runtime.id, version.id)
        assert caught.value.code == code


def test_adb_install_is_exact_serial_fixed_flags_and_shell_false(tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict]] = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, b"Success\n", b"")

    apk = tmp_path / "fixture.apk"
    apk.write_bytes(b"apk")
    AdbExecutor(runner=runner).install_package("localhost:7101", apk)
    assert calls[0][0] == [
        "adb", "-s", "localhost:7101", "install", "-r", str(apk)
    ]
    assert calls[0][1]["shell"] is False
    assert "-d" not in calls[0][0] and "-g" not in calls[0][0]


def test_adb_install_failure_keeps_safe_internal_diagnostic(
    runtime_app_db, tmp_path: Path
) -> None:
    session, runtime, _app, version, blob_bytes = runtime_app_db
    storage = ContentStorageService(
        tmp_path / "failed-install", max_upload_bytes=1024, max_total_bytes=4096
    )
    storage.prepare()
    (storage.blobs / ("1" * 32)).write_bytes(blob_bytes)
    (storage.blobs / ("1" * 32)).chmod(0o600)

    class FailingAdb(FakeAdb):
        def install_package(self, serial: str, path: Path, *, timeout: float) -> None:
            assert path.suffix == ".apk" and path.is_file()
            raise AdbExecutorError("failed", "ADB automation command failed")

    with pytest.raises(AppManagementError) as failed:
        AndroidAppManagementService(
            session, adb=FailingAdb(None), runtime_adapter=ReadyAdapter(),
            guard=RuntimeOperationGuard(tmp_path / "failed-install-locks"),
            storage=storage, readiness_timeout=0,
        ).install(runtime.id, version.id)
    assert failed.value.code == "APP_INSTALL_FAILED"
    assert failed.value.diagnostic_code == "adb_nonzero_exit"
    assert list(storage.staging.iterdir()) == []


def test_runtime_removal_clears_live_fk_but_preserves_snapshot(runtime_app_db) -> None:
    session, runtime, _app, _version, _ = runtime_app_db
    RuntimeAppService.initialize_required(session, runtime)
    session.commit()
    RuntimeAppService.mark_runtime_removed(session, runtime.id)
    session.commit()
    row = session.scalar(select(RuntimeAppInstallation))
    assert row.runtime_id is None
    assert row.runtime_id_snapshot == runtime.id
    assert row.status == "removed"


def test_runtime_app_api_stopped_intent_and_publishing_readiness(
    runtime_app_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, runtime, app, _version, _ = runtime_app_db
    application = create_test_app()

    def override_get_db() -> Iterator[Session]:
        yield session

    application.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(
        "app.routers.runtime_apps.RedroidRuntimeAdapter", lambda: ReadyAdapter()
    )
    with TestClient(application) as client:
        response = client.post(
            f"/runtimes/{runtime.id}/apps/{app.id}/install", json={}
        )
        assert response.status_code == 202
        assert response.json()["job_id"] is None
        assert response.json()["installation"]["status"] == "pending"
        assert client.get(f"/runtimes/{runtime.id}/apps").json()["items"][0]["managed_app_id"] == app.id
        readiness = client.get(
            f"/runtimes/{runtime.id}/publishing-readiness"
        ).json()
        assert readiness == {
            "runtime_id": runtime.id,
            "runtime_ready": True,
            "required_apps_ready": False,
            "publishing_ready": False,
            "required_count": 1,
            "installed_count": 0,
            "pending_count": 1,
            "failed_count": 0,
            "outdated_count": 0,
        }
        verify = client.post(f"/runtimes/{runtime.id}/apps/{app.id}/verify")
        assert verify.status_code == 409
        assert verify.json()["detail"]["code"] == "RUNTIME_STOPPED"
    application.dependency_overrides.clear()
