"""Add durable content inspection job ownership and events.

Revision ID: 20261004_0015
Revises: 20261004_0014
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261004_0015"
down_revision: str | None = "20261004_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("content_asset_versions") as batch:
        batch.add_column(sa.Column("inspection_job_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_content_versions_inspection_job",
            "jobs",
            ["inspection_job_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_unique_constraint(
            "uq_content_versions_inspection_job", ["inspection_job_id"]
        )
        batch.create_index(
            "ix_content_asset_versions_inspection_job_id", ["inspection_job_id"]
        )

    with op.batch_alter_table("content_events") as batch:
        batch.drop_constraint("ck_content_events_type", type_="check")
        batch.create_check_constraint(
            "ck_content_events_type",
            "event_type IN ('uploaded', 'processing_queued', 'processing_started', "
            "'ready', 'invalid', 'metadata_updated', 'archived', 'restored', "
            "'deleted', 'version_added')",
        )


def downgrade() -> None:
    with op.batch_alter_table("content_events") as batch:
        batch.drop_constraint("ck_content_events_type", type_="check")
        batch.create_check_constraint(
            "ck_content_events_type",
            "event_type IN ('uploaded', 'metadata_updated', 'archived', "
            "'restored', 'deleted', 'version_added')",
        )

    with op.batch_alter_table("content_asset_versions") as batch:
        batch.drop_index("ix_content_asset_versions_inspection_job_id")
        batch.drop_constraint("uq_content_versions_inspection_job", type_="unique")
        batch.drop_constraint("fk_content_versions_inspection_job", type_="foreignkey")
        batch.drop_column("inspection_job_id")
