"""Make Redroid runtime identifiers unique.

Revision ID: 20261001_0006
Revises: 20261001_0005
Create Date: 2026-10-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261001_0006"
down_revision: str | None = "20261001_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Require non-null Docker container names and ADB serials to be unique."""
    with op.batch_alter_table("runtimes") as batch_op:
        batch_op.create_unique_constraint(
            "uq_runtimes_docker_container_name", ["docker_container_name"]
        )
        batch_op.create_unique_constraint(
            "uq_runtimes_adb_serial", ["adb_serial"]
        )


def downgrade() -> None:
    """Remove uniqueness from Redroid runtime identifiers."""
    with op.batch_alter_table("runtimes") as batch_op:
        batch_op.drop_constraint("uq_runtimes_adb_serial", type_="unique")
        batch_op.drop_constraint(
            "uq_runtimes_docker_container_name", type_="unique"
        )
