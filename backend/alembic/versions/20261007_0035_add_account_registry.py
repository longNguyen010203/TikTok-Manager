"""Extend the canonical Account entity and add encrypted Account secrets.

Revision ID: 20261007_0035
Revises: 20261007_0034
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0035"
down_revision: str | None = "20261007_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.alter_column(
            "username", existing_type=sa.String(length=255), nullable=True
        )
        batch_op.add_column(sa.Column("display_name", sa.String(length=255)))
        batch_op.add_column(sa.Column("email", sa.String(length=320)))
        batch_op.add_column(sa.Column("phone", sa.String(length=50)))
        batch_op.add_column(
            sa.Column(
                "registration_state",
                sa.String(length=30),
                nullable=False,
                server_default="unknown",
            )
        )
        batch_op.add_column(
            sa.Column(
                "health_status",
                sa.String(length=30),
                nullable=False,
                server_default="unknown",
            )
        )
        batch_op.add_column(sa.Column("status_reason", sa.String(length=500)))
        batch_op.add_column(sa.Column("niche", sa.String(length=100)))
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("follower_count", sa.Integer()))
        batch_op.add_column(sa.Column("following_count", sa.Integer()))
        batch_op.add_column(sa.Column("likes_count", sa.Integer()))
        batch_op.add_column(sa.Column("video_count", sa.Integer()))
        batch_op.add_column(sa.Column("metrics_updated_at", sa.DateTime(timezone=True)))
        batch_op.create_check_constraint(
            "ck_accounts_registration_state",
            "registration_state IN ('unknown', 'pending', 'registered', 'failed')",
        )
        batch_op.create_check_constraint(
            "ck_accounts_health_status",
            "health_status IN ('unknown', 'healthy', 'warning', 'unhealthy')",
        )
        for column in ("follower_count", "following_count", "likes_count", "video_count"):
            batch_op.create_check_constraint(
                f"ck_accounts_{column}_nonnegative", f"{column} IS NULL OR {column} >= 0"
            )
        batch_op.create_index("ix_accounts_status", ["status"])
        batch_op.create_index("ix_accounts_niche", ["niche"])
        batch_op.create_index("ix_accounts_archived_at", ["archived_at"])

    op.execute(sa.text("UPDATE accounts SET display_name = name WHERE display_name IS NULL"))

    op.create_table(
        "account_tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("tag", sa.String(length=50), nullable=False),
        sa.CheckConstraint(
            "length(tag) BETWEEN 1 AND 50", name="ck_account_tags_length"
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "tag", name="uq_account_tags_account_tag"),
    )
    op.create_index("ix_account_tags_account_id", "account_tags", ["account_id"])

    op.create_table(
        "account_secrets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("secret_type", sa.String(length=40), nullable=False),
        sa.Column("encrypted_value", sa.LargeBinary(), nullable=False),
        sa.Column("encryption_version", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "secret_type IN ('account_password', 'email_password', 'recovery_credential')",
            name="ck_account_secrets_type",
        ),
        sa.CheckConstraint(
            "encryption_version = 'fernet-v1'",
            name="ck_account_secrets_encryption_version",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id", "secret_type", name="uq_account_secrets_account_type"
        ),
    )
    op.create_index(
        "ix_account_secrets_account_id", "account_secrets", ["account_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_account_secrets_account_id", table_name="account_secrets")
    op.drop_table("account_secrets")
    op.drop_index("ix_account_tags_account_id", table_name="account_tags")
    op.drop_table("account_tags")
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_index("ix_accounts_archived_at")
        batch_op.drop_index("ix_accounts_niche")
        batch_op.drop_index("ix_accounts_status")
        for column in ("follower_count", "following_count", "likes_count", "video_count"):
            batch_op.drop_constraint(
                f"ck_accounts_{column}_nonnegative", type_="check"
            )
        batch_op.drop_constraint("ck_accounts_registration_state", type_="check")
        batch_op.drop_constraint("ck_accounts_health_status", type_="check")
        batch_op.drop_column("metrics_updated_at")
        batch_op.drop_column("video_count")
        batch_op.drop_column("likes_count")
        batch_op.drop_column("following_count")
        batch_op.drop_column("follower_count")
        batch_op.drop_column("archived_at")
        batch_op.drop_column("niche")
        batch_op.drop_column("status_reason")
        batch_op.drop_column("registration_state")
        batch_op.drop_column("health_status")
        batch_op.drop_column("phone")
        batch_op.drop_column("email")
        batch_op.drop_column("display_name")
        batch_op.alter_column(
            "username", existing_type=sa.String(length=255), nullable=False
        )
