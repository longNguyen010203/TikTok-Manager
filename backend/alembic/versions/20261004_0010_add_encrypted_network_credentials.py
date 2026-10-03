"""Add encrypted per-Runtime proxy credentials.

Revision ID: 20261004_0010
Revises: 20261003_0009
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261004_0010"
down_revision: str | None = "20261003_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE_CHECK = (
    "(credential_source = 'none' AND proxy_username_secret_ref IS NULL "
    "AND proxy_password_secret_ref IS NULL) OR "
    "(mode = 'http_proxy' AND credential_source = 'environment_reference' AND "
    "(proxy_username_secret_ref IS NOT NULL OR proxy_password_secret_ref IS NOT NULL)) OR "
    "(mode = 'http_proxy' AND credential_source = 'stored_encrypted' "
    "AND proxy_username_secret_ref IS NULL "
    "AND proxy_password_secret_ref IS NULL)"
)


def upgrade() -> None:
    for table in (
        "runtime_network_configs",
        "runtime_network_config_revisions",
    ):
        with op.batch_alter_table(table) as batch:
            batch.add_column(
                sa.Column(
                    "credential_source",
                    sa.String(length=30),
                    nullable=False,
                    server_default="none",
                )
            )
        op.execute(
            sa.text(
                f"UPDATE {table} SET credential_source = "
                "CASE WHEN proxy_username_secret_ref IS NOT NULL "
                "OR proxy_password_secret_ref IS NOT NULL "
                "THEN 'environment_reference' ELSE 'none' END"
            )
        )
        with op.batch_alter_table(table) as batch:
            batch.create_check_constraint(
                f"ck_{'runtime_network_configs' if table.endswith('configs') else 'runtime_network_revisions'}_credential_source",
                _SOURCE_CHECK,
            )
            batch.alter_column("credential_source", server_default=None)

    op.create_table(
        "runtime_network_credentials",
        sa.Column("runtime_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_username", sa.LargeBinary(), nullable=False),
        sa.Column("encrypted_password", sa.LargeBinary(), nullable=False),
        sa.Column("encryption_version", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "encryption_version = 'fernet-v1'",
            name="ck_runtime_network_credentials_version",
        ),
        sa.CheckConstraint(
            "encrypted_username IS NOT NULL AND encrypted_password IS NOT NULL",
            name="ck_runtime_network_credentials_complete",
        ),
        sa.ForeignKeyConstraint(["runtime_id"], ["runtimes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("runtime_id"),
    )


def downgrade() -> None:
    op.drop_table("runtime_network_credentials")
    for table in (
        "runtime_network_config_revisions",
        "runtime_network_configs",
    ):
        constraint = (
            "ck_runtime_network_configs_credential_source"
            if table.endswith("configs")
            else "ck_runtime_network_revisions_credential_source"
        )
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(constraint, type_="check")
            batch.drop_column("credential_source")
