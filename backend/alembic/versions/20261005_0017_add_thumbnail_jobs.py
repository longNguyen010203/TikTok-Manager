"""Add durable thumbnail job linkage and content events.

Revision ID: 20261005_0017
Revises: 20261004_0016
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0017"
down_revision: str | None = "20261004_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("content_asset_versions") as batch:
        batch.add_column(sa.Column("thumbnail_job_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_content_asset_versions_thumbnail_job_id_jobs",
            "jobs", ["thumbnail_job_id"], ["id"], ondelete="SET NULL",
        )
        batch.create_unique_constraint(
            "uq_content_asset_versions_thumbnail_job_id", ["thumbnail_job_id"]
        )
        batch.create_index(
            "ix_content_asset_versions_thumbnail_job_id", ["thumbnail_job_id"]
        )
    with op.batch_alter_table("content_events") as batch:
        batch.drop_constraint("ck_content_events_type", type_="check")
        batch.create_check_constraint(
            "ck_content_events_type",
            "event_type IN ('uploaded', 'processing_queued', 'processing_started', "
            "'ready', 'invalid', 'metadata_updated', 'archived', 'restored', "
            "'deleted', 'version_added', 'delivery_requested', 'delivery_started', "
            "'delivered', 'delivery_failed', 'delivery_cancelled', 'delivery_repeated', "
            "'thumbnail_queued', 'thumbnail_ready', 'thumbnail_failed')",
        )


def downgrade() -> None:
    with op.batch_alter_table("content_events") as batch:
        batch.drop_constraint("ck_content_events_type", type_="check")
        batch.create_check_constraint(
            "ck_content_events_type",
            "event_type IN ('uploaded', 'processing_queued', 'processing_started', "
            "'ready', 'invalid', 'metadata_updated', 'archived', 'restored', "
            "'deleted', 'version_added', 'delivery_requested', 'delivery_started', "
            "'delivered', 'delivery_failed', 'delivery_cancelled', 'delivery_repeated')",
        )
    with op.batch_alter_table("content_asset_versions") as batch:
        batch.drop_index("ix_content_asset_versions_thumbnail_job_id")
        batch.drop_constraint("uq_content_asset_versions_thumbnail_job_id", type_="unique")
        batch.drop_constraint(
            "fk_content_asset_versions_thumbnail_job_id_jobs", type_="foreignkey"
        )
        batch.drop_column("thumbnail_job_id")
