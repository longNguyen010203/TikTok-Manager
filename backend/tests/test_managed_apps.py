"""Managed app admission, inspection, activation, and isolation tests."""

from __future__ import annotations

import io
import stat
import subprocess
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, init_db
from app.models import ContentAsset, ContentBlob, Job, ManagedAppVersion
from app.services.apk_admission import ApkAdmissionError, validate_apk_archive
from app.services.apk_inspection import ApkInspectionError, ApkToolInspector
from app.services.content_operation_lock import ContentVersionOperationGuard
from app.services.content_storage import ContentStorageService
from app.services.managed_app_inspection import ManagedAppInspectionService
from tests.app_factory import create_test_app


def apk_bytes(*, manifest: bool = True, entry_name: str = "classes.dex", payload: bytes = b"dex\n035\x00") -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if manifest:
            archive.writestr("AndroidManifest.xml", b"binary manifest fixture")
        archive.writestr(entry_name, payload)
    return output.getvalue()


@pytest.fixture
def managed_app_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("TIKTOK_MANAGER_CONTENT_ROOT", str(tmp_path / "content"))
    monkeypatch.setenv("TIKTOK_MANAGER_MAX_APK_BYTES", str(2 * 1024 * 1024))
    aapt2 = tmp_path / "api-aapt2"
    apksigner = tmp_path / "api-apksigner"
    aapt2.write_text(
        "#!/bin/sh\nprintf \"package: name='com.example.app' versionCode='9' versionName='9.0'\\nsdkVersion:'23'\\ntargetSdkVersion:'35'\\n\"\n",
        encoding="utf-8",
    )
    apksigner.write_text(
        "#!/bin/sh\nprintf 'Signer #1 certificate SHA-256 digest: " + "ef" * 32 + "\\n'\n",
        encoding="utf-8",
    )
    aapt2.chmod(0o700)
    apksigner.chmod(0o700)
    monkeypatch.setenv("TIKTOK_MANAGER_AAPT2_PATH", str(aapt2))
    monkeypatch.setenv("TIKTOK_MANAGER_APKSIGNER_PATH", str(apksigner))
    database_url = URL.create("sqlite", database=str(tmp_path / "managed-apps.db"))
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    init_db(engine)
    application = create_test_app()
    application.state.managed_app_sessions = sessions

    def override_get_db() -> Iterator[Session]:
        with sessions() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as client:
        yield client
    application.dependency_overrides.clear()
    engine.dispose()


def create_managed_app(client: TestClient, *, key: str = "tiktok", package: str = "com.zhiliaoapp.musically") -> dict:
    response = client.post("/managed-apps", json={
        "key": key, "display_name": key.title(), "android_package_name": package,
        "install_policy": "required",
    })
    assert response.status_code == 201
    return response.json()


def upload_apk(client: TestClient, app_id: int, data: bytes | None = None, *, name: str = "fixture.apk"):
    return client.post(
        f"/managed-apps/{app_id}/versions",
        files={"file": (name, data if data is not None else apk_bytes(), "application/vnd.android.package-archive")},
    )


def test_create_list_patch_and_strict_package_validation(managed_app_api: TestClient) -> None:
    created = create_managed_app(managed_app_api)
    assert created["key"] == "tiktok"
    repeated = managed_app_api.post("/managed-apps", json={
        "key": "tiktok", "display_name": "Tiktok",
        "android_package_name": "com.zhiliaoapp.musically", "install_policy": "required",
    })
    assert repeated.status_code == 201 and repeated.json()["id"] == created["id"]
    invalid = managed_app_api.post("/managed-apps", json={
        "key": "Bad Key", "display_name": "Bad", "android_package_name": "not-package",
        "install_policy": "optional", "command": "anything",
    })
    assert invalid.status_code == 422
    patched = managed_app_api.patch(f"/managed-apps/{created['id']}", json={"status": "disabled"})
    assert patched.status_code == 200 and patched.json()["status"] == "disabled"
    listed = managed_app_api.get("/managed-apps").json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == created["id"]


def test_apk_upload_is_internal_deduplicated_and_hidden_from_library(managed_app_api: TestClient) -> None:
    app = create_managed_app(managed_app_api)
    package = apk_bytes()
    first = upload_apk(managed_app_api, app["id"], package)
    assert first.status_code == 202
    body = first.json()
    assert body["created"] is True and body["version"]["status"] == "inspecting"
    assert body["version"]["inspection_level"] == "basic"
    assert body["version"]["package_verification"] == "post_install"
    assert body["version"]["basic_approved"] is False
    second = upload_apk(managed_app_api, app["id"], package)
    assert second.status_code == 202 and second.json()["created"] is False
    assert second.json()["version"]["id"] == body["version"]["id"]
    assert managed_app_api.get("/content").json()["total"] == 0
    with managed_app_api.app.state.managed_app_sessions() as session:
        asset = session.scalar(select(ContentAsset))
        asset_id = asset.id
        version = session.get(ManagedAppVersion, body["version"]["id"])
        assert asset.purpose == "managed_app_package"
        assert session.scalar(select(func.count()).select_from(ContentBlob)) == 1
        job = session.get(Job, version.inspection_job_id)
        assert job.job_type == "app.inspect" and job.runtime_id is None
    assert managed_app_api.get(f"/content/{asset_id}").status_code == 404
    denied = managed_app_api.post("/jobs", json={
        "job_type": "app.inspect", "payload": {"managed_app_version_id": body["version"]["id"]},
    })
    assert denied.status_code == 422


@pytest.mark.parametrize(
    ("payload", "filename", "code"),
    [
        (b"", "empty.apk", "EMPTY_CONTENT"),
        (b"not a zip", "bad.apk", "APK_INVALID"),
        (apk_bytes(manifest=False), "missing.apk", "APK_MANIFEST_MISSING"),
        (apk_bytes(entry_name="../escape"), "traversal.apk", "APK_INVALID"),
        (apk_bytes(), "wrong.zip", "APK_TYPE_MISMATCH"),
    ],
)
def test_apk_admission_rejections(managed_app_api: TestClient, payload: bytes, filename: str, code: str) -> None:
    app = create_managed_app(managed_app_api)
    response = upload_apk(managed_app_api, app["id"], payload, name=filename)
    assert response.status_code in {422, 503}
    assert response.json()["detail"]["code"] == code


def test_archive_limits() -> None:
    with pytest.raises(ApkAdmissionError, match="structure"):
        validate_apk_archive(io.BytesIO(apk_bytes()), max_entries=1, max_expanded_bytes=10_000, max_compression_ratio=100)
    with pytest.raises(ApkAdmissionError, match="expanded"):
        validate_apk_archive(io.BytesIO(apk_bytes(payload=b"x" * 1000)), max_entries=5, max_expanded_bytes=100, max_compression_ratio=1000)
    with pytest.raises(ApkAdmissionError, match="compression"):
        validate_apk_archive(io.BytesIO(apk_bytes(payload=b"x" * 10_000)), max_entries=5, max_expanded_bytes=20_000, max_compression_ratio=2)
    linked = io.BytesIO()
    with zipfile.ZipFile(linked, "w") as archive:
        archive.writestr("AndroidManifest.xml", b"manifest")
        entry = zipfile.ZipInfo("linked-entry")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(entry, b"target")
    with pytest.raises(ApkAdmissionError, match="structure"):
        validate_apk_archive(io.BytesIO(linked.getvalue()), max_entries=5, max_expanded_bytes=1000, max_compression_ratio=100)


def test_inspector_normalizes_and_uses_argument_arrays(tmp_path: Path) -> None:
    aapt, signer, package = tool_fixture(tmp_path)
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        assert kwargs["shell"] is False
        if command[-1] == "version":
            return subprocess.CompletedProcess(command, 0, b"Android tool 35.0.1\n", b"")
        if command[0] == str(aapt):
            return subprocess.CompletedProcess(command, 0, b"package: name='com.example.app' versionCode='42' versionName='1.2'\nsdkVersion:'23'\ntargetSdkVersion:'35'\n", b"")
        return subprocess.CompletedProcess(command, 0, b"Signer #1 certificate SHA-256 digest: " + b"ab" * 32 + b"\n", b"")

    result = ApkToolInspector(aapt, signer, timeout_seconds=5, max_stdout_bytes=4096, max_stderr_bytes=1024, runner=runner).inspect(package)
    assert result.package_name == "com.example.app"
    assert (result.version_code, result.version_name, result.min_sdk, result.target_sdk) == (42, "1.2", 23, 35)
    assert result.signer_fingerprint == "ab" * 32
    assert result.inspector_version == "aapt2:35.0.1;apksigner:35.0.1"
    assert all(str(package) == call[-1] for call in calls[:2])


def test_inspector_signature_failure_timeout_and_cancellation(tmp_path: Path) -> None:
    aapt, signer, package = tool_fixture(tmp_path)

    def bad_signature(command, **_kwargs):
        if command[-1] == "version":
            return subprocess.CompletedProcess(command, 0, b"35.0.1", b"")
        output = b"package: name='com.example.app' versionCode='1' versionName='1'\n"
        return subprocess.CompletedProcess(command, 0 if command[0] == str(aapt) else 1, output, b"secret raw error")

    with pytest.raises(ApkInspectionError) as invalid:
        ApkToolInspector(aapt, signer, timeout_seconds=5, max_stdout_bytes=4096, max_stderr_bytes=1024, runner=bad_signature).inspect(package)
    assert invalid.value.code == "APK_SIGNATURE_INVALID" and "secret" not in str(invalid.value)

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["tool"], 1, output=b"raw secret")

    with pytest.raises(ApkInspectionError) as timed:
        ApkToolInspector(aapt, signer, timeout_seconds=1, max_stdout_bytes=100, max_stderr_bytes=100, runner=timeout).inspect(package)
    assert timed.value.code == "APK_INSPECTION_TIMEOUT" and timed.value.retryable
    with pytest.raises(ApkInspectionError) as cancelled:
        ApkToolInspector(aapt, signer, timeout_seconds=1, max_stdout_bytes=100, max_stderr_bytes=100, runner=timeout, cancellation_hook=lambda: True).inspect(package)
    assert cancelled.value.code == "APP_INSPECTION_CANCELLED"


def test_ready_activation_and_retirement_safety(managed_app_api: TestClient, tmp_path: Path) -> None:
    app_data = create_managed_app(managed_app_api, key="example", package="com.example.app")
    uploaded = upload_apk(managed_app_api, app_data["id"]).json()["version"]
    aapt, signer, _package = tool_fixture(tmp_path)

    def runner(command, **_kwargs):
        if command[-1] == "version":
            return subprocess.CompletedProcess(command, 0, b"35.0.1", b"")
        if command[0] == str(aapt):
            return subprocess.CompletedProcess(command, 0, b"package: name='com.example.app' versionCode='7' versionName='7.0'\nsdkVersion:'21'\ntargetSdkVersion:'34'\n", b"")
        return subprocess.CompletedProcess(command, 0, b"Signer #1 certificate SHA-256 digest: " + b"cd" * 32, b"")

    with managed_app_api.app.state.managed_app_sessions() as session:
        config_root = Path(managed_app_api.app.state.managed_app_sessions.kw["bind"].url.database).parent
        result = ManagedAppInspectionService(
            session,
            storage=ContentStorageService.from_application_config(),
            guard=ContentVersionOperationGuard(config_root / "app-locks"),
            inspector=ApkToolInspector(aapt, signer, timeout_seconds=5, max_stdout_bytes=4096, max_stderr_bytes=1024, runner=runner),
        ).inspect(uploaded["id"])
        assert result["status"] == "ready"
        assert result["inspection_level"] == "verified"
    activated = managed_app_api.post(f"/managed-apps/{app_data['id']}/versions/{uploaded['id']}/activate")
    assert activated.status_code == 200 and activated.json()["current_version_id"] == uploaded["id"]
    assert managed_app_api.post(f"/managed-apps/{app_data['id']}/versions/{uploaded['id']}/activate").status_code == 200
    assert managed_app_api.post(f"/managed-apps/{app_data['id']}/versions/{uploaded['id']}/retire").status_code == 409

    replacement = upload_apk(
        managed_app_api, app_data["id"], apk_bytes(payload=b"different dex")
    ).json()["version"]

    def changed_signer(command, **_kwargs):
        if command[-1] == "version":
            return subprocess.CompletedProcess(command, 0, b"35.0.1", b"")
        if command[0] == str(aapt):
            return subprocess.CompletedProcess(command, 0, b"package: name='com.example.app' versionCode='8' versionName='8.0'\n", b"")
        return subprocess.CompletedProcess(command, 0, b"Signer #1 certificate SHA-256 digest: " + b"ab" * 32, b"")

    with managed_app_api.app.state.managed_app_sessions() as session:
        with pytest.raises(ApkInspectionError) as mismatch:
            ManagedAppInspectionService(
                session,
                storage=ContentStorageService.from_application_config(),
                guard=ContentVersionOperationGuard(config_root / "app-locks"),
                inspector=ApkToolInspector(aapt, signer, timeout_seconds=5, max_stdout_bytes=4096, max_stderr_bytes=1024, runner=changed_signer),
            ).inspect(replacement["id"])
        assert mismatch.value.code == "APK_SIGNER_MISMATCH"
        assert session.get(ManagedAppVersion, replacement["id"]).status == "invalid"


def test_worker_fenced_app_inspect_execution_boundary(managed_app_api: TestClient) -> None:
    app = create_managed_app(managed_app_api, key="example", package="com.example.app")
    version = upload_apk(managed_app_api, app["id"]).json()["version"]
    claim = managed_app_api.post("/jobs/claim", json={"claimed_by": "managed-app-test"}).json()
    assert claim["job_type"] == "app.inspect" and claim["runtime_id"] is None
    headers = {
        "X-Job-Claim-Token": claim["claim_token"],
        "X-Job-Attempt": str(claim["attempt_count"]),
    }
    executed = managed_app_api.post(f"/jobs/{claim['id']}/execute", headers=headers, json={})
    assert executed.status_code == 200
    result = executed.json()["result"]
    assert result["status"] == "ready"
    assert result["package_name"] == "com.example.app"
    assert result["version_code"] == 9
    succeeded = managed_app_api.post(
        f"/jobs/{claim['id']}/succeed", headers=headers, json={"result": result}
    )
    assert succeeded.status_code == 200
    detail = managed_app_api.get(f"/managed-apps/{app['id']}/versions/{version['id']}").json()
    assert detail["status"] == "ready" and detail["signer_fingerprint"] == "ef" * 32
    assert detail["inspection_level"] == "verified"
    assert detail["package_verification"] == "pre_and_post_install"


def test_inspector_unavailable_can_be_explicitly_basic_approved(
    managed_app_api: TestClient, tmp_path: Path,
) -> None:
    app = create_managed_app(
        managed_app_api, key="controlled", package="com.ss.android.ugc.trill"
    )
    version = upload_apk(managed_app_api, app["id"]).json()["version"]

    with managed_app_api.app.state.managed_app_sessions() as session:
        with pytest.raises(ApkInspectionError) as unavailable:
            ManagedAppInspectionService(
                session,
                storage=ContentStorageService.from_application_config(),
                guard=ContentVersionOperationGuard(tmp_path / "unavailable-locks"),
                inspector=ApkToolInspector(
                    tmp_path / "missing-aapt2",
                    tmp_path / "missing-apksigner",
                    timeout_seconds=5,
                    max_stdout_bytes=4096,
                    max_stderr_bytes=1024,
                ),
            ).inspect(version["id"])
        assert unavailable.value.code == "APK_INSPECTOR_UNAVAILABLE"
        assert session.get(ManagedAppVersion, version["id"]).status == "inspecting"

    # Upload/admission alone never authorizes installation or activation.
    blocked = managed_app_api.post(
        f"/managed-apps/{app['id']}/versions/{version['id']}/activate"
    )
    assert blocked.status_code == 409

    approved = managed_app_api.post(
        f"/managed-apps/{app['id']}/versions/{version['id']}/approve-basic"
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "ready"
    assert body["inspection_level"] == "basic"
    assert body["package_verification"] == "post_install"
    assert body["basic_approved"] is True
    assert body["basic_approved_at"] is not None
    assert body["discovered_package_name"] is None
    assert body["signer_fingerprint"] is None

    repeated = managed_app_api.post(
        f"/managed-apps/{app['id']}/versions/{version['id']}/approve-basic"
    )
    assert repeated.status_code == 200
    activated = managed_app_api.post(
        f"/managed-apps/{app['id']}/versions/{version['id']}/activate"
    )
    assert activated.status_code == 200
    assert activated.json()["current_version_id"] == version["id"]


def test_package_mismatch_is_deterministically_invalid(managed_app_api: TestClient) -> None:
    app = create_managed_app(managed_app_api)
    version = upload_apk(managed_app_api, app["id"]).json()["version"]
    claim = managed_app_api.post("/jobs/claim", json={"claimed_by": "mismatch-test"}).json()
    headers = {
        "X-Job-Claim-Token": claim["claim_token"],
        "X-Job-Attempt": str(claim["attempt_count"]),
    }
    executed = managed_app_api.post(f"/jobs/{claim['id']}/execute", headers=headers, json={})
    assert executed.status_code == 422
    assert executed.json()["detail"]["code"] == "APK_PACKAGE_MISMATCH"
    detail = managed_app_api.get(f"/managed-apps/{app['id']}/versions/{version['id']}").json()
    assert detail["status"] == "invalid"
    assert detail["error_code"] == "APK_PACKAGE_MISMATCH"


def tool_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    aapt = tmp_path / "aapt2"
    signer = tmp_path / "apksigner"
    package = tmp_path / "fixture.apk"
    for tool in (aapt, signer):
        tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        tool.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    package.write_bytes(apk_bytes())
    package.chmod(0o600)
    return aapt, signer, package
