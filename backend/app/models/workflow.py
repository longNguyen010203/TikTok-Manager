"""Durable workflow orchestration models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.timestamps import utc_now


WORKFLOW_STATUSES = (
    "draft", "pending", "running", "waiting", "paused",
    "succeeded", "failed", "cancelling", "cancelled",
)
WORKFLOW_STEP_STATUSES = (
    "pending", "ready", "running", "waiting", "succeeded",
    "failed", "skipped", "cancelling", "cancelled",
)
WORKFLOW_EVENT_TYPES = (
    "workflow_created", "workflow_started", "workflow_paused",
    "workflow_resumed", "step_ready", "step_started", "job_created",
    "step_succeeded", "step_failed", "waiting", "waiting_for_approval", "approved",
    "rejected", "retry_requested", "cancellation_requested",
    "workflow_succeeded", "workflow_failed", "workflow_cancelled",
)


class Workflow(Base):
    __tablename__ = "workflows"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','pending','running','waiting','paused','succeeded',"
            "'failed','cancelling','cancelled')", name="ck_workflows_status",
        ),
        CheckConstraint("length(request_fingerprint) = 64", name="ck_workflows_fingerprint"),
        CheckConstraint("length(name) BETWEEN 1 AND 255", name="ck_workflows_name"),
        CheckConstraint("description IS NULL OR length(description) <= 4000", name="ck_workflows_description"),
        CheckConstraint("length(parameters_json) <= 16384", name="ck_workflows_parameters"),
        CheckConstraint("transition_version >= 0", name="ck_workflows_transition_version"),
        UniqueConstraint("idempotency_key", name="uq_workflows_idempotency_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    template_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), index=True)
    runtime_id: Mapped[int | None] = mapped_column(ForeignKey("runtimes.id", ondelete="SET NULL"), index=True)
    runtime_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    content_asset_id: Mapped[int | None] = mapped_column(ForeignKey("content_assets.id", ondelete="RESTRICT"), index=True)
    content_asset_version_id: Mapped[int | None] = mapped_column(ForeignKey("content_asset_versions.id", ondelete="RESTRICT"), index=True)
    current_step_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="SET NULL", use_alter=True, name="fk_workflows_current_step")
    )
    transition_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    pause_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    __table_args__ = (
        UniqueConstraint("workflow_id", "step_index", name="uq_workflow_steps_index"),
        UniqueConstraint("workflow_id", "step_key", name="uq_workflow_steps_key"),
        UniqueConstraint("job_id", name="uq_workflow_steps_job_id"),
        CheckConstraint("step_index >= 0", name="ck_workflow_steps_index"),
        CheckConstraint("attempt > 0 AND max_attempts > 0", name="ck_workflow_steps_attempts"),
        CheckConstraint("length(input_json) <= 16384", name="ck_workflow_steps_input"),
        CheckConstraint("result_json IS NULL OR length(result_json) <= 16384", name="ck_workflow_steps_result"),
        CheckConstraint(
            "status IN ('pending','ready','running','waiting','succeeded','failed',"
            "'skipped','cancelling','cancelled')", name="ck_workflow_steps_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_key: Mapped[str] = mapped_column(String(100), nullable=False)
    step_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    depends_on_step_id: Mapped[int | None] = mapped_column(ForeignKey("workflow_steps.id", ondelete="SET NULL"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    resume_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    waiting_reason: Mapped[str | None] = mapped_column(String(100))
    approval_decision: Mapped[str | None] = mapped_column(String(20))
    approval_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_actor: Mapped[str | None] = mapped_column(String(255))
    approval_comment: Mapped[str | None] = mapped_column(String(1000))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))
    transition_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)


class WorkflowStepJobRun(Base):
    __tablename__ = "workflow_step_job_runs"
    __table_args__ = (
        UniqueConstraint("workflow_step_id", "step_attempt", name="uq_workflow_step_job_run_attempt"),
        UniqueConstraint("job_id", name="uq_workflow_step_job_runs_job_id"),
        CheckConstraint("step_attempt > 0", name="ck_workflow_step_job_runs_attempt"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_step_id: Mapped[int] = mapped_column(ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False, index=True)
    step_attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    __table_args__ = (
        CheckConstraint("length(metadata_json) <= 8192", name="ck_workflow_events_metadata"),
        CheckConstraint(
            "event_type IN ('workflow_created','workflow_started','workflow_paused',"
            "'workflow_resumed','step_ready','step_started','job_created','step_succeeded',"
            "'step_failed','waiting','waiting_for_approval','approved','rejected','retry_requested',"
            "'cancellation_requested','workflow_succeeded','workflow_failed','workflow_cancelled')",
            name="ck_workflow_events_type",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_step_id: Mapped[int | None] = mapped_column(ForeignKey("workflow_steps.id", ondelete="SET NULL"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
