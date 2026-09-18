"""Pydantic schemas for account endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AccountFields(BaseModel):
    """Fields shared by account creation and response payloads."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=1, max_length=255)
    platform: str = Field(min_length=1, max_length=50)
    status: str = Field(min_length=1, max_length=50)
    notes: str | None = None


class AccountCreate(AccountFields):
    """Payload for creating an account."""


class AccountUpdate(BaseModel):
    """Payload for partially updating an account."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    username: str | None = Field(default=None, min_length=1, max_length=255)
    platform: str | None = Field(default=None, min_length=1, max_length=50)
    status: str | None = Field(default=None, min_length=1, max_length=50)
    notes: str | None = None

    @field_validator("name", "username", "platform", "status", mode="before")
    @classmethod
    def required_fields_cannot_be_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class AccountRead(AccountFields):
    """Account representation returned by the API."""

    model_config = ConfigDict(
        extra="forbid", from_attributes=True, str_strip_whitespace=True
    )

    id: int
    created_at: datetime
    updated_at: datetime


class AccountList(BaseModel):
    """Paginated account collection."""

    items: list[AccountRead]
    total: int
    page: int
    page_size: int
