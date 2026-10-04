"""Internal typed results for safe Android automation primitives."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AutomationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime_id: int = Field(gt=0)


class DeviceStateResult(AutomationResult):
    container_status: str
    boot_completed: bool
    adb_state: str
    ready: bool


class PackageStateResult(AutomationResult):
    package_name: str
    installed: bool
    running: bool
    pid: int | None = None


class ArtifactResult(AutomationResult):
    artifact_id: int = Field(gt=0)
    kind: str
    filename: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    sha256: str


class ScreenshotResult(ArtifactResult):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class FileTransferResult(AutomationResult):
    artifact_id: int = Field(gt=0)
    remote_path: str
    filename: str
    size_bytes: int = Field(ge=0)
    sha256: str


class MediaImportResult(FileTransferResult):
    media_imported: bool
    media_uri: str | None = None


class InputActionResult(AutomationResult):
    action: str


class ArtifactMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    job_id: int | None = Field(default=None, gt=0)
    kind: str
    filename: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    sha256: str
    state: Literal["available", "expired", "deleted"]
    created_at: datetime
    expires_at: datetime | None = None
