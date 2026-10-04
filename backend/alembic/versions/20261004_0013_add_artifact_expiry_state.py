"""Add explicit artifact expiry state.

Revision ID: 20261004_0013
Revises: 20261004_0012
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261004_0013"
down_revision: str | None = "20261004_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_artifacts") as batch:
        batch.drop_constraint(
            "ck_job_artifacts_cleanup_status", type_="check"
        )
        batch.create_check_constraint(
            "ck_job_artifacts_cleanup_status",
            "cleanup_status IN ('active', 'expired', 'deleted', 'failed')",
        )


def downgrade() -> None:
    op.execute(
        "UPDATE job_artifacts SET cleanup_status = 'deleted' "
        "WHERE cleanup_status = 'expired'"
    )
    with op.batch_alter_table("job_artifacts") as batch:
        batch.drop_constraint(
            "ck_job_artifacts_cleanup_status", type_="check"
        )
        batch.create_check_constraint(
            "ck_job_artifacts_cleanup_status",
            "cleanup_status IN ('active', 'deleted', 'failed')",
        )
