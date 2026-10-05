"""Add durable workflow orchestration.

Revision ID: 20261005_0018
Revises: 20261005_0017
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0018"
down_revision: str | None = "20261005_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("idempotency_key", sa.String(128)),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("template_key", sa.String(100), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("runtime_id", sa.Integer(), sa.ForeignKey("runtimes.id", ondelete="SET NULL")),
        sa.Column("runtime_id_snapshot", sa.Integer()),
        sa.Column("content_asset_id", sa.Integer(), sa.ForeignKey("content_assets.id", ondelete="RESTRICT")),
        sa.Column("content_asset_version_id", sa.Integer(), sa.ForeignKey("content_asset_versions.id", ondelete="RESTRICT")),
        sa.Column("current_step_id", sa.Integer()),
        sa.Column("transition_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pause_requested_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_message", sa.String(500)),
        sa.CheckConstraint("status IN ('draft','pending','running','waiting','paused','succeeded','failed','cancelling','cancelled')", name="ck_workflows_status"),
        sa.CheckConstraint("length(request_fingerprint) = 64", name="ck_workflows_fingerprint"),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 255", name="ck_workflows_name"),
        sa.CheckConstraint("description IS NULL OR length(description) <= 4000", name="ck_workflows_description"),
        sa.CheckConstraint("length(parameters_json) <= 16384", name="ck_workflows_parameters"),
        sa.CheckConstraint("transition_version >= 0", name="ck_workflows_transition_version"),
        sa.UniqueConstraint("idempotency_key", name="uq_workflows_idempotency_key"),
    )
    for column in ("template_key", "status", "account_id", "runtime_id", "content_asset_id", "content_asset_version_id", "created_at"):
        op.create_index(f"ix_workflows_{column}", "workflows", [column])

    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("step_key", sa.String(100), nullable=False),
        sa.Column("step_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("depends_on_step_id", sa.Integer(), sa.ForeignKey("workflow_steps.id", ondelete="SET NULL")),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON()),
        sa.Column("resume_at", sa.DateTime(timezone=True)),
        sa.Column("waiting_reason", sa.String(100)),
        sa.Column("approval_decision", sa.String(20)),
        sa.Column("approval_at", sa.DateTime(timezone=True)),
        sa.Column("approval_actor", sa.String(255)),
        sa.Column("approval_comment", sa.String(1000)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_message", sa.String(500)),
        sa.Column("transition_version", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("status IN ('pending','ready','running','waiting','succeeded','failed','skipped','cancelling','cancelled')", name="ck_workflow_steps_status"),
        sa.CheckConstraint("step_index >= 0", name="ck_workflow_steps_index"),
        sa.CheckConstraint("attempt > 0 AND max_attempts > 0", name="ck_workflow_steps_attempts"),
        sa.CheckConstraint("length(input_json) <= 16384", name="ck_workflow_steps_input"),
        sa.CheckConstraint("result_json IS NULL OR length(result_json) <= 16384", name="ck_workflow_steps_result"),
        sa.UniqueConstraint("workflow_id", "step_index", name="uq_workflow_steps_index"),
        sa.UniqueConstraint("workflow_id", "step_key", name="uq_workflow_steps_key"),
        sa.UniqueConstraint("job_id", name="uq_workflow_steps_job_id"),
    )
    for column in ("workflow_id", "status", "job_id"):
        op.create_index(f"ix_workflow_steps_{column}", "workflow_steps", [column])
    with op.batch_alter_table("workflows") as batch:
        batch.create_foreign_key("fk_workflows_current_step", "workflow_steps", ["current_step_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "workflow_step_job_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_step_id", sa.Integer(), sa.ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_attempt", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("step_attempt > 0", name="ck_workflow_step_job_runs_attempt"),
        sa.UniqueConstraint("workflow_step_id", "step_attempt", name="uq_workflow_step_job_run_attempt"),
        sa.UniqueConstraint("job_id", name="uq_workflow_step_job_runs_job_id"),
    )
    op.create_index("ix_workflow_step_job_runs_workflow_step_id", "workflow_step_job_runs", ["workflow_step_id"])

    op.create_table(
        "workflow_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_step_id", sa.Integer(), sa.ForeignKey("workflow_steps.id", ondelete="SET NULL")),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(metadata_json) <= 8192", name="ck_workflow_events_metadata"),
        sa.CheckConstraint("event_type IN ('workflow_created','workflow_started','workflow_paused','workflow_resumed','step_ready','step_started','job_created','step_succeeded','step_failed','waiting_for_approval','approved','rejected','retry_requested','cancellation_requested','workflow_succeeded','workflow_failed','workflow_cancelled')", name="ck_workflow_events_type"),
    )
    for column in ("workflow_id", "workflow_step_id", "job_id", "event_type", "created_at"):
        op.create_index(f"ix_workflow_events_{column}", "workflow_events", [column])


def downgrade() -> None:
    op.drop_table("workflow_events")
    op.drop_table("workflow_step_job_runs")
    with op.batch_alter_table("workflows") as batch:
        batch.drop_constraint("fk_workflows_current_step", type_="foreignkey")
    op.drop_table("workflow_steps")
    op.drop_table("workflows")
