"""Ownership and secret-boundary tests for the systemd bridge adapter."""

from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from app.services.network_config import RuntimeNetworkSettings
from app.services.network_secrets import SecretValue
from app.services.proxy_bridge import (
    BridgeCredentials,
    BridgeOwnershipConflict,
    BridgeSpec,
)
from app.services.systemd_proxy_bridge import (
    SystemdBridgeError,
    SystemdHostProxyBridgeSupervisor,
)


class FakeSystemdRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.units: dict[str, dict[str, str]] = {}
        self.next_pid = 4100

    def __call__(self, command) -> subprocess.CompletedProcess[str]:
        copied = list(command)
        self.commands.append(copied)
        executable = copied[0]
        if executable == "systemd-run":
            unit = copied[copied.index("--unit") + 1]
            if unit in self.units and self.units[unit]["ActiveState"] == "active":
                return subprocess.CompletedProcess(copied, 1, "", "unit exists")
            description = next(
                copied[index + 1].removeprefix("Description=")
                for index, value in enumerate(copied)
                if value == "--property"
                and copied[index + 1].startswith("Description=")
            )
            self.next_pid += 1
            self.units[unit] = {
                "LoadState": "loaded",
                "ActiveState": "active",
                "Description": description,
                "MainPID": str(self.next_pid),
            }
            return subprocess.CompletedProcess(copied, 0, "", "")
        if executable == "systemctl" and "show" in copied:
            unit = copied[copied.index("show") + 1]
            properties = self.units.get(
                unit,
                {
                    "LoadState": "not-found",
                    "ActiveState": "inactive",
                    "Description": "",
                    "MainPID": "0",
                },
            )
            output = "".join(f"{key}={value}\n" for key, value in properties.items())
            return subprocess.CompletedProcess(copied, 0, output, "")
        if executable == "systemctl" and "stop" in copied:
            unit = copied[-1]
            if unit in self.units:
                self.units[unit]["ActiveState"] = "inactive"
                self.units[unit]["MainPID"] = "0"
            return subprocess.CompletedProcess(copied, 0, "", "")
        raise AssertionError(f"unexpected command shape: {copied!r}")


def settings(tmp_path: Path) -> RuntimeNetworkSettings:
    return RuntimeNetworkSettings(
        lock_directory=tmp_path / "locks",
        bridge_state_directory=tmp_path / "state",
        bridge_python_executable=Path(sys.executable),
        bridge_systemd_scope="user",
    )


def spec(runtime_id: int, owner: str, port: int) -> BridgeSpec:
    return BridgeSpec(
        runtime_id,
        owner,
        "127.0.0.1",
        port,
        "proxy.example.test",
        3128,
        "generic_http",
    )


def supervisor(
    tmp_path: Path, runner: FakeSystemdRunner
) -> SystemdHostProxyBridgeSupervisor:
    result = SystemdHostProxyBridgeSupervisor(
        settings(tmp_path),
        runner=runner,
        readiness_timeout_seconds=0,
        readiness_interval_seconds=0,
    )
    result._process_start_token = lambda pid: f"birth-{pid}"  # type: ignore[method-assign]
    result._pid_owns_listener = lambda pid, host, port: True  # type: ignore[method-assign]
    return result


def test_real_supervisor_is_loopback_idempotent_and_redacts_credentials(
    tmp_path: Path,
) -> None:
    fake_username = "FAKE-USERNAME-MUST-NOT-LEAK"
    fake_password = "FAKE-PASSWORD-MUST-NOT-LEAK"
    runner = FakeSystemdRunner()
    bridge = supervisor(tmp_path, runner)
    bridge_spec = spec(7, "owner-7", 8807)
    credentials = BridgeCredentials(
        SecretValue(fake_username), SecretValue(fake_password)
    )

    first = bridge.ensure_started(bridge_spec, credentials)
    second = bridge.ensure_started(bridge_spec, credentials)

    assert first == second
    assert first.status == "running"
    start_commands = [command for command in runner.commands if command[0] == "systemd-run"]
    assert len(start_commands) == 1
    start = start_commands[0]
    assert start[start.index("--listen-host") + 1] == "127.0.0.1"
    command_text = " ".join(start)
    assert fake_username not in command_text
    assert fake_password not in command_text
    assert not list((tmp_path / "state").glob("*.credential"))
    persisted = "".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "state").glob("*.json")
    )
    assert fake_username not in persisted
    assert fake_password not in persisted
    manifest = tmp_path / "state/runtime-7.json"
    assert stat.S_IMODE(manifest.stat().st_mode) == 0o600


def test_real_supervisor_keeps_two_runtime_units_isolated(tmp_path: Path) -> None:
    runner = FakeSystemdRunner()
    bridge = supervisor(tmp_path, runner)

    first = bridge.ensure_started(spec(7, "owner-7", 8807), BridgeCredentials())
    second = bridge.ensure_started(spec(8, "owner-8", 8808), BridgeCredentials())

    assert first.supervisor_id == "tiktok-manager-network-r7.service"
    assert second.supervisor_id == "tiktok-manager-network-r8.service"
    assert first.pid != second.pid
    assert set(runner.units) == {
        "tiktok-manager-network-r7.service",
        "tiktok-manager-network-r8.service",
    }
    assert bridge.stop(7, "owner-7").status == "stopped"
    assert runner.units["tiktok-manager-network-r8.service"]["ActiveState"] == "active"


def test_real_supervisor_stop_is_idempotent(tmp_path: Path) -> None:
    runner = FakeSystemdRunner()
    bridge = supervisor(tmp_path, runner)
    bridge.ensure_started(spec(7, "owner-7", 8807), BridgeCredentials())

    assert bridge.stop(7, "owner-7").status == "stopped"
    stop_count = sum("stop" in command for command in runner.commands)
    assert bridge.stop(7, "owner-7").status == "stopped"
    assert sum("stop" in command for command in runner.commands) == stop_count


def test_real_supervisor_never_stops_ambiguous_owner(tmp_path: Path) -> None:
    runner = FakeSystemdRunner()
    bridge = supervisor(tmp_path, runner)
    bridge.ensure_started(spec(7, "owner-7", 8807), BridgeCredentials())

    with pytest.raises(BridgeOwnershipConflict, match="BRIDGE_OWNERSHIP_CONFLICT"):
        bridge.stop(7, "different-owner")

    assert not any("stop" in command for command in runner.commands)
    assert runner.units["tiktok-manager-network-r7.service"]["ActiveState"] == "active"


def test_real_supervisor_rejects_changed_fingerprint_without_adoption(
    tmp_path: Path,
) -> None:
    runner = FakeSystemdRunner()
    bridge = supervisor(tmp_path, runner)
    bridge.ensure_started(spec(7, "owner-7", 8807), BridgeCredentials())
    changed = BridgeSpec(
        7,
        "owner-7",
        "127.0.0.1",
        8807,
        "different-proxy.example.test",
        3128,
        "generic_http",
    )

    with pytest.raises(BridgeOwnershipConflict):
        bridge.ensure_started(changed, BridgeCredentials())

    assert len([command for command in runner.commands if command[0] == "systemd-run"]) == 1


def test_real_supervisor_treats_listener_mismatch_as_unhealthy(
    tmp_path: Path,
) -> None:
    runner = FakeSystemdRunner()
    bridge = supervisor(tmp_path, runner)
    bridge._pid_owns_listener = lambda pid, host, port: False  # type: ignore[method-assign]

    with pytest.raises(SystemdBridgeError, match="did not become ready"):
        bridge.ensure_started(spec(7, "owner-7", 8807), BridgeCredentials())


def test_real_supervisor_waits_for_worker_listener_readiness(
    tmp_path: Path,
) -> None:
    runner = FakeSystemdRunner()
    bridge = SystemdHostProxyBridgeSupervisor(
        settings(tmp_path),
        runner=runner,
        readiness_timeout_seconds=1,
        readiness_interval_seconds=0,
    )
    bridge._process_start_token = lambda pid: f"birth-{pid}"  # type: ignore[method-assign]
    observations = iter((False, False, True))
    bridge._pid_owns_listener = (  # type: ignore[method-assign]
        lambda pid, host, port: next(observations)
    )

    observation = bridge.ensure_started(
        spec(7, "owner-7", 8807), BridgeCredentials()
    )

    assert observation.status == "running"


def test_real_supervisor_rejects_tampered_manifest_mode(tmp_path: Path) -> None:
    runner = FakeSystemdRunner()
    bridge = supervisor(tmp_path, runner)
    bridge.ensure_started(spec(7, "owner-7", 8807), BridgeCredentials())
    manifest = tmp_path / "state/runtime-7.json"
    manifest.chmod(0o644)

    with pytest.raises(BridgeOwnershipConflict):
        bridge.inspect(7, "owner-7")


def test_manifest_contains_no_upstream_or_credentials(tmp_path: Path) -> None:
    runner = FakeSystemdRunner()
    bridge = supervisor(tmp_path, runner)
    bridge.ensure_started(spec(7, "owner-7", 8807), BridgeCredentials())
    payload = json.loads(
        (tmp_path / "state/runtime-7.json").read_text(encoding="utf-8")
    )

    assert "upstream_host" not in payload
    assert "username" not in payload
    assert "password" not in payload
