"""Add Job claims, leases, cancellation, and structured log events.

Revision ID: 20261004_0012
Revises: 20261004_0011
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261004_0012"
down_revision: str | None = "20261004_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_constraint("ck_jobs_status", type_="check")
        batch.add_column(sa.Column("error_code", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("error_retryable", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("claim_token_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("claimed_by", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("execution_stage", sa.String(length=50), nullable=True))
        batch.create_check_constraint(
            "ck_jobs_status",
            "status IN ('pending', 'running', 'succeeded', 'failed', "
            "'retrying', 'cancelling', 'cancelled')",
        )
        batch.create_index(
            op.f("ix_jobs_lease_expires_at"), ["lease_expires_at"], unique=False
        )

    with op.batch_alter_table("job_logs") as batch:
        batch.add_column(sa.Column("event_type", sa.String(length=64), nullable=True))
        batch.create_index(op.f("ix_job_logs_event_type"), ["event_type"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("job_logs") as batch:
        batch.drop_index(op.f("ix_job_logs_event_type"))
        batch.drop_column("event_type")

    with op.batch_alter_table("jobs") as batch:
        batch.drop_index(op.f("ix_jobs_lease_expires_at"))
        batch.drop_constraint("ck_jobs_status", type_="check")
        batch.create_check_constraint(
            "ck_jobs_status",
            "status IN ('pending', 'running', 'succeeded', 'failed', "
            "'retrying', 'cancelled')",
        )
        for column in (
            "execution_stage",
            "execution_started_at",
            "cancellation_requested_at",
            "lease_expires_at",
            "heartbeat_at",
            "claimed_at",
            "claimed_by",
            "claim_token_hash",
            "error_retryable",
            "error_code",
        ):
            batch.drop_column(column)
