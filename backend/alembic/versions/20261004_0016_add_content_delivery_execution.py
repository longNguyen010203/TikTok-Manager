"""Add executable content delivery state and history.

Revision ID: 20261004_0016
Revises: 20261004_0015
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261004_0016"
down_revision: str | None = "20261004_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table(
        "content_deliveries",
        naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
    ) as batch:
        batch.drop_constraint("uq_content_deliveries_idempotency_key", type_="unique")
        batch.alter_column("idempotency_key", existing_type=sa.String(255), nullable=True)
        batch.add_column(
            sa.Column("import_media", sa.Boolean(), server_default="0", nullable=False)
        )
        batch.alter_column("remote_filename", existing_type=sa.String(255), nullable=False)
        batch.alter_column("remote_path", existing_type=sa.String(512), nullable=False)
        batch.alter_column("delivered_at", new_column_name="completed_at")
        batch.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_unique_constraint(
            "uq_content_delivery_idempotency",
            ["content_asset_version_id", "runtime_id_snapshot", "idempotency_key"],
        )

    with op.batch_alter_table("content_events") as batch:
        batch.drop_constraint("ck_content_events_type", type_="check")
        batch.create_check_constraint(
            "ck_content_events_type",
            "event_type IN ('uploaded', 'processing_queued', 'processing_started', "
            "'ready', 'invalid', 'metadata_updated', 'archived', 'restored', "
            "'deleted', 'version_added', 'delivery_requested', 'delivery_started', "
            "'delivered', 'delivery_failed', 'delivery_cancelled', 'delivery_repeated')",
        )


def downgrade() -> None:
    with op.batch_alter_table("content_events") as batch:
        batch.drop_constraint("ck_content_events_type", type_="check")
        batch.create_check_constraint(
            "ck_content_events_type",
            "event_type IN ('uploaded', 'processing_queued', 'processing_started', "
            "'ready', 'invalid', 'metadata_updated', 'archived', 'restored', "
            "'deleted', 'version_added')",
        )

    with op.batch_alter_table(
        "content_deliveries",
        naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
    ) as batch:
        batch.drop_constraint("uq_content_delivery_idempotency", type_="unique")
        batch.drop_column("started_at")
        batch.alter_column("completed_at", new_column_name="delivered_at")
        batch.alter_column("remote_path", existing_type=sa.String(512), nullable=True)
        batch.alter_column("remote_filename", existing_type=sa.String(255), nullable=True)
        batch.drop_column("import_media")
        batch.alter_column("idempotency_key", existing_type=sa.String(255), nullable=False)
        batch.create_unique_constraint(
            "uq_content_deliveries_idempotency_key", ["idempotency_key"]
        )
