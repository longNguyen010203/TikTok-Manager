"""Add per-Runtime network desired and observed state.

Revision ID: 20261003_0009
Revises: 20261003_0008
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0009"
down_revision: str | None = "20261003_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MODE_FIELDS = (
    "(mode = 'direct' AND proxy_host IS NULL AND proxy_port IS NULL "
    "AND proxy_username_secret_ref IS NULL AND proxy_password_secret_ref IS NULL "
    "AND bridge_host_port IS NULL AND bridge_device_port IS NULL) OR "
    "(mode = 'http_proxy' AND proxy_host IS NOT NULL AND proxy_port IS NOT NULL "
    "AND bridge_host_port IS NOT NULL AND bridge_device_port IS NOT NULL)"
)


def _desired_columns(*, revision_name: str) -> list[sa.Column]:
    return [
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("proxy_host", sa.String(length=253), nullable=True),
        sa.Column("proxy_port", sa.Integer(), nullable=True),
        sa.Column("proxy_username_secret_ref", sa.String(length=255), nullable=True),
        sa.Column("proxy_password_secret_ref", sa.String(length=255), nullable=True),
        sa.Column("bridge_host_port", sa.Integer(), nullable=True),
        sa.Column("bridge_device_port", sa.Integer(), nullable=True),
        sa.Column(revision_name, sa.Integer(), nullable=False),
    ]


def _desired_checks(prefix: str, *, revision_name: str) -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint("mode IN ('direct', 'http_proxy')", name=f"ck_{prefix}_mode"),
        sa.CheckConstraint(_MODE_FIELDS, name=f"ck_{prefix}_mode_fields"),
        sa.CheckConstraint("proxy_port IS NULL OR (proxy_port >= 1 AND proxy_port <= 65535)", name=f"ck_{prefix}_proxy_port"),
        sa.CheckConstraint("bridge_host_port IS NULL OR (bridge_host_port >= 1 AND bridge_host_port <= 65535)", name=f"ck_{prefix}_bridge_host_port"),
        sa.CheckConstraint("bridge_device_port IS NULL OR (bridge_device_port >= 1 AND bridge_device_port <= 65535)", name=f"ck_{prefix}_bridge_device_port"),
        sa.CheckConstraint(f"{revision_name} > 0", name=f"ck_{prefix}_revision"),
    ]


def upgrade() -> None:
    op.create_table(
        "runtime_network_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("runtime_id", sa.Integer(), nullable=False),
        *_desired_columns(revision_name="desired_revision"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *_desired_checks("runtime_network_configs", revision_name="desired_revision"),
        sa.ForeignKeyConstraint(["runtime_id"], ["runtimes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("runtime_id"),
        sa.UniqueConstraint("bridge_host_port"),
    )
    op.create_index("ix_runtime_network_configs_runtime_id", "runtime_network_configs", ["runtime_id"], unique=True)

    op.create_table(
        "runtime_network_config_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("runtime_id", sa.Integer(), nullable=False),
        *_desired_columns(revision_name="revision"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        *_desired_checks("runtime_network_revisions", revision_name="revision"),
        sa.ForeignKeyConstraint(["runtime_id"], ["runtimes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("runtime_id", "revision", name="uq_runtime_network_revision"),
    )
    op.create_index("ix_runtime_network_config_revisions_runtime_id", "runtime_network_config_revisions", ["runtime_id"], unique=False)

    op.create_table(
        "runtime_network_states",
        sa.Column("runtime_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("desired_revision", sa.Integer(), nullable=False),
        sa.Column("applied_revision", sa.Integer(), nullable=True),
        sa.Column("observed_mode", sa.String(length=20), nullable=False),
        sa.Column("observed_android_proxy_host", sa.String(length=253), nullable=True),
        sa.Column("observed_android_proxy_port", sa.Integer(), nullable=True),
        sa.Column("reverse_present", sa.Boolean(), nullable=True),
        sa.Column("bridge_status", sa.String(length=20), nullable=False),
        sa.Column("bridge_owner_token", sa.String(length=36), nullable=True),
        sa.Column("bridge_supervisor_id", sa.String(length=255), nullable=True),
        sa.Column("bridge_pid", sa.Integer(), nullable=True),
        sa.Column("bridge_process_start_token", sa.String(length=100), nullable=True),
        sa.Column("last_apply_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_probe_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('disabled', 'pending', 'applying', 'ready', 'degraded', 'failed')", name="ck_runtime_network_states_status"),
        sa.CheckConstraint("observed_mode IN ('unknown', 'direct', 'http_proxy')", name="ck_runtime_network_states_observed_mode"),
        sa.CheckConstraint("bridge_status IN ('unknown', 'stopped', 'starting', 'running', 'unhealthy')", name="ck_runtime_network_states_bridge_status"),
        sa.CheckConstraint("desired_revision > 0", name="ck_runtime_network_states_desired_revision"),
        sa.CheckConstraint("applied_revision IS NULL OR applied_revision > 0", name="ck_runtime_network_states_applied_revision"),
        sa.CheckConstraint("observed_android_proxy_port IS NULL OR (observed_android_proxy_port >= 1 AND observed_android_proxy_port <= 65535)", name="ck_runtime_network_states_proxy_port"),
        sa.ForeignKeyConstraint(["runtime_id"], ["runtimes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("runtime_id"),
    )


def downgrade() -> None:
    op.drop_table("runtime_network_states")
    op.drop_index("ix_runtime_network_config_revisions_runtime_id", table_name="runtime_network_config_revisions")
    op.drop_table("runtime_network_config_revisions")
    op.drop_index("ix_runtime_network_configs_runtime_id", table_name="runtime_network_configs")
    op.drop_table("runtime_network_configs")
