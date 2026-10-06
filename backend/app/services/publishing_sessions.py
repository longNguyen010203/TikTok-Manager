"""Projection of authoritative Workflow state into publishing domain history."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PublishingSession, Workflow, WorkflowStep
from app.models.timestamps import utc_now


def sync_publishing_session(session: Session, workflow: Workflow) -> None:
    if workflow.template_key != "publishing_prepare_review":
        return
    record = session.scalar(select(PublishingSession).where(PublishingSession.workflow_id == workflow.id))
    if record is None:
        return
    approval = session.scalar(select(WorkflowStep).where(
        WorkflowStep.workflow_id == workflow.id,
        WorkflowStep.step_type == "workflow.approval",
    ))
    if workflow.status == "cancelled":
        status = "cancelled"
    elif workflow.error_code == "WORKFLOW_APPROVAL_REJECTED" or (approval and approval.approval_decision == "rejected"):
        status = "rejected"
    elif workflow.status == "failed":
        status = "failed"
    elif workflow.status == "succeeded" or (approval and approval.approval_decision == "approved"):
        status = "prepared"
    elif workflow.status == "waiting" and approval and workflow.current_step_id == approval.id:
        status = "waiting_approval"
    else:
        status = "preparing"
    record.status = status
    record.error_code = workflow.error_code
    record.error_message = workflow.error_message
    if status == "prepared":
        record.prepared_at = record.prepared_at or utc_now()
        record.approved_at = record.approved_at or (approval.approval_at if approval else None)
