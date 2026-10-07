"""Add observed TikTok 44.4.3 ready-to-publish profile v7.

Revision ID: 20261007_0030
Revises: 20261007_0029
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0030"
down_revision: str | None = "20261007_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    profile = sa.table(
        "tiktok_ui_profiles",
        sa.column("key", sa.String), sa.column("version", sa.Integer),
        sa.column("package_name", sa.String), sa.column("min_version_code", sa.Integer),
        sa.column("max_version_code", sa.Integer), sa.column("min_version_name", sa.String),
        sa.column("max_version_name", sa.String), sa.column("locale_assumption", sa.String),
        sa.column("profile_fingerprint", sa.String), sa.column("resource_key", sa.String),
        sa.column("status", sa.String),
    )
    op.bulk_insert(profile, [{
        "key": "trill-44-4-3", "version": 7,
        "package_name": "com.ss.android.ugc.trill",
        "min_version_code": 440403, "max_version_code": 440403,
        "min_version_name": "44.4.3", "max_version_name": "44.4.3",
        "locale_assumption": "en",
        "resource_key": "trill-44.4.3-ready-v7",
        "profile_fingerprint": "6081585ed317b52f23b82cb251be6dfa381efd46c724473dd03c03d9ca4d1b4f",
        "status": "testing",
    }])


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM tiktok_ui_profiles WHERE key=:key AND version=:version"
    ).bindparams(key="trill-44-4-3", version=7))
