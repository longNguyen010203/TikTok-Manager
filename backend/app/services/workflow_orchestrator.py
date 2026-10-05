"""Restart-safe reconciler that advances Workflows by observing Jobs."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentAsset, ContentAssetVersion, Job, Runtime, Workflow, WorkflowStep
from app.models.timestamps import utc_now
from app.services.content_delivery import ContentDeliveryError
from app.services.job_lifecycle import cancel_job
from app.services.workflow_adapters import WorkflowStepAdapter, default_workflow_adapters
from app.services.workflow_lock import WorkflowOperationGuard, WorkflowOperationLockBusy
from app.services.workflow_service import append_workflow_event
from app.services.workflow_state import transition_step, transition_workflow
from app.services.workflow_wait import WorkflowWaitError, calculate_resume_at, is_due

LOGGER = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """Transitions durable orchestration state; never claims or executes Jobs."""

    def __init__(self, session_factory: Callable[[], Session], guard: WorkflowOperationGuard,
                 adapters: dict[str, WorkflowStepAdapter] | None = None) -> None:
        self.session_factory = session_factory
        self.guard = guard
        self.adapters = adapters or default_workflow_adapters()

    def run_once(self, *, limit: int = 100) -> int:
        with self.session_factory() as session:
            ids = list(session.scalars(
                select(Workflow.id).where(Workflow.status.in_([
                    "pending", "running", "waiting", "cancelling"
                ])).order_by(Workflow.updated_at, Workflow.id).limit(limit)
            ))
        reconciled = 0
        for workflow_id in ids:
            try:
                with self.guard.acquire_workflow(workflow_id, blocking=False):
                    with self.session_factory() as session:
                        workflow = session.get(Workflow, workflow_id)
                        if workflow is not None:
                            self.reconcile(session, workflow)
                            session.commit()
                            reconciled += 1
            except WorkflowOperationLockBusy:
                continue
            except Exception:
                LOGGER.exception("Workflow reconciliation failed for workflow_id=%s", workflow_id)
        return reconciled

    def reconcile(self, session: Session, workflow: Workflow) -> None:
        if workflow.status == "cancelling":
            self._reconcile_cancellation(session, workflow)
            return

        current = session.get(WorkflowStep, workflow.current_step_id) if workflow.current_step_id else None
        if workflow.status == "waiting":
            if current is None:
                self._fail_workflow_without_step(session, workflow, "WORKFLOW_CURRENT_STEP_MISSING", "Workflow current step was not found")
                return
            if current.step_type != "workflow.wait":
                return
            if not self._reconcile_wait(session, workflow, current):
                return

        if workflow.status == "pending":
            first_start = workflow.started_at is None
            transition_workflow(workflow, "running")
            if first_start:
                append_workflow_event(session, workflow, "workflow_started")

        current = session.get(WorkflowStep, workflow.current_step_id) if workflow.current_step_id else None
        if current is not None and current.status == "waiting":
            if current.step_type == "workflow.wait":
                if not self._reconcile_wait(session, workflow, current):
                    return
            else:
                transition_workflow(workflow, "waiting")
                return

        if current is not None and current.status == "running" and current.job_id:
            job = session.get(Job, current.job_id)
            if job is None:
                self._fail(session, workflow, current, "WORKFLOW_JOB_MISSING", "Workflow Job was not found")
                return
            if job.status == "succeeded":
                transition_step(current, "succeeded")
                current.result_json = self._safe_result(job.result, workflow=workflow, job=job)
                append_workflow_event(session, workflow, "step_succeeded", step=current, job_id=job.id)
                if workflow.pause_requested_at is not None:
                    workflow.pause_requested_at = None
                    transition_workflow(workflow, "paused")
                    append_workflow_event(session, workflow, "workflow_paused")
                    return
            elif job.status in {"failed", "cancelled"}:
                code = "WORKFLOW_JOB_CANCELLED" if job.status == "cancelled" else job.error_code or "WORKFLOW_JOB_FAILED"
                message = "Workflow Job was cancelled" if job.status == "cancelled" else job.error_message or "Workflow Job failed"
                self._fail(session, workflow, current, code, message)
                return
            else:
                return

        steps = list(session.scalars(
            select(WorkflowStep).where(WorkflowStep.workflow_id == workflow.id).order_by(WorkflowStep.step_index)
        ))
        next_step = next((step for step in steps if step.status in {"pending", "ready"}), None)
        if next_step is None:
            if all(step.status in {"succeeded", "skipped"} for step in steps):
                workflow.current_step_id = None
                transition_workflow(workflow, "succeeded")
                append_workflow_event(session, workflow, "workflow_succeeded")
            return
        if next_step.depends_on_step_id:
            dependency = session.get(WorkflowStep, next_step.depends_on_step_id)
            if dependency is None or dependency.status != "succeeded":
                return
        if next_step.status == "pending":
            transition_step(next_step, "ready")
            append_workflow_event(session, workflow, "step_ready", step=next_step)
        workflow.current_step_id = next_step.id

        if next_step.step_type == "workflow.approval":
            transition_step(next_step, "waiting")
            next_step.waiting_reason = "waiting_for_approval"
            transition_workflow(workflow, "waiting")
            append_workflow_event(session, workflow, "waiting_for_approval", step=next_step)
            return
        if next_step.step_type == "workflow.wait":
            self._enter_wait(session, workflow, next_step)
            return

        if next_step.job_id is not None:
            job = session.get(Job, next_step.job_id)
            if job is None or job.status not in {"pending", "retrying", "running"}:
                self._fail(session, workflow, next_step, "WORKFLOW_JOB_INVALID", "Workflow Job cannot be resumed")
                return
        else:
            binding_error = self._validate_runtime_content_bindings(session, workflow)
            if binding_error is not None:
                self._fail(session, workflow, next_step, *binding_error)
                return
            adapter = self.adapters.get(next_step.step_type)
            if adapter is None:
                self._fail(session, workflow, next_step, "WORKFLOW_STEP_UNSUPPORTED", "Workflow step type is unsupported")
                return
            try:
                materialized = adapter.materialize(session, workflow, next_step)
            except ContentDeliveryError as error:
                self._fail(session, workflow, next_step, error.code, error.safe_message)
                return
            except ValueError:
                self._fail(session, workflow, next_step, "WORKFLOW_STEP_MATERIALIZATION_FAILED", "Workflow step could not be materialized")
                return
            next_step.job_id = materialized.job.id
            append_workflow_event(session, workflow, "job_created", step=next_step, job_id=materialized.job.id)
        transition_step(next_step, "running")
        append_workflow_event(session, workflow, "step_started", step=next_step, job_id=next_step.job_id)

    def _enter_wait(self, session: Session, workflow: Workflow, step: WorkflowStep) -> None:
        try:
            if step.resume_at is None:
                step.resume_at = calculate_resume_at(step.input_json, now=utc_now())
        except WorkflowWaitError as error:
            self._fail(session, workflow, step, "WORKFLOW_WAIT_INVALID", str(error))
            return
        transition_step(step, "waiting")
        step.waiting_reason = "waiting_until_resume_at"
        transition_workflow(workflow, "waiting")
        append_workflow_event(session, workflow, "waiting", step=step, metadata={"resume_at": step.resume_at.isoformat()})

    def _reconcile_wait(self, session: Session, workflow: Workflow, step: WorkflowStep) -> bool:
        if step.status != "waiting" or step.resume_at is None:
            self._fail(session, workflow, step, "WORKFLOW_WAIT_INVALID", "Workflow wait state is invalid")
            return False
        if not is_due(step.resume_at, now=utc_now()):
            if workflow.status == "running":
                transition_workflow(workflow, "waiting")
            return False
        transition_step(step, "succeeded")
        step.waiting_reason = None
        if workflow.status == "waiting":
            transition_workflow(workflow, "running")
        append_workflow_event(session, workflow, "step_succeeded", step=step)
        return True

    def _reconcile_cancellation(self, session: Session, workflow: Workflow) -> None:
        steps = list(session.scalars(select(WorkflowStep).where(WorkflowStep.workflow_id == workflow.id)))
        waiting = False
        for step in steps:
            if step.status in {"pending", "ready", "waiting"}:
                transition_step(step, "cancelled")
            elif step.status in {"running", "cancelling"} and step.job_id:
                job = session.get(Job, step.job_id)
                if job and job.status in {"pending", "retrying", "running", "cancelling"}:
                    if job.status != "cancelling":
                        cancel_job(session, job, commit=False)
                    if job.status == "cancelled":
                        if step.status == "running":
                            transition_step(step, "cancelling")
                        transition_step(step, "cancelled")
                    else:
                        if step.status == "running":
                            transition_step(step, "cancelling")
                        waiting = True
                elif job and job.status == "succeeded" and step.status == "running":
                    transition_step(step, "succeeded")
                    step.result_json = self._safe_result(job.result, workflow=workflow, job=job)
                    append_workflow_event(session, workflow, "step_succeeded", step=step, job_id=job.id)
                else:
                    if step.status == "running":
                        transition_step(step, "cancelling")
                    transition_step(step, "cancelled")
        if not waiting:
            workflow.current_step_id = None
            transition_workflow(workflow, "cancelled")
            append_workflow_event(session, workflow, "workflow_cancelled")

    @staticmethod
    def _safe_result(result: object | None, *, workflow: Workflow, job: Job) -> dict:
        if not isinstance(result, dict):
            return {"job_id": job.id, "outcome": "completed"}
        projected: dict[str, object] = {
            "job_id": job.id,
            "runtime_id_snapshot": workflow.runtime_id_snapshot,
            "content_asset_version_id": workflow.content_asset_version_id,
        }
        mapping = {
            "content_delivery_id": "delivery_id", "delivery_id": "delivery_id",
            "status": "delivery_status", "remote_filename": "remote_filename",
            "media_uri": "media_uri", "sha256": "sha256",
        }
        for source, target in mapping.items():
            if source in result:
                value = result[source]
                if isinstance(value, (str, int, float, bool, type(None))):
                    projected[target] = value
        return projected if len(json.dumps(projected, separators=(",", ":"))) <= 16384 else {"job_id": job.id, "outcome": "completed"}

    @staticmethod
    def _validate_runtime_content_bindings(session: Session, workflow: Workflow) -> tuple[str, str] | None:
        runtime = session.get(Runtime, workflow.runtime_id) if workflow.runtime_id else None
        if runtime is None or runtime.id != workflow.runtime_id_snapshot or runtime.runtime_type != "redroid":
            return "WORKFLOW_RUNTIME_UNAVAILABLE", "Pinned Runtime is no longer available"
        asset = session.get(ContentAsset, workflow.content_asset_id) if workflow.content_asset_id else None
        if asset is None or asset.status == "deleted":
            return "CONTENT_DELETED", "Pinned content is no longer available"
        version = session.get(ContentAssetVersion, workflow.content_asset_version_id) if workflow.content_asset_version_id else None
        if version is None or version.content_asset_id != asset.id or version.processing_status != "ready":
            return "CONTENT_VERSION_NOT_READY", "Pinned content version is not ready"
        if version.blob is None or version.blob.status != "active":
            return "CONTENT_BLOB_INVALID", "Pinned content blob is unavailable"
        return None

    @staticmethod
    def _fail(session: Session, workflow: Workflow, step: WorkflowStep, code: str, message: str) -> None:
        if step.status == "ready":
            transition_step(step, "running")
        transition_step(step, "failed")
        step.error_code = code
        step.error_message = message[:500]
        workflow.error_code = code
        workflow.error_message = message[:500]
        transition_workflow(workflow, "failed")
        append_workflow_event(session, workflow, "step_failed", step=step, job_id=step.job_id, metadata={"error_code": code})
        append_workflow_event(session, workflow, "workflow_failed", metadata={"error_code": code})

    @staticmethod
    def _fail_workflow_without_step(session: Session, workflow: Workflow, code: str, message: str) -> None:
        workflow.error_code = code
        workflow.error_message = message
        transition_workflow(workflow, "failed")
        append_workflow_event(session, workflow, "workflow_failed", metadata={"error_code": code})
