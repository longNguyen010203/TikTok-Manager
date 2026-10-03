"""API and orchestration tests for per-Runtime networking."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, init_db
from app.models import Device, Runtime, RuntimeNetworkConfig, RuntimeNetworkConfigRevision, RuntimeNetworkCredential, RuntimeNetworkState
from app.routers.runtime_networks import (
    get_android_network_adapter,
    get_host_proxy_bridge_supervisor,
    get_network_runtime_adapter,
    get_network_credential_provider,
    get_runtime_network_settings,
)
from app.services.android_network import AdbReverseRule, AndroidNetworkCommandError, AndroidProxySettings
from app.services.network_config import RuntimeNetworkSettings
from app.services.network_operation_lock import RuntimeNetworkOperationGuard
from app.services.network_credentials import MasterKeyManager, NetworkCredentialProvider
from app.services.network_secrets import SecretResolver
from app.services.proxy_bridge import (
    BridgeOwnershipConflict,
    FakeHostProxyBridgeSupervisor,
)
from app.services.runtime_network_orchestration import RuntimeNetworkRecoveryCoordinator
from tests.app_factory import create_test_app


class FakeAndroidNetwork:
    def __init__(self) -> None:
        self.settings: dict[str, AndroidProxySettings] = {}
        self.rules: dict[str, set[AdbReverseRule]] = {}
        self.calls: list[tuple] = []
        self.fail = False
        self.on_set = None

    def _check(self) -> None:
        if self.fail:
            raise AndroidNetworkCommandError("sensitive raw adb output")

    def get_proxy_settings(self, serial: str) -> AndroidProxySettings:
        self._check(); self.calls.append(("get", serial))
        return self.settings.get(serial, AndroidProxySettings(None, None, None, None))

    def set_global_http_proxy(self, serial: str, host: str, port: int) -> None:
        self._check(); self.calls.append(("set", serial, host, port))
        self.settings[serial] = AndroidProxySettings(f"{host}:{port}", host, port, None)
        if self.on_set:
            self.on_set()

    def clear_global_http_proxy(self, serial: str) -> None:
        self._check(); self.calls.append(("clear", serial))
        self.settings[serial] = AndroidProxySettings(None, None, None, None)

    def list_reverse_rules(self, serial: str) -> tuple[AdbReverseRule, ...]:
        self._check(); self.calls.append(("list", serial))
        return tuple(self.rules.get(serial, set()))

    def add_reverse_rule(self, serial: str, device_port: int, host_port: int) -> None:
        self._check(); self.calls.append(("add", serial, device_port, host_port))
        self.rules.setdefault(serial, set()).add(AdbReverseRule(device_port, host_port))

    def remove_reverse_rule(self, serial: str, device_port: int, host_port: int) -> bool:
        self._check(); self.calls.append(("remove", serial, device_port, host_port))
        rule = AdbReverseRule(device_port, host_port)
        present = rule in self.rules.get(serial, set())
        self.rules.setdefault(serial, set()).discard(rule)
        return present


class FakeRuntimeReadiness:
    def __init__(self) -> None:
        self.container_status = "running"
        self.boot = True
        self.adb = True
        self.calls: list[tuple[str, str]] = []

    def get_container_status(self, name: str) -> str:
        self.calls.append(("container", name)); return self.container_status
    def check_boot(self, name: str) -> bool:
        self.calls.append(("boot", name)); return self.boot
    def check_adb(self, serial: str) -> bool:
        self.calls.append(("adb", serial)); return self.adb


class FailingBridge(FakeHostProxyBridgeSupervisor):
    def ensure_started(self, spec, credentials):
        raise RuntimeError("credential must never be exposed")


class ConflictedBridge(FakeHostProxyBridgeSupervisor):
    def ensure_started(self, spec, credentials):
        raise BridgeOwnershipConflict("BRIDGE_OWNERSHIP_CONFLICT")


class CapturingBridge(FakeHostProxyBridgeSupervisor):
    def __init__(self) -> None:
        super().__init__()
        self.resolved_credentials: tuple[str | None, str | None] | None = None

    def ensure_started(self, spec, credentials):
        self.resolved_credentials = (
            credentials.username.reveal() if credentials.username else None,
            credentials.password.reveal() if credentials.password else None,
        )
        return super().ensure_started(spec, credentials)


@dataclass
class NetworkApiEnvironment:
    client: TestClient
    factory: sessionmaker[Session]
    android: FakeAndroidNetwork
    runtime_adapter: FakeRuntimeReadiness
    bridge: CapturingBridge
    settings: RuntimeNetworkSettings
    credential_provider: NetworkCredentialProvider


@pytest.fixture
def network_api(tmp_path: Path, monkeypatch) -> Iterator[NetworkApiEnvironment]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'network-api.db'}",
        connect_args={"check_same_thread": False},
    )
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    init_db(engine)
    app = create_test_app()
    android = FakeAndroidNetwork()
    runtime_adapter = FakeRuntimeReadiness()
    bridge = CapturingBridge()
    credential_provider = NetworkCredentialProvider(
        MasterKeyManager(tmp_path / "credentials.key")
    )
    settings = RuntimeNetworkSettings(
        bridge_port_start=19800,
        bridge_port_end=19820,
        bridge_device_port=18888,
        lock_directory=tmp_path / "locks",
    )
    monkeypatch.setenv("TIKTOK_PROXY_API_USERNAME", "fake-user-secret")
    monkeypatch.setenv("TIKTOK_PROXY_API_PASSWORD", "fake-password-secret")

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_android_network_adapter] = lambda: android
    app.dependency_overrides[get_network_runtime_adapter] = lambda: runtime_adapter
    app.dependency_overrides[get_host_proxy_bridge_supervisor] = lambda: bridge
    app.dependency_overrides[get_runtime_network_settings] = lambda: settings
    app.dependency_overrides[get_network_credential_provider] = lambda: credential_provider
    try:
        with TestClient(app) as client:
            yield NetworkApiEnvironment(
                client,
                factory,
                android,
                runtime_adapter,
                bridge,
                settings,
                credential_provider,
            )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def add_runtime(environment: NetworkApiEnvironment, suffix: int, *, status: str = "running") -> int:
    with environment.factory() as session:
        device = Device(
            name=f"Device {suffix}", device_type="emulator", platform="android",
            os_version="12", status="online" if status == "running" else "offline",
        )
        runtime = Runtime(
            name=f"Runtime {suffix}", runtime_type="redroid", status=status,
            docker_container_name=f"redroid-device-{suffix:02d}",
            adb_serial=f"localhost:{5554 + suffix}",
        )
        device.runtimes.append(runtime)
        session.add(device); session.commit()
        return runtime.id


def proxy_payload(expected_revision: int = 0) -> dict[str, object]:
    return {
        "mode": "http_proxy",
        "proxy_host": "proxy.example.net",
        "proxy_port": 3128,
        "proxy_username_secret_ref": "env:TIKTOK_PROXY_API_USERNAME",
        "proxy_password_secret_ref": "env:TIKTOK_PROXY_API_PASSWORD",
        "expected_revision": expected_revision,
    }


def assert_redacted(response) -> None:
    text = response.text
    assert "fake-user-secret" not in text
    assert "fake-password-secret" not in text
    assert "env:TIKTOK_PROXY" not in text
    assert "bridge_owner_token" not in text


def test_get_unmanaged_legacy_runtime(network_api: NetworkApiEnvironment) -> None:
    runtime_id = add_runtime(network_api, 1, status="stopped")
    response = network_api.client.get(f"/runtimes/{runtime_id}/network")
    assert response.status_code == 200
    assert response.json()["managed"] is False
    assert response.json()["desired_revision"] == 0


def test_put_first_direct_and_http_proxy_are_desired_only(network_api: NetworkApiEnvironment) -> None:
    direct_id = add_runtime(network_api, 2, status="stopped")
    direct = network_api.client.put(
        f"/runtimes/{direct_id}/network",
        json={"mode": "direct", "expected_revision": 0},
    )
    assert direct.status_code == 200
    assert direct.json()["status"] == "disabled"

    proxy_id = add_runtime(network_api, 3, status="stopped")
    proxy = network_api.client.put(
        f"/runtimes/{proxy_id}/network", json=proxy_payload()
    )
    assert proxy.status_code == 200
    assert proxy.json()["status"] == "pending"
    assert proxy.json()["credentials"] == {
        "username_configured": True, "password_configured": True
    }
    assert network_api.android.calls == []
    assert network_api.bridge._bridges == {}
    assert_redacted(proxy)


def test_plaintext_credentials_are_encrypted_redacted_and_resolved_for_bridge(
    network_api: NetworkApiEnvironment,
) -> None:
    username = "phase6b-user-plaintext"
    password = "phase6b-password-plaintext"
    runtime_id = add_runtime(network_api, 20)

    response = network_api.client.put(
        f"/runtimes/{runtime_id}/network",
        json={
            "mode": "http_proxy",
            "proxy_host": "proxy.example.net",
            "proxy_port": 3128,
            "username": username,
            "password": password,
            "expected_revision": 0,
        },
    )

    assert response.status_code == 200
    assert response.json()["credentials"] == {
        "username_configured": True,
        "password_configured": True,
    }
    assert username not in response.text
    assert password not in response.text
    with network_api.factory() as session:
        config = session.scalar(
            select(RuntimeNetworkConfig).where(
                RuntimeNetworkConfig.runtime_id == runtime_id
            )
        )
        stored = session.get(RuntimeNetworkCredential, runtime_id)
        assert config.credential_source == "stored_encrypted"
        assert config.proxy_username_secret_ref is None
        assert config.proxy_password_secret_ref is None
        assert stored.encrypted_username != username.encode()
        assert stored.encrypted_password != password.encode()
    database_path = Path(network_api.factory.kw["bind"].url.database)
    database_bytes = database_path.read_bytes()
    assert username.encode() not in database_bytes
    assert password.encode() not in database_bytes

    applied = network_api.client.post(f"/runtimes/{runtime_id}/network/apply")
    assert applied.status_code == 200
    assert network_api.bridge.resolved_credentials == (username, password)
    assert username not in applied.text
    assert password not in applied.text


def test_retain_replace_and_clear_stored_credentials(
    network_api: NetworkApiEnvironment,
) -> None:
    runtime_id = add_runtime(network_api, 21, status="stopped")
    first = network_api.client.put(
        f"/runtimes/{runtime_id}/network",
        json={
            "mode": "http_proxy",
            "proxy_host": "one.example.net",
            "proxy_port": 3128,
            "username": "first-user",
            "password": "first-password",
            "expected_revision": 0,
        },
    )
    assert first.status_code == 200
    with network_api.factory() as session:
        initial_ciphertext = session.get(
            RuntimeNetworkCredential, runtime_id
        ).encrypted_password

    retained = network_api.client.put(
        f"/runtimes/{runtime_id}/network",
        json={
            "mode": "http_proxy",
            "proxy_host": "two.example.net",
            "proxy_port": 8080,
            "credential_action": "retain",
            "expected_revision": 1,
        },
    )
    assert retained.status_code == 200
    with network_api.factory() as session:
        assert (
            session.get(RuntimeNetworkCredential, runtime_id).encrypted_password
            == initial_ciphertext
        )

    replaced = network_api.client.put(
        f"/runtimes/{runtime_id}/network",
        json={
            "mode": "http_proxy",
            "proxy_host": "two.example.net",
            "proxy_port": 8080,
            "credential_action": "replace",
            "username": "second-user",
            "password": "second-password",
            "expected_revision": 2,
        },
    )
    assert replaced.status_code == 200
    with network_api.factory() as session:
        config = session.scalar(
            select(RuntimeNetworkConfig).where(
                RuntimeNetworkConfig.runtime_id == runtime_id
            )
        )
        resolved = network_api.credential_provider.resolve(session, config)
        assert resolved.username.reveal() == "second-user"
        assert resolved.password.reveal() == "second-password"

    cleared = network_api.client.put(
        f"/runtimes/{runtime_id}/network",
        json={
            "mode": "http_proxy",
            "proxy_host": "two.example.net",
            "proxy_port": 8080,
            "credential_action": "clear",
            "expected_revision": 3,
        },
    )
    assert cleared.status_code == 200
    assert cleared.json()["credentials"] == {
        "username_configured": False,
        "password_configured": False,
    }
    with network_api.factory() as session:
        assert session.get(RuntimeNetworkCredential, runtime_id) is None
        config = session.scalar(
            select(RuntimeNetworkConfig).where(
                RuntimeNetworkConfig.runtime_id == runtime_id
            )
        )
        assert config.credential_source == "none"


def test_credential_write_rejects_ambiguous_partial_or_empty_values(
    network_api: NetworkApiEnvironment,
) -> None:
    runtime_id = add_runtime(network_api, 22, status="stopped")
    for credentials in (
        {"username": "only-user"},
        {"username": "", "password": "secret"},
        {"credential_action": "replace"},
        {"credential_action": "clear", "username": "user", "password": "secret"},
    ):
        response = network_api.client.put(
            f"/runtimes/{runtime_id}/network",
            json={
                "mode": "http_proxy",
                "proxy_host": "proxy.example.net",
                "proxy_port": 3128,
                "expected_revision": 0,
                **credentials,
            },
        )
        assert response.status_code == 422
        assert "secret" not in response.text


def test_expected_revision_conflict_is_safe(network_api: NetworkApiEnvironment) -> None:
    runtime_id = add_runtime(network_api, 4, status="stopped")
    network_api.client.put(f"/runtimes/{runtime_id}/network", json=proxy_payload())
    response = network_api.client.put(
        f"/runtimes/{runtime_id}/network", json=proxy_payload(0)
    )
    assert response.status_code == 409
    assert_redacted(response)


def test_apply_http_proxy_uses_exact_serial_and_fake_bridge(network_api: NetworkApiEnvironment) -> None:
    runtime_id = add_runtime(network_api, 5)
    network_api.client.put(f"/runtimes/{runtime_id}/network", json=proxy_payload())
    response = network_api.client.post(f"/runtimes/{runtime_id}/network/apply")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["applied_revision"] == 1
    assert all(call[1] == "localhost:5559" for call in network_api.android.calls)
    assert_redacted(response)


def test_apply_direct_clears_all_state(network_api: NetworkApiEnvironment) -> None:
    runtime_id = add_runtime(network_api, 6)
    network_api.client.put(
        f"/runtimes/{runtime_id}/network",
        json={"mode": "direct", "expected_revision": 0},
    )
    response = network_api.client.post(f"/runtimes/{runtime_id}/network/apply")
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    assert ("clear", "localhost:5560") in network_api.android.calls


def test_clear_running_and_stopped_are_idempotent(network_api: NetworkApiEnvironment) -> None:
    running = add_runtime(network_api, 7)
    network_api.client.put(f"/runtimes/{running}/network", json=proxy_payload())
    network_api.client.post(f"/runtimes/{running}/network/apply")
    cleared = network_api.client.post(f"/runtimes/{running}/network/clear")
    assert cleared.status_code == 200
    assert cleared.json()["mode"] == "direct"
    assert cleared.json()["status"] == "disabled"
    repeated = network_api.client.post(f"/runtimes/{running}/network/clear")
    assert repeated.status_code == 200

    stopped = add_runtime(network_api, 8, status="stopped")
    network_api.client.put(f"/runtimes/{stopped}/network", json=proxy_payload())
    call_count = len(network_api.android.calls)
    pending = network_api.client.post(f"/runtimes/{stopped}/network/clear")
    assert pending.status_code == 200
    assert pending.json()["mode"] == "direct"
    assert pending.json()["status"] == "pending"
    assert len(network_api.android.calls) == call_count


def test_apply_failure_does_not_change_lifecycle_state(network_api: NetworkApiEnvironment) -> None:
    runtime_id = add_runtime(network_api, 9)
    network_api.client.put(f"/runtimes/{runtime_id}/network", json=proxy_payload())
    network_api.android.fail = True
    response = network_api.client.post(f"/runtimes/{runtime_id}/network/apply")
    assert response.status_code == 502
    with network_api.factory() as session:
        runtime = session.get(Runtime, runtime_id)
        assert runtime.status == "running"
        assert runtime.device.status == "online"
    assert_redacted(response)


def test_adb_readiness_failure_is_502_and_preserves_lifecycle(network_api) -> None:
    runtime_id = add_runtime(network_api, 15)
    network_api.client.put(f"/runtimes/{runtime_id}/network", json=proxy_payload())
    network_api.runtime_adapter.adb = False
    response = network_api.client.post(f"/runtimes/{runtime_id}/network/apply")
    assert response.status_code == 502
    with network_api.factory() as session:
        assert session.get(Runtime, runtime_id).status == "running"
        assert session.get(RuntimeNetworkState, runtime_id).error_code == "ADB_UNAVAILABLE"


def test_missing_secret_and_bridge_failure_are_sanitized(network_api, monkeypatch) -> None:
    missing_id = add_runtime(network_api, 10)
    network_api.client.put(f"/runtimes/{missing_id}/network", json=proxy_payload())
    monkeypatch.delenv("TIKTOK_PROXY_API_PASSWORD")
    missing = network_api.client.post(f"/runtimes/{missing_id}/network/apply")
    assert missing.status_code == 503
    assert_redacted(missing)

    bridge_id = add_runtime(network_api, 11)
    network_api.client.put(
        f"/runtimes/{bridge_id}/network",
        json={**proxy_payload(), "proxy_password_secret_ref": None},
    )
    app = network_api.client.app
    app.dependency_overrides[get_host_proxy_bridge_supervisor] = lambda: FailingBridge()
    failed = network_api.client.post(f"/runtimes/{bridge_id}/network/apply")
    assert failed.status_code == 502
    assert "credential" not in failed.text
    assert_redacted(failed)


def test_ambiguous_bridge_ownership_uses_stable_error_and_preserves_runtime(
    network_api: NetworkApiEnvironment,
) -> None:
    runtime_id = add_runtime(network_api, 19)
    network_api.client.put(f"/runtimes/{runtime_id}/network", json=proxy_payload())
    network_api.client.app.dependency_overrides[
        get_host_proxy_bridge_supervisor
    ] = lambda: ConflictedBridge()

    response = network_api.client.post(f"/runtimes/{runtime_id}/network/apply")

    assert response.status_code == 502
    with network_api.factory() as session:
        assert (
            session.get(RuntimeNetworkState, runtime_id).error_code
            == "BRIDGE_OWNERSHIP_CONFLICT"
        )
        assert session.get(Runtime, runtime_id).status == "running"
    assert_redacted(response)


def test_duplicate_apply_lock_contention(network_api: NetworkApiEnvironment) -> None:
    runtime_id = add_runtime(network_api, 12)
    network_api.client.put(f"/runtimes/{runtime_id}/network", json=proxy_payload())
    guard = RuntimeNetworkOperationGuard(network_api.settings.lock_directory)
    with guard.acquire_runtime(runtime_id):
        response = network_api.client.post(f"/runtimes/{runtime_id}/network/apply")
    assert response.status_code == 409


def test_revision_race_never_marks_old_revision_ready(network_api: NetworkApiEnvironment) -> None:
    runtime_id = add_runtime(network_api, 13)
    network_api.client.put(f"/runtimes/{runtime_id}/network", json=proxy_payload())

    def race() -> None:
        network_api.android.on_set = None
        with network_api.factory() as session:
            config = session.scalar(select(RuntimeNetworkConfig).where(RuntimeNetworkConfig.runtime_id == runtime_id))
            config.desired_revision = 2
            session.add(RuntimeNetworkConfigRevision(
                runtime_id=runtime_id, revision=2, mode="http_proxy",
                proxy_host=config.proxy_host, proxy_port=config.proxy_port,
                proxy_username_secret_ref=config.proxy_username_secret_ref,
                proxy_password_secret_ref=config.proxy_password_secret_ref,
                credential_source=config.credential_source,
                bridge_host_port=config.bridge_host_port,
                bridge_device_port=config.bridge_device_port,
            ))
            session.get(RuntimeNetworkState, runtime_id).desired_revision = 2
            session.commit()

    network_api.android.on_set = race
    response = network_api.client.post(f"/runtimes/{runtime_id}/network/apply")
    assert response.status_code == 409
    with network_api.factory() as session:
        state = session.get(RuntimeNetworkState, runtime_id)
        assert state.status == "pending"
        assert state.desired_revision == 2
        assert state.applied_revision != 1


def test_status_response_contains_safe_checks(network_api: NetworkApiEnvironment) -> None:
    runtime_id = add_runtime(network_api, 14, status="stopped")
    response = network_api.client.get(f"/runtimes/{runtime_id}/network/status")
    assert response.status_code == 200
    assert response.json()["checks"]["connectivity"] == "not_run"
    assert_redacted(response)


def test_runtime_delete_uses_network_cleanup_and_cascades(network_api) -> None:
    runtime_id = add_runtime(network_api, 16)
    network_api.client.put(
        f"/runtimes/{runtime_id}/network",
        json={"mode": "direct", "expected_revision": 0},
    )
    response = network_api.client.delete(f"/runtimes/{runtime_id}")
    assert response.status_code == 204
    assert ("clear", "localhost:5570") in network_api.android.calls
    with network_api.factory() as session:
        assert session.get(Runtime, runtime_id) is None
        assert session.get(RuntimeNetworkState, runtime_id) is None


def test_manager_restart_recovery_restores_missing_ephemeral_state(
    network_api: NetworkApiEnvironment,
) -> None:
    runtime_id = add_runtime(network_api, 17)
    network_api.client.put(f"/runtimes/{runtime_id}/network", json=proxy_payload())
    assert network_api.client.post(
        f"/runtimes/{runtime_id}/network/apply"
    ).status_code == 200
    serial = "localhost:5571"
    network_api.android.settings[serial] = AndroidProxySettings(
        "127.0.0.1:19999", "127.0.0.1", 19999, None
    )
    network_api.android.rules[serial] = set()

    RuntimeNetworkRecoveryCoordinator(
        network_api.factory,
        runtime_adapter=network_api.runtime_adapter,
        android_adapter=network_api.android,
        bridge_supervisor=network_api.bridge,
        secret_resolver=SecretResolver(),
        guard=RuntimeNetworkOperationGuard(network_api.settings.lock_directory),
    ).reconcile_startup()

    with network_api.factory() as session:
        config = session.scalar(
            select(RuntimeNetworkConfig).where(
                RuntimeNetworkConfig.runtime_id == runtime_id
            )
        )
        state = session.get(RuntimeNetworkState, runtime_id)
        assert state.status == "ready"
        assert state.applied_revision == config.desired_revision
        expected = AdbReverseRule(
            config.bridge_device_port, config.bridge_host_port
        )
    assert network_api.android.settings[serial].port == 18888
    assert expected in network_api.android.rules[serial]
    assert len(network_api.bridge._bridges) == 1


def test_manager_restart_does_not_start_stopped_runtime_and_stops_owned_bridge(
    network_api: NetworkApiEnvironment,
) -> None:
    runtime_id = add_runtime(network_api, 18)
    network_api.client.put(f"/runtimes/{runtime_id}/network", json=proxy_payload())
    network_api.client.post(f"/runtimes/{runtime_id}/network/apply")
    with network_api.factory() as session:
        session.get(Runtime, runtime_id).status = "stopped"
        session.commit()
    previous_android_calls = len(network_api.android.calls)

    RuntimeNetworkRecoveryCoordinator(
        network_api.factory,
        runtime_adapter=network_api.runtime_adapter,
        android_adapter=network_api.android,
        bridge_supervisor=network_api.bridge,
        secret_resolver=SecretResolver(),
        guard=RuntimeNetworkOperationGuard(network_api.settings.lock_directory),
    ).reconcile_startup()

    with network_api.factory() as session:
        state = session.get(RuntimeNetworkState, runtime_id)
        assert state.status == "pending"
        assert state.error_code == "RUNTIME_STOPPED"
        assert session.get(Runtime, runtime_id).status == "stopped"
    assert runtime_id not in network_api.bridge._bridges
    assert len(network_api.android.calls) == previous_android_calls
