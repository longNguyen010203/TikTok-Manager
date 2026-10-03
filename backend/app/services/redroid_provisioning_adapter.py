"""Safe Docker and filesystem primitives for Redroid provisioning."""

from __future__ import annotations

import json
import os
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from app.services.host_lifecycle import check_binder_readiness
from app.services.redroid_provisioning_config import RedroidProvisioningSettings


class ProvisioningAdapterError(RuntimeError):
    pass


class ProvisioningConflictError(ProvisioningAdapterError):
    pass


class ProvisioningVerificationError(ProvisioningAdapterError):
    pass


class ProvisioningOwnershipError(ProvisioningAdapterError):
    pass


@dataclass(frozen=True)
class ProvisioningAllocation:
    provisioning_id: str
    ownership_token: str
    device_number: int
    container_name: str
    adb_host_port: int
    adb_serial: str
    data_path: Path
    network_name: str
    image_reference: str
    installation_id: str

    @property
    def suffix(self) -> str:
        return f"{self.device_number:02d}"

    def labels(self, resource: str) -> dict[str, str]:
        return {
            "com.tiktok-manager.managed": "true",
            "com.tiktok-manager.installation": self.installation_id,
            "com.tiktok-manager.provisioning-id": self.provisioning_id,
            "com.tiktok-manager.ownership-token": self.ownership_token,
            "com.tiktok-manager.device-number": self.suffix,
            "com.tiktok-manager.resource": resource,
            "com.tiktok-manager.runtime": "redroid",
        }


@dataclass(frozen=True)
class OccupiedResources:
    container_names: frozenset[str]
    network_names: frozenset[str]
    data_paths: frozenset[Path]
    host_ports: frozenset[int]


class RedroidProvisioningAdapter:
    """Create and roll back only resources carrying matching ownership proof."""

    marker_name = ".tiktok-manager-provisioning.json"

    def __init__(self, settings: RedroidProvisioningSettings) -> None:
        self.settings = settings

    def preflight(self) -> None:
        self._run(["docker", "info", "--format", "{{.ServerVersion}}"])
        self._run(["docker", "image", "inspect", self.settings.image_reference])
        failures = check_binder_readiness()
        if failures:
            raise ProvisioningAdapterError("; ".join(failures))
        root = self.settings.data_root
        if root.is_symlink() or not root.is_dir() or not os.access(root, os.W_OK | os.X_OK):
            raise ProvisioningAdapterError(f"Provisioning data root is not writable: {root}")

    def occupied_resources(self) -> OccupiedResources:
        containers = self._inspect_all("container")
        networks = self._inspect_all("network")
        names: set[str] = set()
        ports: set[int] = set()
        for item in containers:
            names.add(str(item.get("Name", "")).lstrip("/"))
            bindings = item.get("HostConfig", {}).get("PortBindings", {}) or {}
            for entries in bindings.values():
                for entry in entries or []:
                    value = entry.get("HostPort")
                    if value and str(value).isdigit():
                        ports.add(int(value))
        network_names = {str(item.get("Name", "")) for item in networks}
        data_paths = (
            frozenset(path.resolve() for path in self.settings.data_root.iterdir())
            if self.settings.data_root.is_dir()
            else frozenset()
        )
        return OccupiedResources(frozenset(names), frozenset(network_names), data_paths, frozenset(ports))

    def port_is_available(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                return False
        return True

    def inspect_container(self, name_or_id: str) -> dict[str, Any] | None:
        return self._inspect_one("container", name_or_id)

    def inspect_network(self, name_or_id: str) -> dict[str, Any] | None:
        return self._inspect_one("network", name_or_id)

    def create_owned_data_directory(self, allocation: ProvisioningAllocation) -> bool:
        self._validate_allocation(allocation)
        path = self._validated_data_path(allocation)
        marker = path / self.marker_name
        payload = self._marker_payload(allocation)
        if path.exists():
            try:
                self._require_marker(marker, payload)
            except ProvisioningOwnershipError as error:
                raise ProvisioningConflictError(
                    "Data path already exists without matching ownership"
                ) from error
            return True
        path.mkdir(mode=0o771, parents=False)
        try:
            with marker.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.write("\n")
        except Exception:
            path.rmdir()
            raise
        return True

    def create_network(self, allocation: ProvisioningAllocation) -> str:
        self._validate_allocation(allocation)
        existing = self.inspect_network(allocation.network_name)
        if existing is not None:
            try:
                self._require_labels(existing, allocation.labels("network"))
            except ProvisioningOwnershipError as error:
                raise ProvisioningConflictError(
                    "Docker network name is already owned by another resource"
                ) from error
            return str(existing["Id"])
        command = ["docker", "network", "create", "--driver", "bridge"]
        command += ["--opt", "com.docker.network.bridge.enable_icc=false"]
        for key, value in allocation.labels("network").items():
            command += ["--label", f"{key}={value}"]
        command.append(allocation.network_name)
        return self._run(command).stdout.strip()

    def verify_network(self, allocation: ProvisioningAllocation, network_id: str) -> None:
        self._validate_allocation(allocation)
        item = self.inspect_network(network_id)
        if item is None or str(item.get("Id")) != network_id:
            raise ProvisioningVerificationError("Created network ID cannot be inspected")
        self._require_labels(item, allocation.labels("network"))
        if item.get("Name") != allocation.network_name:
            raise ProvisioningVerificationError("Provisioning network name differs")
        if item.get("Driver") != "bridge":
            raise ProvisioningVerificationError("Provisioning network is not a bridge")
        options = item.get("Options") or {}
        if options.get("com.docker.network.bridge.enable_icc") != "false":
            raise ProvisioningVerificationError("Provisioning network ICC is not disabled")

    def create_container(self, allocation: ProvisioningAllocation) -> str:
        self._validate_allocation(allocation)
        existing = self.inspect_container(allocation.container_name)
        if existing is not None:
            try:
                self._require_labels(existing, allocation.labels("container"))
            except ProvisioningOwnershipError as error:
                raise ProvisioningConflictError(
                    "Docker container name is already owned by another resource"
                ) from error
            return str(existing["Id"])
        mount = f"type=bind,src={allocation.data_path},dst=/data,bind-propagation=rprivate"
        command = [
            "docker", "create", "--name", allocation.container_name,
            "--privileged", "--security-opt", "label=disable", "--interactive", "--tty",
            "--restart", "no", "--stop-timeout", "30",
            "--publish", f"127.0.0.1:{allocation.adb_host_port}:5555/tcp",
            "--mount", mount, "--network", allocation.network_name,
        ]
        for key, value in allocation.labels("container").items():
            command += ["--label", f"{key}={value}"]
        command.append(allocation.image_reference)
        return self._run(command).stdout.strip()

    def verify_container(self, allocation: ProvisioningAllocation, container_id: str) -> None:
        self._validate_allocation(allocation)
        item = self.inspect_container(container_id)
        if item is None or str(item.get("Id")) != container_id:
            raise ProvisioningVerificationError("Created container ID cannot be inspected")
        self._require_labels(item, allocation.labels("container"))
        host = item.get("HostConfig", {})
        config = item.get("Config", {})
        state = item.get("State", {})
        expected_binding = [{"HostIp": "127.0.0.1", "HostPort": str(allocation.adb_host_port)}]
        bindings = (host.get("PortBindings") or {}).get("5555/tcp")
        mounts = [mount for mount in item.get("Mounts", []) if mount.get("Destination") == "/data"]
        networks = item.get("NetworkSettings", {}).get("Networks", {})
        failures = []
        if str(item.get("Name", "")).lstrip("/") != allocation.container_name:
            failures.append("container name differs")
        if state.get("Status") != "created" or state.get("Running"):
            failures.append("container is not stopped in created state")
        if config.get("Image") != allocation.image_reference:
            failures.append("image reference differs")
        if bindings != expected_binding:
            failures.append("ADB binding is not exact loopback-only mapping")
        if not host.get("Privileged") or host.get("AutoRemove"):
            failures.append("privileged/auto-remove settings differ")
        if not config.get("OpenStdin") or not config.get("Tty"):
            failures.append("stdin/tty settings differ")
        if "label=disable" not in (host.get("SecurityOpt") or []):
            failures.append("security label setting differs")
        if config.get("StopTimeout") != 30:
            failures.append("stop timeout differs")
        if (host.get("RestartPolicy") or {}).get("Name") not in {"", "no"}:
            failures.append("restart policy differs")
        if host.get("Devices"):
            failures.append("explicit device mappings are forbidden")
        if (
            len(mounts) != 1
            or mounts[0].get("Type") != "bind"
            or Path(str(mounts[0].get("Source", ""))) != allocation.data_path
            or mounts[0].get("Propagation") != "rprivate"
            or not mounts[0].get("RW")
        ):
            failures.append("/data bind mount differs")
        if any(str(mount.get("Destination", "")).startswith("/dev/binder") for mount in item.get("Mounts", [])):
            failures.append("explicit Binder mounts are forbidden")
        if allocation.network_name not in networks:
            failures.append("dedicated network is missing")
        if failures:
            raise ProvisioningVerificationError("; ".join(failures))

    def remove_owned_container(self, allocation: ProvisioningAllocation, container_id: str) -> bool:
        self._validate_allocation(allocation)
        item = self.inspect_container(container_id)
        if item is None:
            return True
        if str(item.get("Id")) != container_id:
            raise ProvisioningOwnershipError("Container ID changed")
        self._require_labels(item, allocation.labels("container"))
        state = item.get("State", {})
        started_at = str(state.get("StartedAt", ""))
        never_started = state.get("Status") == "created" and started_at.startswith("0001-01-01")
        if not never_started:
            raise ProvisioningOwnershipError("Container has started; automatic removal refused")
        self._run(["docker", "container", "rm", container_id])
        return True

    def owned_container_id(self, allocation: ProvisioningAllocation) -> str | None:
        self._validate_allocation(allocation)
        item = self.inspect_container(allocation.container_name)
        if item is None:
            return None
        self._require_labels(item, allocation.labels("container"))
        return str(item["Id"])

    def remove_owned_network(self, allocation: ProvisioningAllocation, network_id: str) -> bool:
        self._validate_allocation(allocation)
        item = self.inspect_network(network_id)
        if item is None:
            return True
        if str(item.get("Id")) != network_id:
            raise ProvisioningOwnershipError("Network ID changed")
        self._require_labels(item, allocation.labels("network"))
        if item.get("Containers"):
            raise ProvisioningOwnershipError("Network still has attached containers")
        self._run(["docker", "network", "rm", network_id])
        return True

    def owned_network_id(self, allocation: ProvisioningAllocation) -> str | None:
        self._validate_allocation(allocation)
        item = self.inspect_network(allocation.network_name)
        if item is None:
            return None
        self._require_labels(item, allocation.labels("network"))
        return str(item["Id"])

    def verify_owned_data_directory(self, allocation: ProvisioningAllocation) -> None:
        """Verify the preserved data directory without changing its contents."""
        self._validate_allocation(allocation)
        path = self._validated_data_path(allocation)
        if not path.is_dir():
            raise ProvisioningOwnershipError("Provisioned data directory is missing")
        self._require_marker(
            path / self.marker_name,
            self._marker_payload(allocation),
        )

    def require_owned_container_for_removal(
        self, allocation: ProvisioningAllocation, container_id: str
    ) -> dict[str, Any]:
        """Return a container only when its immutable ID and ownership all match."""
        self._validate_allocation(allocation)
        if not container_id:
            raise ProvisioningOwnershipError("Recorded container ID is missing")
        item = self.inspect_container(container_id)
        if item is None:
            replacement = self.inspect_container(allocation.container_name)
            if replacement is not None:
                raise ProvisioningOwnershipError(
                    "A different container occupies the provisioned name"
                )
            raise ProvisioningOwnershipError("Recorded container is missing")
        if str(item.get("Id")) != container_id:
            raise ProvisioningOwnershipError("Container ID changed")
        self._require_labels(item, allocation.labels("container"))
        if str(item.get("Name", "")).lstrip("/") != allocation.container_name:
            raise ProvisioningOwnershipError("Container name changed")
        return item

    def require_owned_network_for_removal(
        self, allocation: ProvisioningAllocation, network_id: str
    ) -> dict[str, Any]:
        """Return a network only when its immutable ID and ownership all match."""
        self._validate_allocation(allocation)
        if not network_id:
            raise ProvisioningOwnershipError("Recorded network ID is missing")
        item = self.inspect_network(network_id)
        if item is None:
            replacement = self.inspect_network(allocation.network_name)
            if replacement is not None:
                raise ProvisioningOwnershipError(
                    "A different network occupies the provisioned name"
                )
            raise ProvisioningOwnershipError("Recorded network is missing")
        if str(item.get("Id")) != network_id:
            raise ProvisioningOwnershipError("Network ID changed")
        self._require_labels(item, allocation.labels("network"))
        if item.get("Name") != allocation.network_name:
            raise ProvisioningOwnershipError("Network name changed")
        return item

    def require_removed_container_absent(
        self, allocation: ProvisioningAllocation
    ) -> None:
        """Refuse recovery if any resource now occupies a removed name."""
        self._validate_allocation(allocation)
        if self.inspect_container(allocation.container_name) is not None:
            raise ProvisioningOwnershipError(
                "A container now occupies the deprovisioned name"
            )

    def require_removed_network_absent(self, allocation: ProvisioningAllocation) -> None:
        """Refuse recovery if any resource now occupies a removed name."""
        self._validate_allocation(allocation)
        if self.inspect_network(allocation.network_name) is not None:
            raise ProvisioningOwnershipError(
                "A network now occupies the deprovisioned name"
            )

    def remove_verified_container(
        self, allocation: ProvisioningAllocation, container_id: str
    ) -> bool:
        """Remove a stopped container by verified immutable ID."""
        item = self.require_owned_container_for_removal(allocation, container_id)
        if (item.get("State") or {}).get("Running"):
            raise ProvisioningOwnershipError("Owned container is still running")
        self._run(["docker", "container", "rm", container_id])
        return True

    def remove_verified_network(
        self, allocation: ProvisioningAllocation, network_id: str
    ) -> bool:
        """Remove an empty network by verified immutable ID."""
        item = self.require_owned_network_for_removal(allocation, network_id)
        if item.get("Containers"):
            raise ProvisioningOwnershipError("Network still has attached containers")
        self._run(["docker", "network", "rm", network_id])
        return True

    def remove_owned_data_directory(self, allocation: ProvisioningAllocation) -> bool:
        self._validate_allocation(allocation)
        path = self._validated_data_path(allocation)
        if not path.exists():
            return True
        marker = path / self.marker_name
        self._require_marker(marker, self._marker_payload(allocation))
        if set(path.iterdir()) != {marker}:
            raise ProvisioningOwnershipError("Data directory contains unexpected files")
        marker.unlink()
        path.rmdir()
        return True

    def _validated_data_path(self, allocation: ProvisioningAllocation) -> Path:
        root = self.settings.data_root.resolve()
        path = allocation.data_path
        expected = root / f"device-{allocation.suffix}-data"
        if path != expected or path.parent.resolve() != root:
            raise ProvisioningOwnershipError("Data path is outside the configured allocation")
        if path.is_symlink():
            raise ProvisioningOwnershipError("Data path must not be a symlink")
        return path

    def _validate_allocation(self, allocation: ProvisioningAllocation) -> None:
        suffix = f"{allocation.device_number:02d}"
        expected = (
            allocation.device_number > 0,
            allocation.container_name == f"redroid-device-{suffix}",
            allocation.adb_host_port == self.settings.base_adb_port + allocation.device_number,
            allocation.adb_serial == f"localhost:{allocation.adb_host_port}",
            allocation.network_name == f"{self.settings.network_prefix}-{suffix}-net",
            allocation.image_reference == self.settings.image_reference,
            allocation.installation_id == self.settings.installation_id,
        )
        if not all(expected) or not 1024 <= allocation.adb_host_port <= 65535:
            raise ProvisioningOwnershipError("Allocation does not match trusted derived configuration")

    @staticmethod
    def _marker_payload(allocation: ProvisioningAllocation) -> dict[str, str]:
        return {"installation_id": allocation.installation_id, "provisioning_id": allocation.provisioning_id, "ownership_token": allocation.ownership_token}

    @staticmethod
    def _require_marker(marker: Path, expected: dict[str, str]) -> None:
        if marker.is_symlink() or not marker.is_file():
            raise ProvisioningOwnershipError("Provisioning ownership marker is missing or unsafe")
        try:
            actual = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ProvisioningOwnershipError("Provisioning ownership marker is invalid") from error
        if actual != expected:
            raise ProvisioningOwnershipError("Provisioning ownership marker does not match")

    @staticmethod
    def _require_labels(item: dict[str, Any], expected: dict[str, str]) -> None:
        labels = item.get("Config", {}).get("Labels") if "Config" in item else item.get("Labels")
        labels = labels or {}
        if any(labels.get(key) != value for key, value in expected.items()):
            raise ProvisioningOwnershipError("Docker ownership labels do not match")

    def _inspect_all(self, resource: str) -> list[dict[str, Any]]:
        noun = "container" if resource == "container" else "network"
        list_args = ["docker", noun, "ls", "-aq"] if noun == "container" else ["docker", noun, "ls", "-q"]
        ids = self._run(list_args).stdout.split()
        if not ids:
            return []
        result = self._run(["docker", noun, "inspect", *ids])
        return list(json.loads(result.stdout))

    def _inspect_one(self, resource: str, name_or_id: str) -> dict[str, Any] | None:
        result = self._run(["docker", resource, "inspect", name_or_id], check=False)
        if result.returncode != 0:
            return None
        values = json.loads(result.stdout)
        return values[0] if values else None

    @staticmethod
    def _run(command: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(list(command), shell=False, capture_output=True, text=True, check=False)
        except OSError as error:
            raise ProvisioningAdapterError(f"Unable to execute {command[0]!r}") from error
        if check and result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise ProvisioningAdapterError(f"{command[0]!r} failed: {detail}")
        return result
