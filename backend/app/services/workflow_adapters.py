"""Server-owned adapters from Workflow steps to existing execution services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.models import Job, Workflow, WorkflowStep, WorkflowStepJobRun
from app.services.content_delivery import ContentDeliveryService


@dataclass(frozen=True)
class MaterializedStepJob:
    job: Job
    created: bool


class WorkflowStepAdapter(Protocol):
    step_type: str

    def materialize(self, session: Session, workflow: Workflow, step: WorkflowStep) -> MaterializedStepJob: ...


class ContentDeliverStepAdapter:
    step_type = "content.deliver"

    def __init__(self, delivery_service: ContentDeliveryService | None = None) -> None:
        self.delivery_service = delivery_service or ContentDeliveryService()

    def materialize(self, session: Session, workflow: Workflow, step: WorkflowStep) -> MaterializedStepJob:
        if workflow.runtime_id is None or workflow.content_asset_id is None or workflow.content_asset_version_id is None:
            raise ValueError("Workflow bindings are no longer available")
        delivery, created = self.delivery_service.create(
            session,
            content_asset_id=workflow.content_asset_id,
            runtime_id=workflow.runtime_id,
            version_id=workflow.content_asset_version_id,
            filename=None,
            import_media=bool(step.input_json.get("import_media", True)),
            allow_repeat=False,
            idempotency_key=f"workflow:{workflow.id}:step:{step.id}:attempt:{step.attempt}",
            commit=False,
        )
        if delivery.job_id is None:
            raise ValueError("Content delivery did not create a Job")
        job = session.get(Job, delivery.job_id)
        if job is None:
            raise ValueError("Content delivery Job was not found")
        run = session.query(WorkflowStepJobRun).filter_by(
            workflow_step_id=step.id, step_attempt=step.attempt
        ).one_or_none()
        if run is None:
            session.add(WorkflowStepJobRun(
                workflow_step_id=step.id, step_attempt=step.attempt, job_id=job.id
            ))
        elif run.job_id != job.id:
            raise ValueError("Workflow step attempt is linked to another Job")
        return MaterializedStepJob(job=job, created=created)


def default_workflow_adapters() -> dict[str, WorkflowStepAdapter]:
    adapter = ContentDeliverStepAdapter()
    return {adapter.step_type: adapter}
