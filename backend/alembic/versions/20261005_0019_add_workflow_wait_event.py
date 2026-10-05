"""Allow durable workflow wait events.

Revision ID: 20261005_0019
Revises: 20261005_0018
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261005_0019"
down_revision: str | None = "20261005_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OLD_EVENTS = (
    "'workflow_created','workflow_started','workflow_paused','workflow_resumed',"
    "'step_ready','step_started','job_created','step_succeeded','step_failed',"
    "'waiting_for_approval','approved','rejected','retry_requested',"
    "'cancellation_requested','workflow_succeeded','workflow_failed','workflow_cancelled'"
)
NEW_EVENTS = OLD_EVENTS.replace("'waiting_for_approval'", "'waiting','waiting_for_approval'")


def upgrade() -> None:
    with op.batch_alter_table("workflow_events") as batch:
        batch.drop_constraint("ck_workflow_events_type", type_="check")
        batch.create_check_constraint(
            "ck_workflow_events_type", f"event_type IN ({NEW_EVENTS})"
        )


def downgrade() -> None:
    with op.batch_alter_table("workflow_events") as batch:
        batch.drop_constraint("ck_workflow_events_type", type_="check")
        batch.create_check_constraint(
            "ck_workflow_events_type", f"event_type IN ({OLD_EVENTS})"
        )
