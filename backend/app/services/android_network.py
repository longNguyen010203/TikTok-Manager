"""Runtime-scoped Android proxy and ADB reverse primitives."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.services.network_validation import validate_adb_serial, validate_port


PROXY_SETTING_KEYS = (
    "http_proxy",
    "global_http_proxy_host",
    "global_http_proxy_port",
    "global_http_proxy_exclusion_list",
)


class AndroidNetworkCommandError(RuntimeError):
    """Raised for a failed non-secret ADB network command."""


@dataclass(frozen=True)
class AndroidProxySettings:
    http_proxy: str | None
    host: str | None
    port: int | None
    exclusion_list: str | None


@dataclass(frozen=True)
class AdbReverseRule:
    device_port: int
    host_port: int


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


class AndroidNetworkAdapter:
    """Execute only serial-targeted ADB settings and reverse operations."""

    def __init__(self, runner: Runner | None = None) -> None:
        self._runner = runner or self._subprocess_runner

    def get_proxy_settings(self, adb_serial: str) -> AndroidProxySettings:
        values = {
            key: self._normalize_setting(self._run_adb(adb_serial, "shell", "settings", "get", "global", key).stdout)
            for key in PROXY_SETTING_KEYS
        }
        port = None
        if values["global_http_proxy_port"] is not None:
            try:
                port = int(values["global_http_proxy_port"] or "")
            except ValueError:
                port = None
        return AndroidProxySettings(
            http_proxy=values["http_proxy"],
            host=values["global_http_proxy_host"],
            port=port,
            exclusion_list=values["global_http_proxy_exclusion_list"],
        )

    def set_global_http_proxy(self, adb_serial: str, host: str, port: int) -> None:
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Android proxy target must be loopback")
        validate_port(port, "port")
        endpoint = f"{host}:{port}"
        self._run_adb(adb_serial, "shell", "settings", "put", "global", "http_proxy", endpoint)
        self._run_adb(adb_serial, "shell", "settings", "put", "global", "global_http_proxy_host", host)
        self._run_adb(adb_serial, "shell", "settings", "put", "global", "global_http_proxy_port", str(port))

    def clear_global_http_proxy(self, adb_serial: str) -> None:
        for key in PROXY_SETTING_KEYS:
            self._run_adb(adb_serial, "shell", "settings", "delete", "global", key)

    def list_reverse_rules(self, adb_serial: str) -> tuple[AdbReverseRule, ...]:
        output = self._run_adb(adb_serial, "reverse", "--list").stdout
        rules: list[AdbReverseRule] = []
        for line in output.splitlines():
            fields = line.split()
            if len(fields) == 3:
                _, device, host = fields
            elif len(fields) == 2:
                device, host = fields
            else:
                continue
            if not device.startswith("tcp:") or not host.startswith("tcp:"):
                continue
            try:
                rules.append(AdbReverseRule(int(device[4:]), int(host[4:])))
            except ValueError:
                continue
        return tuple(rules)

    def add_reverse_rule(self, adb_serial: str, device_port: int, host_port: int) -> None:
        validate_port(device_port, "device_port")
        validate_port(host_port, "host_port")
        self._run_adb(adb_serial, "reverse", f"tcp:{device_port}", f"tcp:{host_port}")

    def remove_reverse_rule(self, adb_serial: str, device_port: int, host_port: int) -> bool:
        expected = AdbReverseRule(
            validate_port(device_port, "device_port"),
            validate_port(host_port, "host_port"),
        )
        if expected not in self.list_reverse_rules(adb_serial):
            return False
        self._run_adb(adb_serial, "reverse", "--remove", f"tcp:{device_port}")
        return True

    def _run_adb(self, adb_serial: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        serial = validate_adb_serial(adb_serial)
        command = ["adb", "-s", serial, *arguments]
        try:
            result = self._runner(command)
        except OSError as error:
            raise AndroidNetworkCommandError("Unable to execute ADB network command") from error
        if result.returncode != 0:
            raise AndroidNetworkCommandError("ADB network command failed")
        return result

    @staticmethod
    def _subprocess_runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(command),
            shell=False,
            capture_output=True,
            text=True,
            check=False,
        )

    @staticmethod
    def _normalize_setting(value: str) -> str | None:
        normalized = value.strip()
        return None if normalized in {"", "null", "undefined"} else normalized

