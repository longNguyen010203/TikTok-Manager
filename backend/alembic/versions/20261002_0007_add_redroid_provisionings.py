"""Add durable managed Redroid provisioning records.

Revision ID: 20261002_0007
Revises: 20261001_0006
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261002_0007"
down_revision: str | None = "20261001_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "redroid_provisionings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("ownership_token", sa.String(length=36), nullable=False),
        sa.Column("installation_id", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("device_number", sa.Integer(), nullable=True),
        sa.Column("container_name", sa.String(length=255), nullable=True),
        sa.Column("docker_container_id", sa.String(length=255), nullable=True),
        sa.Column("adb_host_port", sa.Integer(), nullable=True),
        sa.Column("adb_serial", sa.String(length=255), nullable=True),
        sa.Column("data_path", sa.String(length=1024), nullable=True),
        sa.Column("network_name", sa.String(length=255), nullable=True),
        sa.Column("docker_network_id", sa.String(length=255), nullable=True),
        sa.Column("image_reference", sa.String(length=512), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("runtime_id", sa.Integer(), nullable=True),
        sa.Column("data_directory_created", sa.Boolean(), nullable=False),
        sa.Column("network_created", sa.Boolean(), nullable=False),
        sa.Column("container_created", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('requested', 'preflighting', 'reserved', 'data_created', "
            "'network_created', 'container_created', 'inspected', 'completed', "
            "'rolling_back', 'rolled_back', 'failed', 'rollback_failed', "
            "'inconsistent')",
            name="ck_redroid_provisionings_state",
        ),
        sa.CheckConstraint(
            "device_number IS NULL OR device_number > 0",
            name="ck_redroid_provisionings_device_number_positive",
        ),
        sa.CheckConstraint(
            "adb_host_port IS NULL OR (adb_host_port >= 1024 AND adb_host_port <= 65535)",
            name="ck_redroid_provisionings_adb_host_port_range",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["runtime_id"], ["runtimes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("ownership_token"),
        sa.UniqueConstraint("device_number"),
        sa.UniqueConstraint("container_name"),
        sa.UniqueConstraint("adb_host_port"),
        sa.UniqueConstraint("adb_serial"),
        sa.UniqueConstraint("data_path"),
        sa.UniqueConstraint("network_name"),
        sa.UniqueConstraint("device_id"),
        sa.UniqueConstraint("runtime_id"),
    )


def downgrade() -> None:
    op.drop_table("redroid_provisionings")
