"""Add managed Android package admission and inspection metadata.

Revision ID: 20261005_0020
Revises: 20261005_0019
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0020"
down_revision: str | None = "20261005_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("content_assets") as batch:
        batch.add_column(sa.Column("purpose", sa.String(30), nullable=False, server_default="library"))
        batch.create_check_constraint(
            "ck_content_assets_purpose",
            "purpose IN ('library','managed_app_package')",
        )
        batch.create_index("ix_content_assets_purpose", ["purpose"])

    op.create_table(
        "managed_apps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("android_package_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("install_policy", sa.String(20), nullable=False, server_default="optional"),
        sa.Column("current_version_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(key) BETWEEN 1 AND 64", name="ck_managed_apps_key_length"),
        sa.CheckConstraint("length(display_name) BETWEEN 1 AND 255", name="ck_managed_apps_name_length"),
        sa.CheckConstraint("length(android_package_name) BETWEEN 3 AND 255", name="ck_managed_apps_package_length"),
        sa.CheckConstraint("status IN ('active','disabled','archived')", name="ck_managed_apps_status"),
        sa.CheckConstraint("install_policy IN ('required','optional','disabled')", name="ck_managed_apps_policy"),
        sa.UniqueConstraint("key", name="uq_managed_apps_key"),
        sa.UniqueConstraint("android_package_name", name="uq_managed_apps_package"),
    )
    op.create_index("ix_managed_apps_key", "managed_apps", ["key"])
    op.create_index("ix_managed_apps_status", "managed_apps", ["status"])

    op.create_table(
        "managed_app_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("managed_app_id", sa.Integer(), sa.ForeignKey("managed_apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_asset_id", sa.Integer(), sa.ForeignKey("content_assets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("content_asset_version_id", sa.Integer(), sa.ForeignKey("content_asset_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_name", sa.String(255)),
        sa.Column("version_code", sa.Integer()),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("discovered_package_name", sa.String(255)),
        sa.Column("min_sdk", sa.Integer()),
        sa.Column("target_sdk", sa.Integer()),
        sa.Column("signer_fingerprint", sa.String(64)),
        sa.Column("signer_metadata", sa.JSON()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("inspection_job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("inspector_name", sa.String(100), nullable=False, server_default="aapt2+apksigner"),
        sa.Column("inspector_version", sa.String(255)),
        sa.Column("validated_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('uploaded','inspecting','ready','invalid','retired')", name="ck_managed_app_versions_status"),
        sa.CheckConstraint("length(sha256) = 64 AND sha256 = lower(sha256) AND sha256 NOT GLOB '*[^0-9a-f]*'", name="ck_managed_app_versions_sha256"),
        sa.CheckConstraint("version_code IS NULL OR version_code >= 0", name="ck_managed_app_versions_code"),
        sa.CheckConstraint("signer_metadata IS NULL OR length(signer_metadata) <= 4096", name="ck_managed_app_versions_signers"),
        sa.CheckConstraint("error_message IS NULL OR length(error_message) <= 500", name="ck_managed_app_versions_error"),
        sa.UniqueConstraint("managed_app_id", "sha256", name="uq_managed_app_version_digest"),
        sa.UniqueConstraint("content_asset_version_id", name="uq_managed_app_content_version"),
        sa.UniqueConstraint("inspection_job_id", name="uq_managed_app_inspection_job"),
    )
    for column in ("managed_app_id", "sha256", "status", "inspection_job_id"):
        op.create_index(f"ix_managed_app_versions_{column}", "managed_app_versions", [column])
    with op.batch_alter_table("managed_apps") as batch:
        batch.create_foreign_key(
            "fk_managed_apps_current_version",
            "managed_app_versions",
            ["current_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    op.create_table(
        "managed_app_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("managed_app_id", sa.Integer(), sa.ForeignKey("managed_apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("managed_app_version_id", sa.Integer(), sa.ForeignKey("managed_app_versions.id", ondelete="SET NULL")),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("event_type IN ('app_created','version_uploaded','inspection_queued','inspection_started','version_ready','version_invalid','version_activated','version_retired','app_updated')", name="ck_managed_app_events_type"),
        sa.CheckConstraint("metadata_json IS NULL OR length(metadata_json) <= 8192", name="ck_managed_app_events_metadata"),
    )
    for column in ("managed_app_id", "managed_app_version_id", "job_id", "event_type"):
        op.create_index(f"ix_managed_app_events_{column}", "managed_app_events", [column])


def downgrade() -> None:
    op.drop_table("managed_app_events")
    with op.batch_alter_table("managed_apps") as batch:
        batch.drop_constraint("fk_managed_apps_current_version", type_="foreignkey")
    op.drop_table("managed_app_versions")
    op.drop_table("managed_apps")
    with op.batch_alter_table("content_assets") as batch:
        batch.drop_index("ix_content_assets_purpose")
        batch.drop_constraint("ck_content_assets_purpose", type_="check")
        batch.drop_column("purpose")
