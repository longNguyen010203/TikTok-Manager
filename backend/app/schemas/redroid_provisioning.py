"""API schemas for managed Redroid provisioning."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RedroidProvisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    notes: str | None = None
    profile: str = Field(min_length=1, max_length=100)


class RedroidProvisioningStatus(BaseModel):
    provisioning_id: str
    state: str
    device_number: int | None
    container_name: str | None
    adb_serial: str | None
    data_path: str | None
    network_name: str | None
    image_reference: str
    device_id: int | None
    runtime_id: int | None
    data_directory_created: bool
    network_created: bool
    container_created: bool
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class RedroidDeprovisioningStatus(BaseModel):
    provisioning_id: str
    state: str
    container_removed: bool
    network_removed: bool
    data_preserved: bool
    data_path: str | None
    device_id: int | None
    runtime_id: int | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
