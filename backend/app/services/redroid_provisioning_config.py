"""Trusted server-side configuration for managed Redroid provisioning."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


class ProvisioningConfigurationError(ValueError):
    """Raised when trusted provisioning configuration is absent or unsafe."""


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
_SAFE_PREFIX = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_IMMUTABLE_IMAGE = re.compile(r"^.+@sha256:[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class RedroidProvisioningSettings:
    installation_id: str
    image_reference: str
    data_root: Path
    base_adb_port: int = 5554
    network_prefix: str = "redroid-device"
    supported_profile: str = "android-12-redroid"

    def __post_init__(self) -> None:
        if not _SAFE_ID.fullmatch(self.installation_id):
            raise ProvisioningConfigurationError("installation_id is required and must be a stable safe identifier")
        if not _IMMUTABLE_IMAGE.fullmatch(self.image_reference):
            raise ProvisioningConfigurationError("image_reference must use an immutable sha256 digest")
        if not self.data_root.is_absolute():
            raise ProvisioningConfigurationError("data_root must be an absolute path")
        if self.data_root == Path("/"):
            raise ProvisioningConfigurationError("data_root must not be the filesystem root")
        if not 1024 <= self.base_adb_port < 65535:
            raise ProvisioningConfigurationError("base_adb_port must be between 1024 and 65534")
        if not _SAFE_PREFIX.fullmatch(self.network_prefix):
            raise ProvisioningConfigurationError("network_prefix contains unsupported characters")
        if not _SAFE_ID.fullmatch(self.supported_profile):
            raise ProvisioningConfigurationError("supported_profile contains unsupported characters")

    @classmethod
    def from_environment(cls) -> "RedroidProvisioningSettings":
        required = {
            "installation_id": os.getenv("TIKTOK_MANAGER_INSTALLATION_ID"),
            "image_reference": os.getenv("REDROID_PROVISIONING_IMAGE"),
            "data_root": os.getenv("REDROID_PROVISIONING_DATA_ROOT"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ProvisioningConfigurationError(
                "Missing required provisioning configuration: " + ", ".join(missing)
            )
        try:
            base_port = int(os.getenv("REDROID_PROVISIONING_BASE_ADB_PORT", "5554"))
        except ValueError as error:
            raise ProvisioningConfigurationError("REDROID_PROVISIONING_BASE_ADB_PORT must be an integer") from error
        return cls(
            installation_id=required["installation_id"] or "",
            image_reference=required["image_reference"] or "",
            data_root=Path(required["data_root"] or ""),
            base_adb_port=base_port,
            network_prefix=os.getenv("REDROID_PROVISIONING_NETWORK_PREFIX", "redroid-device"),
            supported_profile=os.getenv("REDROID_PROVISIONING_PROFILE", "android-12-redroid"),
        )
