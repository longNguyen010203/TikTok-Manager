"""Explicit Workflow and WorkflowStep transition validation."""

from __future__ import annotations

from app.models import Workflow, WorkflowStep
from app.models.timestamps import utc_now


WORKFLOW_TRANSITIONS = {
    "draft": {"pending", "cancelled"},
    "pending": {"running", "paused", "cancelling", "failed"},
    "running": {"waiting", "paused", "succeeded", "failed", "cancelling"},
    "waiting": {"running", "paused", "failed", "cancelling"},
    "paused": {"pending", "cancelling"},
    "failed": {"pending"},
    "cancelling": {"cancelled"},
    "succeeded": set(),
    "cancelled": set(),
}
STEP_TRANSITIONS = {
    "pending": {"ready", "cancelled"},
    "ready": {"running", "waiting", "cancelled"},
    "running": {"succeeded", "failed", "cancelling"},
    "waiting": {"succeeded", "failed", "cancelled"},
    "failed": {"ready"},
    "cancelling": {"cancelled"},
    "succeeded": set(),
    "skipped": set(),
    "cancelled": set(),
}


class WorkflowTransitionError(ValueError):
    def __init__(self, code: str, safe_message: str) -> None:
        self.code = code
        self.safe_message = safe_message
        super().__init__(safe_message)


def transition_workflow(workflow: Workflow, target: str) -> None:
    if target not in WORKFLOW_TRANSITIONS.get(workflow.status, set()):
        raise WorkflowTransitionError(
            "INVALID_WORKFLOW_TRANSITION",
            f"Workflow cannot transition from {workflow.status} to {target}",
        )
    now = utc_now()
    workflow.status = target
    workflow.transition_version += 1
    workflow.updated_at = now
    if target == "running" and workflow.started_at is None:
        workflow.started_at = now
    if target in {"succeeded", "failed"}:
        workflow.completed_at = now
    if target == "cancelled":
        workflow.cancelled_at = now
        workflow.completed_at = now


def transition_step(step: WorkflowStep, target: str) -> None:
    if target not in STEP_TRANSITIONS.get(step.status, set()):
        raise WorkflowTransitionError(
            "INVALID_WORKFLOW_STEP_TRANSITION",
            f"Workflow step cannot transition from {step.status} to {target}",
        )
    now = utc_now()
    step.status = target
    step.transition_version += 1
    if target in {"running", "waiting"} and step.started_at is None:
        step.started_at = now
    if target in {"succeeded", "failed", "skipped", "cancelled"}:
        step.completed_at = now
