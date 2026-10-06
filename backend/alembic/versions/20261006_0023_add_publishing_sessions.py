"""Add pinned publishing bindings and publishing session history.

Revision ID: 20261006_0023
Revises: 20261006_0022
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0023"
down_revision: str | None = "20261006_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("workflows") as batch:
        batch.add_column(sa.Column("managed_app_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("managed_app_version_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_workflows_managed_app", "managed_apps", ["managed_app_id"], ["id"], ondelete="RESTRICT")
        batch.create_foreign_key("fk_workflows_managed_app_version", "managed_app_versions", ["managed_app_version_id"], ["id"], ondelete="RESTRICT")
        batch.create_index("ix_workflows_managed_app_id", ["managed_app_id"])
        batch.create_index("ix_workflows_managed_app_version_id", ["managed_app_version_id"])
    op.create_table(
        "publishing_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), sa.ForeignKey("workflows.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("account_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("runtime_id", sa.Integer(), sa.ForeignKey("runtimes.id", ondelete="SET NULL")),
        sa.Column("runtime_id_snapshot", sa.Integer(), nullable=False),
        sa.Column("content_asset_version_id", sa.Integer(), sa.ForeignKey("content_asset_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("managed_app_id", sa.Integer(), sa.ForeignKey("managed_apps.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("managed_app_version_id", sa.Integer(), sa.ForeignKey("managed_app_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="preparing"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prepared_at", sa.DateTime(timezone=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_message", sa.String(500)),
        sa.UniqueConstraint("workflow_id", name="uq_publishing_sessions_workflow"),
        sa.CheckConstraint("status IN ('preparing','waiting_approval','prepared','rejected','failed','cancelled')", name="ck_publishing_sessions_status"),
    )
    for name, cols in (
        ("ix_publishing_sessions_workflow_id", ["workflow_id"]),
        ("ix_publishing_sessions_account_id", ["account_id"]),
        ("ix_publishing_sessions_runtime_id", ["runtime_id"]),
        ("ix_publishing_sessions_status", ["status"]),
        ("ix_publishing_sessions_created_at", ["created_at"]),
    ):
        op.create_index(name, "publishing_sessions", cols)


def downgrade() -> None:
    op.drop_table("publishing_sessions")
    with op.batch_alter_table("workflows") as batch:
        batch.drop_index("ix_workflows_managed_app_version_id")
        batch.drop_index("ix_workflows_managed_app_id")
        batch.drop_constraint("fk_workflows_managed_app_version", type_="foreignkey")
        batch.drop_constraint("fk_workflows_managed_app", type_="foreignkey")
        batch.drop_column("managed_app_version_id")
        batch.drop_column("managed_app_id")
