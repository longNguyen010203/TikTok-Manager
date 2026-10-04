"""Typed public device Job definitions and execution metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.schemas.device_automation import (
    ArtifactResult,
    FileTransferResult,
    MediaImportResult,
    PackageStateResult,
    ScreenshotResult,
)


class EmptyDevicePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PackagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    package_name: str = Field(min_length=3, max_length=255)


class ArtifactPushPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    artifact_id: int = Field(gt=0)
    filename: str | None = Field(default=None, min_length=1, max_length=255)


class PullFilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    remote_path: str = Field(min_length=1, max_length=512)


@dataclass(frozen=True)
class DeviceJobDefinition:
    job_type: str
    payload_schema: type[BaseModel]
    result_schema: type[BaseModel]
    requires_device_ready: bool
    requires_network: bool
    retryable_codes: frozenset[str]
    idempotency: Literal["safe", "artifact_identity", "non_idempotent"]
    command_timeout_seconds: float
    handler_timeout_seconds: float
    overall_timeout_seconds: float

    @property
    def allows_post_dispatch_retry(self) -> bool:
        return self.idempotency in {"safe", "artifact_identity"}


_TRANSIENT_CODES = frozenset(
    {
        "ADB_UNAVAILABLE",
        "DEVICE_NOT_READY",
        "RUNTIME_BUSY",
        "AUTOMATION_TIMEOUT",
        "ADB_COMMAND_FAILED",
        "FILE_TRANSFER_FAILED",
        "MEDIA_IMPORT_FAILED",
    }
)


DEVICE_JOB_DEFINITIONS: dict[str, DeviceJobDefinition] = {
    "device.screenshot": DeviceJobDefinition(
        "device.screenshot", EmptyDevicePayload, ScreenshotResult,
        True, False, _TRANSIENT_CODES, "safe", 30, 60, 90,
    ),
    "device.package_state": DeviceJobDefinition(
        "device.package_state", PackagePayload, PackageStateResult,
        True, False, _TRANSIENT_CODES, "safe", 15, 45, 60,
    ),
    "device.launch_app": DeviceJobDefinition(
        "device.launch_app", PackagePayload, PackageStateResult,
        True, False, _TRANSIENT_CODES, "safe", 15, 45, 60,
    ),
    "device.stop_app": DeviceJobDefinition(
        "device.stop_app", PackagePayload, PackageStateResult,
        True, False, _TRANSIENT_CODES, "safe", 15, 45, 60,
    ),
    "device.push_file": DeviceJobDefinition(
        "device.push_file", ArtifactPushPayload, FileTransferResult,
        True, False, _TRANSIENT_CODES, "artifact_identity", 120, 150, 180,
    ),
    "device.pull_file": DeviceJobDefinition(
        "device.pull_file", PullFilePayload, ArtifactResult,
        True, False, _TRANSIENT_CODES, "artifact_identity", 120, 150, 180,
    ),
    "device.import_media": DeviceJobDefinition(
        "device.import_media", ArtifactPushPayload, MediaImportResult,
        True, False, _TRANSIENT_CODES, "artifact_identity", 120, 180, 240,
    ),
}


class DeviceJobValidationError(ValueError):
    """Raised when a public device Job type or payload is invalid."""


def get_device_job_definition(
    job_type: str, *, required: bool = True
) -> DeviceJobDefinition | None:
    try:
        return DEVICE_JOB_DEFINITIONS[job_type]
    except KeyError as error:
        if not required:
            return None
        raise DeviceJobValidationError("Unknown device Job type") from error


def validate_device_job_payload(job_type: str, payload: Any) -> dict[str, Any]:
    definition = get_device_job_definition(job_type)
    assert definition is not None
    try:
        validated = definition.payload_schema.model_validate(payload or {})
    except ValidationError as error:
        raise DeviceJobValidationError("Invalid device Job payload") from error
    return validated.model_dump()


def is_device_job_type(job_type: object) -> bool:
    return isinstance(job_type, str) and job_type.startswith("device.")
