"""Safe API schemas for per-Runtime managed application state."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


RuntimeAppStatus = Literal[
    "pending", "installing", "installed", "failed", "outdated", "removed"
]


class RuntimeAppInstallRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    managed_app_version_id: int | None = Field(default=None, gt=0)


class RuntimeAppInstallationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    runtime_id: int | None
    runtime_id_snapshot: int
    managed_app_id: int
    desired_managed_app_version_id: int
    observed_managed_app_version_id: int | None
    status: RuntimeAppStatus
    observed_package_name: str | None
    observed_version_name: str | None
    observed_version_code: int | None
    observed_signer_fingerprint: str | None
    latest_job_id: int | None
    installed_at: datetime | None
    verified_at: datetime | None
    last_attempt_at: datetime | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class RuntimeAppOperationRead(BaseModel):
    installation: RuntimeAppInstallationRead
    job_id: int | None


class RuntimeAppsRead(BaseModel):
    runtime_id: int
    items: list[RuntimeAppInstallationRead]


class PublishingReadinessRead(BaseModel):
    runtime_id: int
    runtime_ready: bool
    required_apps_ready: bool
    publishing_ready: bool
    required_count: int
    installed_count: int
    pending_count: int
    failed_count: int
    outdated_count: int

