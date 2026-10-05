"""Strict public schemas for server-owned workflow orchestration."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkflowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    template_key: str = Field(min_length=1, max_length=100)
    template_version: int | None = Field(default=None, gt=0)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    runtime_id: int = Field(gt=0)
    content_asset_id: int = Field(gt=0)
    content_asset_version_id: int | None = Field(default=None, gt=0)
    account_id: int | None = Field(default=None, gt=0)
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    actor: str = Field(min_length=1, max_length=255)
    comment: str | None = Field(default=None, max_length=1000)


class WorkflowStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    step_index: int
    step_key: str
    step_type: str
    status: str
    depends_on_step_id: int | None
    job_id: int | None
    attempt: int
    max_attempts: int
    result_json: dict[str, Any] | None
    resume_at: datetime | None
    waiting_reason: str | None
    approval_decision: str | None
    approval_at: datetime | None
    approval_actor: str | None
    approval_comment: str | None
    started_at: datetime | None
    completed_at: datetime | None
    error_code: str | None
    error_message: str | None


class WorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    name: str
    description: str | None
    template_key: str
    template_version: int
    status: str
    parameters: dict[str, Any]
    account_id: int | None
    runtime_id: int | None
    runtime_id_snapshot: int | None
    content_asset_id: int | None
    content_asset_version_id: int | None
    current_step_id: int | None
    transition_version: int
    pause_requested_at: datetime | None
    cancel_requested_at: datetime | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    error_code: str | None
    error_message: str | None
    steps: list[WorkflowStepRead]


class WorkflowList(BaseModel):
    items: list[WorkflowRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class WorkflowEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    workflow_id: int
    workflow_step_id: int | None
    job_id: int | None
    event_type: str
    metadata: dict[str, Any]
    created_at: datetime


class WorkflowEventList(BaseModel):
    items: list[WorkflowEventRead]
    total: int
    page: int
    page_size: int


class WorkflowTemplateRead(BaseModel):
    key: str
    version: int
    label: str
    description: str
    required_bindings: list[Literal["runtime_id", "content_asset_id"]]
    parameters_schema: dict[str, Any]
