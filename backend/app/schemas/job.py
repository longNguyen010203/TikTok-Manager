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
    error_code: str | None = None
    error_retryable: bool | None = None
    cancellation_requested_at: datetime | None = None
    execution_stage: str | None = None


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
    error_code: str | None = Field(default=None, min_length=1, max_length=100)
    retryable: bool = False


class JobClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    claimed_by: str = Field(default="legacy-worker", min_length=1, max_length=100)


class JobClaimRead(JobRead):
    claim_token: str
    claimed_by: str
    lease_expires_at: datetime


class JobHeartbeatRead(BaseModel):
    job_id: int
    attempt: int
    status: str
    lease_expires_at: datetime
    cancellation_requested: bool


class JobExecuteRead(BaseModel):
    result: Any


class JobCancelAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    event_type: str | None = None
    message: str
    metadata: Any | None = Field(default=None, validation_alias="log_metadata")
    created_at: datetime
