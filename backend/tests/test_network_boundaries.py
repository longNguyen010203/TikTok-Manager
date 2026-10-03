"""Tests for secret, ADB, bridge, and operation-lock boundaries."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

from app.services.android_network import AndroidNetworkAdapter, PROXY_SETTING_KEYS
from app.services.network_operation_lock import NetworkOperationLockBusy, RuntimeNetworkOperationGuard
from app.services.network_secrets import SecretResolutionError, SecretResolver
from app.services.proxy_bridge import (
    BridgeCredentials,
    BridgeSpec,
    FakeHostProxyBridgeSupervisor,
)


class RecordingRunner:
    def __init__(self, outputs: list[str] | None = None) -> None:
        self.commands: list[list[str]] = []
        self.outputs = iter(outputs or [])

    def __call__(self, command) -> subprocess.CompletedProcess[str]:
        copied = list(command)
        self.commands.append(copied)
        return subprocess.CompletedProcess(copied, 0, next(self.outputs, ""), "")


def test_secret_resolver_redacts_value_from_repr_logs_and_errors(monkeypatch, caplog) -> None:
    fake = "FAKE-CREDENTIAL-MUST-NOT-LEAK"
    monkeypatch.setenv("TIKTOK_PROXY_TEST_PASSWORD", fake)
    secret = SecretResolver().resolve("env:TIKTOK_PROXY_TEST_PASSWORD")
    credentials = BridgeCredentials(password=secret)
    with caplog.at_level(logging.INFO):
        logging.getLogger("test").info("credentials=%r secret=%s", credentials, secret)
    assert secret.reveal() == fake
    assert fake not in repr(secret)
    assert fake not in repr(credentials)
    assert fake not in caplog.text

    monkeypatch.delenv("TIKTOK_PROXY_TEST_PASSWORD")
    with pytest.raises(SecretResolutionError) as raised:
        SecretResolver().resolve("env:TIKTOK_PROXY_TEST_PASSWORD")
    assert fake not in str(raised.value)


@pytest.mark.parametrize(
    "reference",
    ["file:/tmp/secret", "env:HOME", "env:TIKTOK_OTHER_SECRET", "env:TIKTOK_PROXY_lower"],
)
def test_secret_resolver_rejects_non_allowlisted_references(reference: str) -> None:
    with pytest.raises(SecretResolutionError):
        SecretResolver().resolve(reference)


def test_android_proxy_commands_always_use_exact_serial_and_clear_all_keys() -> None:
    runner = RecordingRunner()
    adapter = AndroidNetworkAdapter(runner)
    adapter.set_global_http_proxy("localhost:5557", "127.0.0.1", 8888)
    adapter.clear_global_http_proxy("localhost:5557")
    assert all(command[:3] == ["adb", "-s", "localhost:5557"] for command in runner.commands)
    deleted = [command[-1] for command in runner.commands if "delete" in command]
    assert deleted == list(PROXY_SETTING_KEYS)
    assert all("shell=True" not in command for command in runner.commands)


def test_reverse_add_and_remove_require_exact_mapping() -> None:
    runner = RecordingRunner(outputs=["", "localhost:5557 tcp:8888 tcp:8803\n", ""])
    adapter = AndroidNetworkAdapter(runner)
    adapter.add_reverse_rule("localhost:5557", 8888, 8803)
    assert adapter.remove_reverse_rule("localhost:5557", 8888, 8803) is True
    assert runner.commands == [
        ["adb", "-s", "localhost:5557", "reverse", "tcp:8888", "tcp:8803"],
        ["adb", "-s", "localhost:5557", "reverse", "--list"],
        ["adb", "-s", "localhost:5557", "reverse", "--remove", "tcp:8888"],
    ]


def test_reverse_remove_does_not_remove_different_host_mapping() -> None:
    runner = RecordingRunner(outputs=["tcp:8888 tcp:8804\n"])
    assert AndroidNetworkAdapter(runner).remove_reverse_rule("localhost:5557", 8888, 8803) is False
    assert len(runner.commands) == 1


def test_operation_guard_reports_contention(tmp_path: Path) -> None:
    first = RuntimeNetworkOperationGuard(tmp_path / "locks")
    second = RuntimeNetworkOperationGuard(tmp_path / "locks")
    with first.acquire_runtime(42):
        with pytest.raises(NetworkOperationLockBusy):
            with second.acquire_runtime(42, blocking=False):
                pass


def test_fake_bridge_supervisor_is_runtime_and_owner_scoped(monkeypatch) -> None:
    monkeypatch.setenv("TIKTOK_PROXY_TEST_PASSWORD", "fake-password")
    secret = SecretResolver().resolve("env:TIKTOK_PROXY_TEST_PASSWORD")
    supervisor = FakeHostProxyBridgeSupervisor()
    spec = BridgeSpec(7, "owner-a", "127.0.0.1", 8807, "proxy.example", 3128, "generic_http")
    observation = supervisor.ensure_started(spec, BridgeCredentials(password=secret))
    assert observation.status == "running"
    assert supervisor.inspect(7, "owner-a") == observation
    with pytest.raises(RuntimeError, match="ownership conflict"):
        supervisor.stop(7, "owner-b")
    assert supervisor.stop(7, "owner-a").status == "stopped"


def test_bridge_spec_requires_loopback_listener() -> None:
    with pytest.raises(ValueError, match="loopback"):
        BridgeSpec(7, "owner-a", "0.0.0.0", 8807, "proxy.example", 3128, "generic_http")
