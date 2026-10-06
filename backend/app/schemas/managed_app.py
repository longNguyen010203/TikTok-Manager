"""Strict public schemas for managed Android packages."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ManagedAppStatus = Literal["active", "disabled", "archived"]
ManagedAppPolicy = Literal["required", "optional", "disabled"]
ManagedAppVersionStatus = Literal["uploaded", "inspecting", "ready", "invalid", "retired"]
InspectionLevel = Literal["basic", "verified"]
PackageVerification = Literal["post_install", "pre_and_post_install"]


class ManagedAppCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=255)
    android_package_name: str = Field(min_length=3, max_length=255)
    install_policy: ManagedAppPolicy = "optional"


class ManagedAppPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    status: ManagedAppStatus | None = None
    install_policy: ManagedAppPolicy | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ManagedAppPatch":
        if not self.model_fields_set:
            raise ValueError("At least one managed app field is required")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Managed app fields cannot be null")
        return self


class ManagedAppVersionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    managed_app_id: int
    version_name: str | None
    version_code: int | None
    sha256: str
    discovered_package_name: str | None
    min_sdk: int | None
    target_sdk: int | None
    signer_fingerprint: str | None
    inspection_level: InspectionLevel
    package_verification: PackageVerification
    basic_approved: bool
    basic_approved_at: datetime | None
    status: ManagedAppVersionStatus
    inspection_job_id: int | None
    inspector_name: str
    inspector_version: str | None
    validated_at: datetime | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ManagedAppRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    key: str
    display_name: str
    android_package_name: str
    status: ManagedAppStatus
    install_policy: ManagedAppPolicy
    current_version_id: int | None
    created_at: datetime
    updated_at: datetime


class ManagedAppDetail(ManagedAppRead):
    versions: list[ManagedAppVersionRead]


class ManagedAppList(BaseModel):
    items: list[ManagedAppRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class ManagedAppVersionList(BaseModel):
    items: list[ManagedAppVersionRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class ManagedAppVersionUploadRead(BaseModel):
    version: ManagedAppVersionRead
    created: bool
