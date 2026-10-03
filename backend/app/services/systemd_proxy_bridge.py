"""Systemd-backed loopback HTTP proxy bridge supervisor."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from uuid import uuid4

from app.services.network_config import RuntimeNetworkSettings
from app.services.proxy_bridge import (
    BridgeCredentials,
    BridgeObservation,
    BridgeOwnershipConflict,
    BridgeSpec,
    HostProxyBridgeSupervisor,
)


class SystemdBridgeError(RuntimeError):
    pass


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


class SystemdHostProxyBridgeSupervisor(HostProxyBridgeSupervisor):
    """Own transient systemd units through manifest plus live evidence."""

    def __init__(
        self,
        settings: RuntimeNetworkSettings,
        *,
        runner: Runner | None = None,
        worker_path: Path | None = None,
        readiness_timeout_seconds: float = 5.0,
        readiness_interval_seconds: float = 0.05,
    ) -> None:
        self.settings = settings
        self.runner = runner or self._run
        self.worker_path = worker_path or Path(__file__).with_name(
            "http_proxy_bridge_worker.py"
        )
        self.readiness_timeout_seconds = readiness_timeout_seconds
        self.readiness_interval_seconds = readiness_interval_seconds

    def ensure_started(
        self, spec: BridgeSpec, credentials: BridgeCredentials
    ) -> BridgeObservation:
        fingerprint = self._fingerprint(spec)
        manifest = self._read_manifest(spec.runtime_id)
        if manifest is not None:
            if manifest.get("owner_token") != spec.owner_token:
                raise BridgeOwnershipConflict("BRIDGE_OWNERSHIP_CONFLICT")
            if manifest.get("fingerprint") != fingerprint:
                raise BridgeOwnershipConflict("BRIDGE_OWNERSHIP_CONFLICT")
            existing = self.inspect(spec.runtime_id, spec.owner_token)
            if existing.status == "running":
                if manifest.get("process_start_token") is None:
                    self._write_manifest(
                        spec,
                        unit=self._unit_name(spec.runtime_id),
                        fingerprint=fingerprint,
                        process_start_token=existing.process_start_token,
                    )
                return existing
            if existing.status == "unhealthy":
                existing = self._wait_until_ready(
                    spec.runtime_id, spec.owner_token
                )
                if existing.status == "running":
                    self._write_manifest(
                        spec,
                        unit=self._unit_name(spec.runtime_id),
                        fingerprint=fingerprint,
                        process_start_token=existing.process_start_token,
                    )
                    return existing
                raise SystemdBridgeError(
                    "Supervised proxy bridge did not become ready"
                )

        self._validate_executables()
        self._prepare_state_directory()
        unit = self._unit_name(spec.runtime_id)
        credential_path = self.settings.bridge_state_directory / (
            f"runtime-{spec.runtime_id}-{uuid4().hex}.credential"
        )
        self._write_secret_file(credential_path, credentials)
        description = self._description(spec, fingerprint)
        command = [
            "systemd-run",
            *self._scope_arguments(),
            "--unit",
            unit,
            "--collect",
            "--property",
            "Type=simple",
            "--property",
            "Restart=no",
            "--property",
            "NoNewPrivileges=yes",
            "--property",
            "PrivateTmp=yes",
            "--property",
            f"Description={description}",
            "--property",
            f"LoadCredential=proxy:{credential_path}",
            str(self.settings.bridge_python_executable),
            str(self.worker_path),
            "--listen-host",
            spec.loopback_host,
            "--listen-port",
            str(spec.host_port),
            "--upstream-host",
            spec.upstream_host,
            "--upstream-port",
            str(spec.upstream_port),
            "--credential-name",
            "proxy",
        ]
        try:
            result = self.runner(command)
            if result.returncode != 0:
                raise SystemdBridgeError("Unable to start supervised proxy bridge")
            self._write_manifest(
                spec,
                unit=unit,
                fingerprint=fingerprint,
                process_start_token=None,
            )
            observation = self._wait_until_ready(
                spec.runtime_id, spec.owner_token
            )
            if observation.status != "running":
                raise SystemdBridgeError("Supervised proxy bridge did not become ready")
            self._write_manifest(
                spec,
                unit=unit,
                fingerprint=fingerprint,
                process_start_token=observation.process_start_token,
            )
            return observation
        finally:
            self._unlink_secret_file(credential_path)

    def _wait_until_ready(
        self, runtime_id: int, owner_token: str
    ) -> BridgeObservation:
        deadline = time.monotonic() + self.readiness_timeout_seconds
        while True:
            observation = self.inspect(runtime_id, owner_token)
            if observation.status != "unhealthy" or time.monotonic() >= deadline:
                return observation
            time.sleep(self.readiness_interval_seconds)

    def inspect(self, runtime_id: int, owner_token: str) -> BridgeObservation:
        manifest = self._read_manifest(runtime_id)
        if manifest is None:
            return BridgeObservation(runtime_id, owner_token, "stopped")
        if manifest.get("owner_token") != owner_token:
            raise BridgeOwnershipConflict("BRIDGE_OWNERSHIP_CONFLICT")
        unit = self._unit_name(runtime_id)
        if manifest.get("unit") != unit:
            raise BridgeOwnershipConflict("BRIDGE_OWNERSHIP_CONFLICT")
        properties = self._unit_properties(unit)
        if properties.get("LoadState") == "not-found" or properties.get("ActiveState") in {"inactive", "failed"}:
            return BridgeObservation(runtime_id, owner_token, "stopped", supervisor_id=unit)
        expected_description = self._description_from_manifest(manifest)
        if properties.get("Description") != expected_description:
            raise BridgeOwnershipConflict("BRIDGE_OWNERSHIP_CONFLICT")
        try:
            pid = int(properties.get("MainPID", "0"))
        except ValueError as error:
            raise BridgeOwnershipConflict("BRIDGE_OWNERSHIP_CONFLICT") from error
        if pid <= 0:
            return BridgeObservation(runtime_id, owner_token, "unhealthy", supervisor_id=unit)
        start_token = self._process_start_token(pid)
        recorded = manifest.get("process_start_token")
        if recorded is not None and recorded != start_token:
            raise BridgeOwnershipConflict("BRIDGE_OWNERSHIP_CONFLICT")
        if not self._pid_owns_listener(pid, str(manifest["loopback_host"]), int(manifest["host_port"])):
            return BridgeObservation(
                runtime_id, owner_token, "unhealthy", supervisor_id=unit,
                pid=pid, process_start_token=start_token,
            )
        return BridgeObservation(
            runtime_id, owner_token, "running", supervisor_id=unit,
            pid=pid, process_start_token=start_token,
        )

    def stop(self, runtime_id: int, owner_token: str) -> BridgeObservation:
        observation = self.inspect(runtime_id, owner_token)
        if observation.status == "stopped":
            self._remove_manifest(runtime_id)
            return observation
        unit = self._unit_name(runtime_id)
        result = self.runner(["systemctl", *self._scope_arguments(), "stop", unit])
        if result.returncode != 0:
            raise SystemdBridgeError("Unable to stop supervised proxy bridge")
        properties = self._unit_properties(unit)
        if properties.get("ActiveState") not in {"inactive", "failed"}:
            raise SystemdBridgeError("Supervised proxy bridge did not stop")
        self._remove_manifest(runtime_id)
        return BridgeObservation(runtime_id, owner_token, "stopped", supervisor_id=unit)

    def _unit_properties(self, unit: str) -> dict[str, str]:
        result = self.runner(
            [
                "systemctl",
                *self._scope_arguments(),
                "show",
                unit,
                "--property=LoadState",
                "--property=ActiveState",
                "--property=Description",
                "--property=MainPID",
            ]
        )
        if result.returncode != 0:
            raise SystemdBridgeError("Unable to inspect supervised proxy bridge")
        return dict(
            line.split("=", 1)
            for line in result.stdout.splitlines()
            if "=" in line
        )

    def _scope_arguments(self) -> list[str]:
        return ["--user"] if self.settings.bridge_systemd_scope == "user" else []

    @staticmethod
    def _unit_name(runtime_id: int) -> str:
        return f"tiktok-manager-network-r{runtime_id}.service"

    @staticmethod
    def _description(spec: BridgeSpec, fingerprint: str) -> str:
        return (
            f"TikTok Manager network bridge runtime={spec.runtime_id} "
            f"owner={spec.owner_token} fingerprint={fingerprint}"
        )

    @staticmethod
    def _description_from_manifest(manifest: dict[str, object]) -> str:
        return (
            f"TikTok Manager network bridge runtime={manifest['runtime_id']} "
            f"owner={manifest['owner_token']} fingerprint={manifest['fingerprint']}"
        )

    def _fingerprint(self, spec: BridgeSpec) -> str:
        payload = {
            "adapter_type": spec.adapter_type,
            "host": spec.loopback_host,
            "host_port": spec.host_port,
            "python": str(self.settings.bridge_python_executable),
            "runtime_id": spec.runtime_id,
            "upstream_host": spec.upstream_host,
            "upstream_port": spec.upstream_port,
            "worker": str(self.worker_path),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def _prepare_state_directory(self) -> None:
        path = self.settings.bridge_state_directory
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise SystemdBridgeError("Bridge state directory is unsafe")
        os.chmod(path, 0o700)

    def _manifest_path(self, runtime_id: int) -> Path:
        return self.settings.bridge_state_directory / f"runtime-{runtime_id}.json"

    def _write_manifest(
        self,
        spec: BridgeSpec,
        *,
        unit: str,
        fingerprint: str,
        process_start_token: str | None,
    ) -> None:
        payload = {
            "runtime_id": spec.runtime_id,
            "owner_token": spec.owner_token,
            "unit": unit,
            "loopback_host": spec.loopback_host,
            "host_port": spec.host_port,
            "fingerprint": fingerprint,
            "process_start_token": process_start_token,
        }
        path = self._manifest_path(spec.runtime_id)
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True)

    def _read_manifest(self, runtime_id: int) -> dict[str, object] | None:
        path = self._manifest_path(runtime_id)
        try:
            info = path.lstat()
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            raise BridgeOwnershipConflict("BRIDGE_OWNERSHIP_CONFLICT")
        try:
            descriptor = os.open(
                path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            )
            with os.fdopen(descriptor, encoding="utf-8") as stream:
                payload = json.load(stream)
        except (OSError, json.JSONDecodeError) as error:
            raise BridgeOwnershipConflict("BRIDGE_OWNERSHIP_CONFLICT") from error
        if not isinstance(payload, dict):
            raise BridgeOwnershipConflict("BRIDGE_OWNERSHIP_CONFLICT")
        return payload

    def _remove_manifest(self, runtime_id: int) -> None:
        path = self._manifest_path(runtime_id)
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    @staticmethod
    def _write_secret_file(path: Path, credentials: BridgeCredentials) -> None:
        payload = {
            "username": credentials.username.reveal() if credentials.username else None,
            "password": credentials.password.reveal() if credentials.password else None,
        }
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream)

    @staticmethod
    def _unlink_secret_file(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def _validate_executables(self) -> None:
        for path in (self.settings.bridge_python_executable, self.worker_path):
            if not path.is_absolute() or not path.is_file():
                raise SystemdBridgeError("Configured bridge executable is unavailable")

    @staticmethod
    def _process_start_token(pid: int) -> str:
        try:
            fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
            return fields[21]
        except (OSError, IndexError) as error:
            raise BridgeOwnershipConflict("BRIDGE_OWNERSHIP_CONFLICT") from error

    @staticmethod
    def _pid_owns_listener(pid: int, host: str, port: int) -> bool:
        if host != "127.0.0.1":
            return False
        try:
            socket_inodes = {
                target.removeprefix("socket:[").removesuffix("]")
                for fd in Path(f"/proc/{pid}/fd").iterdir()
                if (target := os.readlink(fd)).startswith("socket:[")
            }
            for line in Path("/proc/net/tcp").read_text(encoding="utf-8").splitlines()[1:]:
                fields = line.split()
                address, hex_port = fields[1].split(":")
                if (
                    address == "0100007F"
                    and int(hex_port, 16) == port
                    and fields[3] == "0A"
                    and fields[9] in socket_inodes
                ):
                    return True
        except (OSError, ValueError, IndexError):
            return False
        return False

    @staticmethod
    def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(command), shell=False, capture_output=True, text=True, check=False
        )
