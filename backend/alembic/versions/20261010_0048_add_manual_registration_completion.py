"""Add Account manual registration completion metadata.

Revision ID: 20261010_0048
Revises: 20261007_0047
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261010_0048"
down_revision: str | None = "20261007_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(
            sa.Column("registration_completed_at", sa.DateTime(timezone=True))
        )


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("registration_completed_at")
