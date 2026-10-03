"""Trusted host configuration for per-Runtime networking."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from app.config import load_application_config


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
        application = load_application_config()
        try:
            return cls(
                bridge_port_start=application.bridge_port_start,
                bridge_port_end=application.bridge_port_end,
                bridge_device_port=application.bridge_device_port,
                lock_directory=application.bridge_lock_directory,
                bridge_state_directory=application.bridge_state_directory,
                bridge_python_executable=Path(
                    os.getenv("RUNTIME_NETWORK_BRIDGE_PYTHON", sys.executable)
                ),
                bridge_systemd_scope=application.bridge_systemd_scope,
            )
        except ValueError as error:
            raise NetworkConfigurationError("network port settings must be integers") from error
