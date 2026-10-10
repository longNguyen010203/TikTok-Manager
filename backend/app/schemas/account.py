"""Validated schemas for the canonical Account Registry API."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

AccountStatus = Literal[
    "pending",
    "active",
    "inactive",
    "restricted",
    "suspended",
    "disabled",
    "archived",
]
RegistrationState = Literal["unknown", "pending", "registered", "failed"]
AccountHealthStatus = Literal["unknown", "healthy", "warning", "unhealthy"]
AccountSecretType = Literal[
    "account_password", "email_password", "recovery_credential"
]
NonNegativeMetric = Annotated[int | None, Field(default=None, ge=0)]


def _normalize_username(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().removeprefix("@").lower()
    if not normalized:
        raise ValueError("username cannot be empty")
    return normalized


def normalize_account_email(value: str | None) -> str | None:
    """Canonical Account email normalization shared by API and typed actions."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("email is invalid")
    normalized = value.strip().lower()
    if (
        not normalized
        or len(normalized) > 320
        or normalized.count("@") != 1
        or normalized.startswith("@")
        or normalized.endswith("@")
    ):
        raise ValueError("email is invalid")
    return normalized


def _normalize_tags(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        tag = " ".join(value.strip().lower().split())
        if not tag:
            raise ValueError("tags cannot be empty")
        if len(tag) > 50:
            raise ValueError("tags must be at most 50 characters")
        if tag not in seen:
            normalized.append(tag)
            seen.add(tag)
    if len(normalized) > 50:
        raise ValueError("at most 50 tags are allowed")
    return normalized


class AccountCreate(BaseModel):
    """Create a canonical Account while accepting the legacy name field."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, min_length=1, max_length=50)
    platform: str = Field(default="tiktok", min_length=1, max_length=50)
    status: AccountStatus = "active"
    registration_state: RegistrationState = "unknown"
    health_status: AccountHealthStatus = "unknown"
    status_reason: str | None = Field(default=None, max_length=500)
    niche: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=10_000)
    tags: list[str] = Field(default_factory=list)
    runtime_id: int | None = Field(default=None, gt=0)
    follower_count: NonNegativeMetric = None
    following_count: NonNegativeMetric = None
    likes_count: NonNegativeMetric = None
    video_count: NonNegativeMetric = None
    metrics_updated_at: datetime | None = None

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: Any) -> Any:
        return _normalize_username(value)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: Any) -> Any:
        return normalize_account_email(value)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return _normalize_tags(value)

    @model_validator(mode="after")
    def require_display_name(self) -> "AccountCreate":
        if self.display_name is None and self.name is None:
            raise ValueError("display_name is required")
        if (
            self.display_name is not None
            and self.name is not None
            and self.display_name != self.name
        ):
            raise ValueError("name and display_name must match when both are supplied")
        return self


class AccountUpdate(BaseModel):
    """Partial metadata, lifecycle, assignment, and metrics update."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    platform: str | None = Field(default=None, min_length=1, max_length=50)
    status: AccountStatus | None = None
    registration_state: RegistrationState | None = None
    health_status: AccountHealthStatus | None = None
    status_reason: str | None = Field(default=None, max_length=500)
    niche: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=10_000)
    tags: list[str] | None = None
    runtime_id: int | None = Field(default=None, gt=0)
    follower_count: NonNegativeMetric = None
    following_count: NonNegativeMetric = None
    likes_count: NonNegativeMetric = None
    video_count: NonNegativeMetric = None
    metrics_updated_at: datetime | None = None

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: Any) -> Any:
        return _normalize_username(value)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: Any) -> Any:
        return normalize_account_email(value)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        return _normalize_tags(value) if value is not None else None

    @model_validator(mode="after")
    def validate_aliases_and_required_values(self) -> "AccountUpdate":
        fields_set = self.model_fields_set
        for field in (
            "display_name",
            "name",
            "platform",
            "status",
            "registration_state",
            "health_status",
        ):
            if field in fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        if (
            "display_name" in fields_set
            and "name" in fields_set
            and self.display_name != self.name
        ):
            raise ValueError("name and display_name must match when both are supplied")
        return self


class AccountRead(BaseModel):
    """Safe Account response; secret material is represented by presence only."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    display_name: str
    username: str | None
    email: str | None
    phone: str | None
    platform: str
    status: str
    registration_state: str
    health_status: str
    status_reason: str | None
    niche: str | None
    notes: str | None
    tags: list[str]
    runtime_id: int | None
    device_id: int | None
    follower_count: int | None
    following_count: int | None
    likes_count: int | None
    video_count: int | None
    metrics_updated_at: datetime | None
    secret_present: bool
    secret_types: list[AccountSecretType]
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class AccountList(BaseModel):
    items: list[AccountRead]
    total: int
    page: int
    page_size: int


class AccountRuntimeAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runtime_id: int = Field(gt=0)


class AccountSecretWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: SecretStr = Field(min_length=1, max_length=4096)


class AccountSecretMetadata(BaseModel):
    secret_type: AccountSecretType
    present: bool
    updated_at: datetime | None = None
