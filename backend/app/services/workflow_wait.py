"""Validated, durable timing for non-busy Workflow wait steps."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


MAX_WAIT_SECONDS = 86_400


class WorkflowWaitError(ValueError):
    pass


class WorkflowWaitInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration_seconds: int | None = Field(default=None, ge=1, le=MAX_WAIT_SECONDS)
    resume_at: datetime | None = None

    @model_validator(mode="after")
    def exactly_one_time_source(self) -> "WorkflowWaitInput":
        if (self.duration_seconds is None) == (self.resume_at is None):
            raise ValueError("Exactly one wait time source is required")
        if self.resume_at is not None and self.resume_at.tzinfo is None:
            raise ValueError("resume_at must include a timezone")
        return self


def calculate_resume_at(payload: object, *, now: datetime) -> datetime:
    try:
        value = WorkflowWaitInput.model_validate(payload)
    except ValidationError as error:
        raise WorkflowWaitError("Workflow wait configuration is invalid") from error
    aware_now = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    if value.duration_seconds is not None:
        return aware_now + timedelta(seconds=value.duration_seconds)
    assert value.resume_at is not None
    result = value.resume_at.astimezone(timezone.utc)
    if result > aware_now + timedelta(seconds=MAX_WAIT_SECONDS):
        raise WorkflowWaitError("Workflow wait exceeds the maximum duration")
    return result


def is_due(resume_at: datetime, *, now: datetime) -> bool:
    aware_resume = resume_at if resume_at.tzinfo is not None else resume_at.replace(tzinfo=timezone.utc)
    aware_now = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    return aware_resume <= aware_now
