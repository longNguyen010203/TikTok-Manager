"""Pydantic schemas for device endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeviceFields(BaseModel):
    """Fields shared by device creation and response payloads."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    device_type: str = Field(min_length=1, max_length=50)
    platform: str = Field(min_length=1, max_length=50)
    os_version: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=50)
    notes: str | None = None


class DeviceCreate(DeviceFields):
    """Payload for creating a device."""


class DeviceUpdate(BaseModel):
    """Payload for partially updating a device."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    device_type: str | None = Field(default=None, min_length=1, max_length=50)
    platform: str | None = Field(default=None, min_length=1, max_length=50)
    os_version: str | None = Field(default=None, min_length=1, max_length=100)
    status: str | None = Field(default=None, min_length=1, max_length=50)
    notes: str | None = None

    @field_validator(
        "name", "device_type", "platform", "os_version", "status", mode="before"
    )
    @classmethod
    def required_fields_cannot_be_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class DeviceRead(DeviceFields):
    """Device representation returned by the API."""

    model_config = ConfigDict(
        extra="forbid", from_attributes=True, str_strip_whitespace=True
    )

    id: int
    created_at: datetime
    updated_at: datetime


class DeviceList(BaseModel):
    """Paginated device collection."""

    items: list[DeviceRead]
    total: int
    page: int
    page_size: int
