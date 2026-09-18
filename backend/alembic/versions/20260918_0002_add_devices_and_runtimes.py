"""Add devices, runtimes, and account runtime assignment.

Revision ID: 20260918_0002
Revises: 20260918_0001
Create Date: 2026-09-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260918_0002"
down_revision: str | None = "20260918_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add device and runtime management tables and relationships."""
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("device_type", sa.String(length=50), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("os_version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "runtimes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("runtime_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runtimes_device_id", "runtimes", ["device_id"])

    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(sa.Column("runtime_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_accounts_runtime_id", ["runtime_id"])
        batch_op.create_foreign_key(
            "fk_accounts_runtime_id_runtimes",
            "runtimes",
            ["runtime_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Remove device and runtime management tables and relationships."""
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_constraint(
            "fk_accounts_runtime_id_runtimes", type_="foreignkey"
        )
        batch_op.drop_index("ix_accounts_runtime_id")
        batch_op.drop_column("runtime_id")

    op.drop_index("ix_runtimes_device_id", table_name="runtimes")
    op.drop_table("runtimes")
    op.drop_table("devices")
