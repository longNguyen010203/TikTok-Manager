"""Add durable per-Runtime managed application installation state.

Revision ID: 20261005_0021
Revises: 20261005_0020
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0021"
down_revision: str | None = "20261005_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runtime_app_installations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("runtime_id", sa.Integer(), sa.ForeignKey("runtimes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("runtime_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("managed_app_id", sa.Integer(), sa.ForeignKey("managed_apps.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("desired_managed_app_version_id", sa.Integer(), sa.ForeignKey("managed_app_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("observed_managed_app_version_id", sa.Integer(), sa.ForeignKey("managed_app_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("observed_package_name", sa.String(255)),
        sa.Column("observed_version_name", sa.String(255)),
        sa.Column("observed_version_code", sa.Integer()),
        sa.Column("observed_signer_fingerprint", sa.String(64)),
        sa.Column("latest_job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("installed_at", sa.DateTime(timezone=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("runtime_id_snapshot > 0", name="ck_runtime_app_installations_snapshot"),
        sa.CheckConstraint(
            "status IN ('pending','installing','installed','failed','outdated','removed')",
            name="ck_runtime_app_installations_status",
        ),
        sa.CheckConstraint("observed_version_code IS NULL OR observed_version_code >= 0", name="ck_runtime_app_installations_version_code"),
        sa.CheckConstraint("error_message IS NULL OR length(error_message) <= 500", name="ck_runtime_app_installations_error"),
        sa.UniqueConstraint("runtime_id", "managed_app_id", name="uq_runtime_app_installation_live_app"),
        sa.UniqueConstraint("latest_job_id", name="uq_runtime_app_installation_latest_job"),
    )
    for column in (
        "runtime_id", "managed_app_id", "desired_managed_app_version_id",
        "observed_managed_app_version_id", "status", "latest_job_id",
    ):
        op.create_index(
            f"ix_runtime_app_installations_{column}",
            "runtime_app_installations",
            [column],
        )

    op.create_table(
        "runtime_app_installation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "runtime_app_installation_id",
            sa.Integer(),
            sa.ForeignKey("runtime_app_installations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "desired_managed_app_version_id",
            sa.Integer(),
            sa.ForeignKey("managed_app_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", name="uq_runtime_app_installation_run_job"),
    )
    op.create_index(
        "ix_runtime_app_installation_runs_installation",
        "runtime_app_installation_runs",
        ["runtime_app_installation_id"],
    )

    # Extend the append-only event vocabulary; installation identifiers remain
    # bounded metadata so historical events survive Runtime FK clearing.
    with op.batch_alter_table("managed_app_events") as batch:
        batch.drop_constraint("ck_managed_app_events_type", type_="check")
        batch.create_check_constraint(
            "ck_managed_app_events_type",
            "event_type IN ('app_created','version_uploaded','inspection_queued','inspection_started',"
            "'version_ready','version_invalid','version_activated','version_retired','app_updated',"
            "'installation_created','install_requested','install_started','install_succeeded',"
            "'install_failed','verify_requested','verified','marked_outdated','runtime_removed')",
        )


def downgrade() -> None:
    with op.batch_alter_table("managed_app_events") as batch:
        batch.drop_constraint("ck_managed_app_events_type", type_="check")
        batch.create_check_constraint(
            "ck_managed_app_events_type",
            "event_type IN ('app_created','version_uploaded','inspection_queued','inspection_started',"
            "'version_ready','version_invalid','version_activated','version_retired','app_updated')",
        )
    op.drop_table("runtime_app_installation_runs")
    op.drop_table("runtime_app_installations")
