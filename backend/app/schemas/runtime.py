"""Pydantic schemas for runtime endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RuntimeFields(BaseModel):
    """Fields shared by runtime creation and response payloads."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    device_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=255)
    runtime_type: str = Field(min_length=1, max_length=50)
    status: str = Field(min_length=1, max_length=50)
    last_seen_at: datetime | None = None


class RuntimeCreate(RuntimeFields):
    """Payload for creating a runtime."""


class RuntimeUpdate(BaseModel):
    """Payload for partially updating a runtime."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    device_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    runtime_type: str | None = Field(default=None, min_length=1, max_length=50)
    status: str | None = Field(default=None, min_length=1, max_length=50)
    last_seen_at: datetime | None = None

    @field_validator(
        "device_id", "name", "runtime_type", "status", mode="before"
    )
    @classmethod
    def required_fields_cannot_be_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class RuntimeRead(RuntimeFields):
    """Runtime representation returned by the API."""

    model_config = ConfigDict(
        extra="forbid", from_attributes=True, str_strip_whitespace=True
    )

    id: int
    created_at: datetime
    updated_at: datetime


class RuntimeList(BaseModel):
    """Paginated runtime collection."""

    items: list[RuntimeRead]
    total: int
    page: int
    page_size: int
