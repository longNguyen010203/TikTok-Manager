"""Trusted server-side configuration for managed Redroid provisioning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.config import load_application_config


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
        application = load_application_config()
        return cls(
            installation_id=application.installation_id,
            image_reference=application.redroid_image,
            data_root=application.redroid_data_root,
            base_adb_port=application.redroid_base_adb_port,
            network_prefix=application.redroid_network_prefix,
            supported_profile=application.redroid_profile,
        )
