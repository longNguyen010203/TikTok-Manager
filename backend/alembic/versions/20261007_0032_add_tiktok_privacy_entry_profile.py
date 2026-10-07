"""Add calibrated TikTok 44.4.3 privacy-entry profile v9.

Revision ID: 20261007_0032
Revises: 20261007_0031
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0032"
down_revision: str | None = "20261007_0031"
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
        "key": "trill-44-4-3", "version": 9,
        "package_name": "com.ss.android.ugc.trill",
        "min_version_code": 440403, "max_version_code": 440403,
        "min_version_name": "44.4.3", "max_version_name": "44.4.3",
        "locale_assumption": "en",
        "resource_key": "trill-44.4.3-privacy-entry-v9",
        "profile_fingerprint": "e73e1c311f4d1b432fcd38503f7fc6f3a832b322378d62825f6e03c5d7774f54",
        "status": "testing",
    }])


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM tiktok_ui_profiles WHERE key=:key AND version=:version"
    ).bindparams(key="trill-44-4-3", version=9))
