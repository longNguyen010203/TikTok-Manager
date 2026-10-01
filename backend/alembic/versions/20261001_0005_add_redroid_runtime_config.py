"""Add Redroid connection configuration to runtimes.

Revision ID: 20261001_0005
Revises: 20260918_0004
Create Date: 2026-10-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20261001_0005"
down_revision: str | None = "20260918_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add optional Docker container and ADB serial identifiers."""
    with op.batch_alter_table("runtimes") as batch_op:
        batch_op.add_column(
            sa.Column("docker_container_name", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("adb_serial", sa.String(length=255), nullable=True)
        )


def downgrade() -> None:
    """Remove Redroid runtime configuration fields."""
    with op.batch_alter_table("runtimes") as batch_op:
        batch_op.drop_column("adb_serial")
        batch_op.drop_column("docker_container_name")
