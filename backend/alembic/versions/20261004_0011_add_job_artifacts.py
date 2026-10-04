"""Add durable managed automation artifacts.

Revision ID: 20261004_0011
Revises: 20261004_0010
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261004_0011"
down_revision: str | None = "20261004_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cleanup_status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
        sa.CheckConstraint(
            "size_bytes >= 0", name="ck_job_artifacts_size_nonnegative"
        ),
        sa.CheckConstraint(
            "cleanup_status IN ('active', 'deleted', 'failed')",
            name="ck_job_artifacts_cleanup_status",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        op.f("ix_job_artifacts_job_id"), "job_artifacts", ["job_id"], unique=False
    )
    op.create_index(
        op.f("ix_job_artifacts_expires_at"),
        "job_artifacts",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_job_artifacts_expires_at"), table_name="job_artifacts")
    op.drop_index(op.f("ix_job_artifacts_job_id"), table_name="job_artifacts")
    op.drop_table("job_artifacts")
