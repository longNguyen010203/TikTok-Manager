"""Server-owned adapters from Workflow steps to existing execution services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.models import Job, JobStatus, ManagedApp, PublishingSession, Workflow, WorkflowStep, WorkflowStepJobRun
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
        if workflow.account_id is not None:
            job.account_id = workflow.account_id
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


def _link_job(session: Session, step: WorkflowStep, job: Job) -> None:
    session.add(job)
    session.flush()
    run = session.query(WorkflowStepJobRun).filter_by(
        workflow_step_id=step.id, step_attempt=step.attempt
    ).one_or_none()
    if run is None:
        session.add(WorkflowStepJobRun(
            workflow_step_id=step.id, step_attempt=step.attempt, job_id=job.id
        ))
    elif run.job_id != job.id:
        raise ValueError("Workflow step attempt is linked to another Job")


class PublishingCheckStepAdapter:
    def __init__(self, step_type: str) -> None:
        self.step_type = step_type

    def materialize(self, session: Session, workflow: Workflow, step: WorkflowStep) -> MaterializedStepJob:
        record = session.query(PublishingSession).filter_by(workflow_id=workflow.id).one_or_none()
        if record is None or workflow.runtime_id is None:
            raise ValueError("Publishing session binding is unavailable")
        job = Job(
            job_type=self.step_type, status=JobStatus.PENDING.value,
            runtime_id=workflow.runtime_id, account_id=workflow.account_id,
            payload={"publishing_session_id": record.id}, max_attempts=3,
            execution_stage="queued",
        )
        _link_job(session, step, job)
        return MaterializedStepJob(job=job, created=True)


class ManagedAppLaunchStepAdapter:
    step_type = "device.launch_app"

    def materialize(self, session: Session, workflow: Workflow, step: WorkflowStep) -> MaterializedStepJob:
        app = session.get(ManagedApp, workflow.managed_app_id) if workflow.managed_app_id else None
        if app is None or workflow.runtime_id is None:
            raise ValueError("Pinned managed app binding is unavailable")
        job = Job(
            job_type="device.launch_app", status=JobStatus.PENDING.value,
            runtime_id=workflow.runtime_id, account_id=workflow.account_id,
            payload={"package_name": app.android_package_name}, max_attempts=3,
            execution_stage="queued",
        )
        _link_job(session, step, job)
        return MaterializedStepJob(job=job, created=True)


def default_workflow_adapters() -> dict[str, WorkflowStepAdapter]:
    adapters: list[WorkflowStepAdapter] = [
        ContentDeliverStepAdapter(), ManagedAppLaunchStepAdapter(),
        PublishingCheckStepAdapter("publishing.verify_runtime"),
        PublishingCheckStepAdapter("publishing.verify_app"),
        PublishingCheckStepAdapter("publishing.verify_app_state"),
    ]
    return {adapter.step_type: adapter for adapter in adapters}
