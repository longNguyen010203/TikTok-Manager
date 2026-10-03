"""Add durable managed Redroid deprovisioning state.

Revision ID: 20261003_0008
Revises: 20261002_0007
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0008"
down_revision: str | None = "20261002_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_STATES = (
    "requested", "preflighting", "reserved", "data_created", "network_created",
    "container_created", "inspected", "completed", "rolling_back",
    "rolled_back", "failed", "rollback_failed", "inconsistent",
)
_NEW_STATES = _OLD_STATES + (
    "deprovisioning", "deprovisioned", "deprovision_failed",
)


def _state_constraint(states: tuple[str, ...]) -> str:
    return "state IN (" + ", ".join(repr(value) for value in states) + ")"


def upgrade() -> None:
    with op.batch_alter_table("redroid_provisionings") as batch:
        batch.drop_constraint("ck_redroid_provisionings_state", type_="check")
        batch.add_column(sa.Column("historical_device_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("historical_runtime_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("container_removed", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.add_column(
            sa.Column("network_removed", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.add_column(
            sa.Column("data_preserved", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.create_check_constraint(
            "ck_redroid_provisionings_state", _state_constraint(_NEW_STATES)
        )


def downgrade() -> None:
    op.execute(
        "UPDATE redroid_provisionings SET state = 'inconsistent' "
        "WHERE state IN ('deprovisioning', 'deprovisioned', 'deprovision_failed')"
    )
    with op.batch_alter_table("redroid_provisionings") as batch:
        batch.drop_constraint("ck_redroid_provisionings_state", type_="check")
        batch.drop_column("data_preserved")
        batch.drop_column("network_removed")
        batch.drop_column("container_removed")
        batch.drop_column("historical_runtime_id")
        batch.drop_column("historical_device_id")
        batch.create_check_constraint(
            "ck_redroid_provisionings_state", _state_constraint(_OLD_STATES)
        )
