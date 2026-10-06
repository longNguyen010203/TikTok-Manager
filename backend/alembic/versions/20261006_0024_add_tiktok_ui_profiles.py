"""Add immutable TikTok UI profile metadata.

Revision ID: 20261006_0024
Revises: 20261006_0023
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0024"
down_revision: str | None = "20261006_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = op.create_table(
        "tiktok_ui_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("package_name", sa.String(255), nullable=False),
        sa.Column("min_version_code", sa.Integer()),
        sa.Column("max_version_code", sa.Integer()),
        sa.Column("min_version_name", sa.String(100)),
        sa.Column("max_version_name", sa.String(100)),
        sa.Column("locale_assumption", sa.String(35)),
        sa.Column("profile_fingerprint", sa.String(64), nullable=False),
        sa.Column("resource_key", sa.String(150), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("key", "version", name="uq_tiktok_ui_profile_key_version"),
        sa.UniqueConstraint("profile_fingerprint"),
        sa.CheckConstraint("version > 0", name="ck_tiktok_ui_profile_version"),
        sa.CheckConstraint("status IN ('testing','active','retired')", name="ck_tiktok_ui_profile_status"),
        sa.CheckConstraint("length(profile_fingerprint) = 64 AND profile_fingerprint = lower(profile_fingerprint) AND profile_fingerprint NOT GLOB '*[^0-9a-f]*'", name="ck_tiktok_ui_profile_fingerprint"),
        sa.CheckConstraint("min_version_code IS NULL OR max_version_code IS NULL OR min_version_code <= max_version_code", name="ck_tiktok_ui_profile_version_range"),
    )
    op.create_index("ix_tiktok_ui_profiles_package_name", "tiktok_ui_profiles", ["package_name"])
    op.create_index("ix_tiktok_ui_profiles_status", "tiktok_ui_profiles", ["status"])
    op.bulk_insert(table, [{
        "key": "trill-44-4-3", "version": 1,
        "package_name": "com.ss.android.ugc.trill",
        "min_version_code": 440403, "max_version_code": 440403,
        "min_version_name": "44.4.3", "max_version_name": "44.4.3",
        "locale_assumption": "en", "resource_key": "trill-44.4.3-testing-v1",
        "profile_fingerprint": "646dbe27f6da4a1b5bd54b7e91bcf7b7903b92e43e800e066bdf829b434636e9",
        "status": "testing",
    }])


def downgrade() -> None:
    op.drop_table("tiktok_ui_profiles")
