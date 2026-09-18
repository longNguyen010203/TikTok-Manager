"""Pydantic schemas for job endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import JobStatus


class JobFields(BaseModel):
    """Fields shared by job creation and response payloads."""

    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, use_enum_values=True
    )

    job_type: str = Field(min_length=1, max_length=100)
    status: JobStatus = JobStatus.PENDING
    account_id: int | None = Field(default=None, gt=0)
    runtime_id: int | None = Field(default=None, gt=0)
    payload: Any | None = None
    result: Any | None = None
    error_message: str | None = None
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, gt=0)
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JobCreate(JobFields):
    """Payload for creating a job."""


class JobUpdate(BaseModel):
    """Payload for partially updating a job."""

    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, use_enum_values=True
    )

    job_type: str | None = Field(default=None, min_length=1, max_length=100)
    status: JobStatus | None = None
    account_id: int | None = Field(default=None, gt=0)
    runtime_id: int | None = Field(default=None, gt=0)
    payload: Any | None = None
    result: Any | None = None
    error_message: str | None = None
    attempt_count: int | None = Field(default=None, ge=0)
    max_attempts: int | None = Field(default=None, gt=0)
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @field_validator(
        "job_type", "status", "attempt_count", "max_attempts", mode="before"
    )
    @classmethod
    def required_fields_cannot_be_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class JobRead(JobFields):
    """Job representation returned by the API."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
        use_enum_values=True,
    )

    id: int
    created_at: datetime
    updated_at: datetime


class JobList(BaseModel):
    """Paginated job collection."""

    items: list[JobRead]
    total: int
    page: int
    page_size: int


class JobSucceeded(BaseModel):
    """Payload for marking a job successful."""

    model_config = ConfigDict(extra="forbid")

    result: Any | None = None


class JobFailed(BaseModel):
    """Payload for marking a job failed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    error_message: str | None = None


class JobRetry(BaseModel):
    """Payload for retrying a failed job."""

    model_config = ConfigDict(extra="forbid")

    scheduled_at: datetime | None = None


class JobLogRead(BaseModel):
    """Persistent Job log representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    level: str
    message: str
    metadata: Any | None = Field(default=None, validation_alias="log_metadata")
    created_at: datetime
