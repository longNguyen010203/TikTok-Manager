"""Add reusable content library foundation.

Revision ID: 20261004_0014
Revises: 20261004_0013
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261004_0014"
down_revision: str | None = "20261004_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_blobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=32), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("detected_mime_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("size_bytes > 0", name="ck_content_blobs_size_positive"),
        sa.CheckConstraint(
            "length(sha256) = 64 AND sha256 = lower(sha256) "
            "AND sha256 NOT GLOB '*[^0-9a-f]*'",
            name="ck_content_blobs_sha256",
        ),
        sa.CheckConstraint(
            "length(storage_key) = 32 AND storage_key NOT GLOB '*[^0-9a-f]*' "
            "AND instr(storage_key, '/') = 0 AND instr(storage_key, '\\') = 0",
            name="ck_content_blobs_storage_key",
        ),
        sa.CheckConstraint(
            "length(detected_mime_type) BETWEEN 1 AND 100",
            name="ck_content_blobs_mime_length",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'orphaned', 'missing', 'deleted')",
            name="ck_content_blobs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
        sa.UniqueConstraint("sha256"),
    )
    op.create_index(op.f("ix_content_blobs_sha256"), "content_blobs", ["sha256"])

    op.create_table(
        "content_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("asset_type", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_version_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "asset_type IN ('video', 'image', 'audio', 'other')",
            name="ck_content_assets_type",
        ),
        sa.CheckConstraint(
            "source IN ('upload', 'promoted_artifact', 'generated', 'imported')",
            name="ck_content_assets_source",
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'ready', 'invalid', 'archived', 'deleted')",
            name="ck_content_assets_status",
        ),
        sa.CheckConstraint(
            "length(display_name) BETWEEN 1 AND 255",
            name="ck_content_assets_display_name",
        ),
        sa.CheckConstraint(
            "notes IS NULL OR length(notes) <= 4000",
            name="ck_content_assets_notes_length",
        ),
        sa.CheckConstraint(
            "current_version_id IS NULL OR current_version_id > 0",
            name="ck_content_assets_current_version",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_assets_asset_type"), "content_assets", ["asset_type"])
    op.create_index(op.f("ix_content_assets_source"), "content_assets", ["source"])
    op.create_index(op.f("ix_content_assets_status"), "content_assets", ["status"])
    op.create_index(op.f("ix_content_assets_created_at"), "content_assets", ["created_at"])

    op.create_table(
        "content_asset_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_asset_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("blob_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("detected_mime_type", sa.String(length=100), nullable=False),
        sa.Column("canonical_extension", sa.String(length=10), nullable=False),
        sa.Column("processing_status", sa.String(length=20), server_default="processing", nullable=False),
        sa.Column("source_job_artifact_id", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("codec", sa.String(length=100), nullable=True),
        sa.Column("frame_rate_numerator", sa.Integer(), nullable=True),
        sa.Column("frame_rate_denominator", sa.Integer(), nullable=True),
        sa.Column("container", sa.String(length=100), nullable=True),
        sa.Column("audio_present", sa.Boolean(), nullable=True),
        sa.Column("bitrate", sa.Integer(), nullable=True),
        sa.Column("sample_rate", sa.Integer(), nullable=True),
        sa.Column("channels", sa.Integer(), nullable=True),
        sa.Column("orientation", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version_number > 0", name="ck_content_versions_number"),
        sa.CheckConstraint(
            "processing_status IN ('processing', 'ready', 'invalid')",
            name="ck_content_versions_processing_status",
        ),
        sa.CheckConstraint(
            "length(original_filename) BETWEEN 1 AND 255",
            name="ck_content_versions_filename",
        ),
        sa.CheckConstraint(
            "length(detected_mime_type) BETWEEN 1 AND 100",
            name="ck_content_versions_mime",
        ),
        sa.CheckConstraint(
            "length(canonical_extension) BETWEEN 2 AND 10",
            name="ck_content_versions_extension",
        ),
        sa.CheckConstraint(
            "metadata_json IS NULL OR length(metadata_json) <= 16384",
            name="ck_content_versions_metadata_size",
        ),
        sa.ForeignKeyConstraint(["blob_id"], ["content_blobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["content_asset_id"], ["content_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_job_artifact_id"], ["job_artifacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_asset_id", "version_number", name="uq_content_asset_version"),
    )
    op.create_index(op.f("ix_content_asset_versions_blob_id"), "content_asset_versions", ["blob_id"])
    op.create_index(op.f("ix_content_asset_versions_content_asset_id"), "content_asset_versions", ["content_asset_id"])
    op.create_index(op.f("ix_content_asset_versions_source_job_artifact_id"), "content_asset_versions", ["source_job_artifact_id"])

    op.create_table(
        "content_variants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_version_id", sa.Integer(), nullable=False),
        sa.Column("blob_id", sa.Integer(), nullable=True),
        sa.Column("variant_kind", sa.String(length=50), nullable=False),
        sa.Column("profile_name", sa.String(length=100), nullable=False),
        sa.Column("profile_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("detected_mime_type", sa.String(length=100), nullable=True),
        sa.Column("canonical_extension", sa.String(length=10), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('processing', 'ready', 'invalid', 'deleted')",
            name="ck_content_variants_status",
        ),
        sa.ForeignKeyConstraint(["blob_id"], ["content_blobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_version_id"], ["content_asset_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_version_id", "variant_kind", "profile_fingerprint", name="uq_content_variant_profile"),
    )
    op.create_index(op.f("ix_content_variants_blob_id"), "content_variants", ["blob_id"])
    op.create_index(op.f("ix_content_variants_source_version_id"), "content_variants", ["source_version_id"])

    op.create_table(
        "content_asset_tags",
        sa.Column("content_asset_id", sa.Integer(), nullable=False),
        sa.Column("tag", sa.String(length=50), nullable=False),
        sa.CheckConstraint(
            "length(tag) BETWEEN 1 AND 50 AND tag = lower(tag)",
            name="ck_content_asset_tags_normalized",
        ),
        sa.ForeignKeyConstraint(["content_asset_id"], ["content_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_asset_id", "tag"),
    )

    op.create_table(
        "content_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_asset_id", sa.Integer(), nullable=False),
        sa.Column("content_asset_version_id", sa.Integer(), nullable=False),
        sa.Column("content_variant_id", sa.Integer(), nullable=True),
        sa.Column("runtime_id", sa.Integer(), nullable=True),
        sa.Column("runtime_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("remote_filename", sa.String(length=255), nullable=True),
        sa.Column("remote_path", sa.String(length=512), nullable=True),
        sa.Column("media_uri", sa.String(length=512), nullable=True),
        sa.Column("delivered_sha256", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'delivering', 'succeeded', 'failed', 'cancelled')",
            name="ck_content_deliveries_status",
        ),
        sa.CheckConstraint("runtime_id_snapshot > 0", name="ck_content_deliveries_runtime_snapshot"),
        sa.ForeignKeyConstraint(["content_asset_id"], ["content_assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["content_asset_version_id"], ["content_asset_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["content_variant_id"], ["content_variants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["runtime_id"], ["runtimes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index(op.f("ix_content_deliveries_content_asset_id"), "content_deliveries", ["content_asset_id"])
    op.create_index(op.f("ix_content_deliveries_runtime_id"), "content_deliveries", ["runtime_id"])

    op.create_table(
        "content_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_asset_id", sa.Integer(), nullable=False),
        sa.Column("content_asset_version_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('uploaded', 'metadata_updated', 'archived', "
            "'restored', 'deleted', 'version_added')",
            name="ck_content_events_type",
        ),
        sa.CheckConstraint(
            "metadata_json IS NULL OR length(metadata_json) <= 8192",
            name="ck_content_events_metadata_size",
        ),
        sa.ForeignKeyConstraint(["content_asset_id"], ["content_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_asset_version_id"], ["content_asset_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_events_content_asset_id"), "content_events", ["content_asset_id"])
    op.create_index(op.f("ix_content_events_event_type"), "content_events", ["event_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_content_events_event_type"), table_name="content_events")
    op.drop_index(op.f("ix_content_events_content_asset_id"), table_name="content_events")
    op.drop_table("content_events")
    op.drop_index(op.f("ix_content_deliveries_runtime_id"), table_name="content_deliveries")
    op.drop_index(op.f("ix_content_deliveries_content_asset_id"), table_name="content_deliveries")
    op.drop_table("content_deliveries")
    op.drop_table("content_asset_tags")
    op.drop_index(op.f("ix_content_variants_source_version_id"), table_name="content_variants")
    op.drop_index(op.f("ix_content_variants_blob_id"), table_name="content_variants")
    op.drop_table("content_variants")
    op.drop_index(op.f("ix_content_asset_versions_source_job_artifact_id"), table_name="content_asset_versions")
    op.drop_index(op.f("ix_content_asset_versions_content_asset_id"), table_name="content_asset_versions")
    op.drop_index(op.f("ix_content_asset_versions_blob_id"), table_name="content_asset_versions")
    op.drop_table("content_asset_versions")
    op.drop_index(op.f("ix_content_assets_created_at"), table_name="content_assets")
    op.drop_index(op.f("ix_content_assets_status"), table_name="content_assets")
    op.drop_index(op.f("ix_content_assets_source"), table_name="content_assets")
    op.drop_index(op.f("ix_content_assets_asset_type"), table_name="content_assets")
    op.drop_table("content_assets")
    op.drop_index(op.f("ix_content_blobs_sha256"), table_name="content_blobs")
    op.drop_table("content_blobs")
