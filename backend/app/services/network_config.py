"""Trusted host configuration for per-Runtime networking."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


class NetworkConfigurationError(ValueError):
    """Raised when trusted network service configuration is unsafe."""


@dataclass(frozen=True)
class RuntimeNetworkSettings:
    bridge_port_start: int = 8800
    bridge_port_end: int = 8899
    bridge_device_port: int = 8888
    lock_directory: Path = Path("/tmp/tiktok-manager-network-locks")
    bridge_state_directory: Path = Path(f"/run/user/{os.getuid()}/tiktok-manager-network")
    bridge_python_executable: Path = Path(sys.executable)
    bridge_systemd_scope: str = "user"

    def __post_init__(self) -> None:
        for name, value in (
            ("bridge_port_start", self.bridge_port_start),
            ("bridge_port_end", self.bridge_port_end),
            ("bridge_device_port", self.bridge_device_port),
        ):
            if not 1 <= value <= 65535:
                raise NetworkConfigurationError(f"{name} must be between 1 and 65535")
        if self.bridge_port_start > self.bridge_port_end:
            raise NetworkConfigurationError("bridge port range is reversed")
        if not self.lock_directory.is_absolute():
            raise NetworkConfigurationError("lock_directory must be absolute")
        if not self.bridge_state_directory.is_absolute():
            raise NetworkConfigurationError("bridge_state_directory must be absolute")
        if not self.bridge_python_executable.is_absolute():
            raise NetworkConfigurationError("bridge_python_executable must be absolute")
        if self.bridge_systemd_scope not in {"user", "system"}:
            raise NetworkConfigurationError("bridge_systemd_scope must be user or system")

    @classmethod
    def from_environment(cls) -> "RuntimeNetworkSettings":
        try:
            return cls(
                bridge_port_start=int(os.getenv("RUNTIME_NETWORK_BRIDGE_PORT_START", "8800")),
                bridge_port_end=int(os.getenv("RUNTIME_NETWORK_BRIDGE_PORT_END", "8899")),
                bridge_device_port=int(os.getenv("RUNTIME_NETWORK_BRIDGE_DEVICE_PORT", "8888")),
                lock_directory=Path(os.getenv("RUNTIME_NETWORK_LOCK_DIRECTORY", "/tmp/tiktok-manager-network-locks")),
                bridge_state_directory=Path(
                    os.getenv(
                        "RUNTIME_NETWORK_BRIDGE_STATE_DIRECTORY",
                        f"/run/user/{os.getuid()}/tiktok-manager-network",
                    )
                ),
                bridge_python_executable=Path(
                    os.getenv("RUNTIME_NETWORK_BRIDGE_PYTHON", sys.executable)
                ),
                bridge_systemd_scope=os.getenv(
                    "RUNTIME_NETWORK_BRIDGE_SYSTEMD_SCOPE", "user"
                ),
            )
        except ValueError as error:
            raise NetworkConfigurationError("network port settings must be integers") from error
