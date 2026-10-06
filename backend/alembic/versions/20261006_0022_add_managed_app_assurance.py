"""Add explicit managed APK inspection assurance.

Revision ID: 20261006_0022
Revises: 20261005_0021
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0022"
down_revision: str | None = "20261005_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("managed_app_versions") as batch:
        batch.add_column(sa.Column("inspection_level", sa.String(20), nullable=False, server_default="basic"))
        batch.add_column(sa.Column("basic_approved_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint(
            "ck_managed_app_versions_inspection_level",
            "inspection_level IN ('basic','verified')",
        )
    op.execute(
        "UPDATE managed_app_versions SET inspection_level = 'verified' "
        "WHERE status IN ('ready','retired') AND validated_at IS NOT NULL"
    )
    with op.batch_alter_table("managed_app_events") as batch:
        batch.drop_constraint("ck_managed_app_events_type", type_="check")
        batch.create_check_constraint(
            "ck_managed_app_events_type",
            "event_type IN ('app_created','version_uploaded','inspection_queued','inspection_started',"
            "'version_ready','version_invalid','version_activated','version_retired','app_updated',"
            "'version_basic_approved','installation_created','install_requested','install_started',"
            "'install_succeeded','install_failed','verify_requested','verified','marked_outdated','runtime_removed')",
        )


def downgrade() -> None:
    with op.batch_alter_table("managed_app_events") as batch:
        batch.drop_constraint("ck_managed_app_events_type", type_="check")
        batch.create_check_constraint(
            "ck_managed_app_events_type",
            "event_type IN ('app_created','version_uploaded','inspection_queued','inspection_started',"
            "'version_ready','version_invalid','version_activated','version_retired','app_updated',"
            "'installation_created','install_requested','install_started','install_succeeded',"
            "'install_failed','verify_requested','verified','marked_outdated','runtime_removed')",
        )
    with op.batch_alter_table("managed_app_versions") as batch:
        batch.drop_constraint("ck_managed_app_versions_inspection_level", type_="check")
        batch.drop_column("basic_approved_at")
        batch.drop_column("inspection_level")
