"""Workflow creation, bindings, operator commands, and safe history."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Account, ContentAsset, ContentAssetVersion, Job, Runtime, Workflow,
    WorkflowEvent, WorkflowStep,
)
from app.models.timestamps import utc_now
from app.services.job_lifecycle import JobRetryLimitError, cancel_job, retry_failed_job
from app.services.workflow_lock import WorkflowOperationGuard, WorkflowOperationLockBusy
from app.services.workflow_state import transition_step, transition_workflow
from app.services.workflow_templates import WorkflowTemplateError, get_workflow_template


class WorkflowError(RuntimeError):
    def __init__(self, code: str, safe_message: str, *, status_code: int = 409) -> None:
        self.code = code
        self.safe_message = safe_message
        self.status_code = status_code
        super().__init__(safe_message)


def append_workflow_event(
    session: Session,
    workflow: Workflow,
    event_type: str,
    *,
    step: WorkflowStep | None = None,
    job_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> WorkflowEvent:
    # Callers supply only small identifiers/statuses. Serialize once to enforce
    # the DB-bound without leaking payloads, paths, commands, or tokens.
    safe = metadata or {}
    if len(json.dumps(safe, sort_keys=True, separators=(",", ":"))) > 8192:
        raise WorkflowError("WORKFLOW_EVENT_INVALID", "Workflow event metadata is too large")
    event = WorkflowEvent(
        workflow_id=workflow.id,
        workflow_step_id=step.id if step else None,
        job_id=job_id,
        event_type=event_type,
        metadata_json=safe,
    )
    session.add(event)
    return event


class WorkflowService:
    def __init__(self, guard: WorkflowOperationGuard) -> None:
        self.guard = guard

    def create(
        self,
        session: Session,
        *,
        template_key: str,
        template_version: int | None,
        name: str,
        description: str | None,
        runtime_id: int,
        content_asset_id: int,
        content_asset_version_id: int | None,
        account_id: int | None,
        parameters: dict[str, Any],
        idempotency_key: str | None,
    ) -> tuple[Workflow, bool]:
        try:
            template = get_workflow_template(template_key, template_version)
            validated = template.parameter_schema.model_validate(parameters).model_dump(mode="json")
        except WorkflowTemplateError as error:
            raise WorkflowError(error.code, error.safe_message, status_code=404) from error
        except ValidationError as error:
            raise WorkflowError("INVALID_WORKFLOW_PARAMETERS", "Workflow parameters are invalid", status_code=422) from error

        runtime = session.get(Runtime, runtime_id)
        if runtime is None or runtime.runtime_type != "redroid":
            raise WorkflowError("RUNTIME_NOT_FOUND", "Runtime was not found", status_code=404)
        if not runtime.adb_serial or not runtime.docker_container_name:
            raise WorkflowError("RUNTIME_INVALID", "Runtime automation configuration is incomplete", status_code=422)
        asset = session.get(ContentAsset, content_asset_id)
        if asset is None:
            raise WorkflowError("CONTENT_NOT_FOUND", "Content was not found", status_code=404)
        if asset.status == "deleted":
            raise WorkflowError("CONTENT_DELETED", "Content was deleted")
        pinned_id = content_asset_version_id or asset.current_version_id
        version = session.get(ContentAssetVersion, pinned_id) if pinned_id else None
        if (
            version is None
            or version.content_asset_id != asset.id
            or version.processing_status != "ready"
        ):
            raise WorkflowError("CONTENT_VERSION_NOT_READY", "Content version is not ready")
        if account_id is not None:
            account = session.get(Account, account_id)
            if account is None:
                raise WorkflowError("ACCOUNT_NOT_FOUND", "Account was not found", status_code=404)
            if account.runtime_id is not None and account.runtime_id != runtime.id:
                raise WorkflowError("ACCOUNT_RUNTIME_MISMATCH", "Account is assigned to a different Runtime")

        fingerprint_payload = {
            "template_key": template.key, "template_version": template.version,
            "name": name, "description": description, "runtime_id": runtime.id,
            "content_asset_id": asset.id, "content_asset_version_id": version.id,
            "account_id": account_id, "parameters": validated,
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()
        if idempotency_key is not None:
            existing = session.scalar(select(Workflow).where(Workflow.idempotency_key == idempotency_key))
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise WorkflowError("WORKFLOW_IDEMPOTENCY_CONFLICT", "Idempotency key was used for a different request")
                return existing, False

        workflow = Workflow(
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            name=name,
            description=description,
            template_key=template.key,
            template_version=template.version,
            status="draft",
            parameters_json=validated,
            account_id=account_id,
            runtime_id=runtime.id,
            runtime_id_snapshot=runtime.id,
            content_asset_id=asset.id,
            content_asset_version_id=version.id,
        )
        session.add(workflow)
        try:
            # The idempotency-key uniqueness race is normally detected here,
            # before commit. Recover the already-created Workflow instead of
            # leaking an IntegrityError/500 to concurrent callers.
            session.flush()
        except IntegrityError as error:
            session.rollback()
            if idempotency_key is not None:
                existing = session.scalar(
                    select(Workflow).where(Workflow.idempotency_key == idempotency_key)
                )
                if existing is not None:
                    if existing.request_fingerprint == fingerprint:
                        return existing, False
                    raise WorkflowError(
                        "WORKFLOW_IDEMPOTENCY_CONFLICT",
                        "Idempotency key was used for a different request",
                    ) from error
            raise WorkflowError(
                "WORKFLOW_CREATION_CONFLICT", "Workflow could not be created"
            ) from error
        previous: WorkflowStep | None = None
        for index, spec in enumerate(template.steps):
            if spec.step_type == "content.deliver":
                step_input = {"import_media": bool(validated.get("import_media", True))}
            elif spec.step_type == "workflow.wait":
                step_input = {"duration_seconds": validated["wait_duration_seconds"]}
            else:
                step_input = {}
            step = WorkflowStep(
                workflow_id=workflow.id,
                step_index=index,
                step_key=spec.key,
                step_type=spec.step_type,
                status="pending",
                depends_on_step_id=previous.id if previous else None,
                attempt=1,
                max_attempts=spec.max_attempts,
                input_json=step_input,
            )
            session.add(step)
            session.flush()
            previous = step
        append_workflow_event(session, workflow, "workflow_created", metadata={
            "template_key": template.key, "template_version": template.version,
            "runtime_id": runtime.id, "content_asset_version_id": version.id,
        })
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            if idempotency_key is not None:
                existing = session.scalar(
                    select(Workflow).where(Workflow.idempotency_key == idempotency_key)
                )
                if existing is not None:
                    if existing.request_fingerprint == fingerprint:
                        return existing, False
                    raise WorkflowError(
                        "WORKFLOW_IDEMPOTENCY_CONFLICT",
                        "Idempotency key was used for a different request",
                    ) from error
            raise WorkflowError(
                "WORKFLOW_CREATION_CONFLICT", "Workflow could not be created"
            ) from error
        session.refresh(workflow)
        return workflow, True

    def command(self, session: Session, workflow_id: int, action: str) -> Workflow:
        try:
            with self.guard.acquire_workflow(workflow_id, blocking=False):
                workflow = self._get(session, workflow_id)
                if action == "start":
                    if workflow.status != "draft":
                        raise WorkflowError("INVALID_WORKFLOW_TRANSITION", "Only a draft Workflow can be started")
                    transition_workflow(workflow, "pending")
                elif action == "pause":
                    self._pause(session, workflow)
                elif action == "resume":
                    if workflow.status != "paused":
                        raise WorkflowError("INVALID_WORKFLOW_TRANSITION", "Only a paused Workflow can be resumed")
                    workflow.pause_requested_at = None
                    transition_workflow(workflow, "pending")
                    append_workflow_event(session, workflow, "workflow_resumed")
                elif action == "cancel":
                    self._cancel(session, workflow)
                elif action == "retry":
                    self._retry(session, workflow)
                else:
                    raise WorkflowError("INVALID_WORKFLOW_COMMAND", "Workflow command is invalid", status_code=422)
                session.commit()
                session.refresh(workflow)
                return workflow
        except WorkflowOperationLockBusy as error:
            raise WorkflowError("WORKFLOW_BUSY", "Workflow is busy") from error

    def decide_approval(
        self, session: Session, workflow_id: int, step_id: int, *,
        approved: bool, actor: str, comment: str | None,
    ) -> Workflow:
        try:
            with self.guard.acquire_workflow(workflow_id, blocking=False):
                workflow = self._get(session, workflow_id)
                step = session.get(WorkflowStep, step_id)
                if (
                    step is None or step.workflow_id != workflow.id
                    or workflow.current_step_id != step.id
                    or workflow.status != "waiting" or step.status != "waiting"
                    or step.step_type != "workflow.approval"
                ):
                    raise WorkflowError("WORKFLOW_APPROVAL_NOT_WAITING", "Workflow is not waiting on this approval")
                step.approval_decision = "approved" if approved else "rejected"
                step.approval_actor = actor
                step.approval_comment = comment
                step.approval_at = utc_now()
                if approved:
                    transition_step(step, "succeeded")
                    transition_workflow(workflow, "running")
                    append_workflow_event(session, workflow, "approved", step=step)
                    append_workflow_event(session, workflow, "step_succeeded", step=step)
                else:
                    transition_step(step, "failed")
                    step.error_code = "WORKFLOW_APPROVAL_REJECTED"
                    step.error_message = "Workflow approval was rejected"
                    transition_workflow(workflow, "failed")
                    workflow.error_code = step.error_code
                    workflow.error_message = step.error_message
                    append_workflow_event(session, workflow, "rejected", step=step)
                    append_workflow_event(session, workflow, "step_failed", step=step, metadata={"error_code": step.error_code})
                    append_workflow_event(session, workflow, "workflow_failed", metadata={"error_code": step.error_code})
                session.commit()
                session.refresh(workflow)
                return workflow
        except WorkflowOperationLockBusy as error:
            raise WorkflowError("WORKFLOW_BUSY", "Workflow is busy") from error

    @staticmethod
    def _get(session: Session, workflow_id: int) -> Workflow:
        workflow = session.get(Workflow, workflow_id)
        if workflow is None:
            raise WorkflowError("WORKFLOW_NOT_FOUND", "Workflow was not found", status_code=404)
        return workflow

    @staticmethod
    def _active_job(session: Session, workflow: Workflow) -> Job | None:
        if workflow.current_step_id is None:
            return None
        step = session.get(WorkflowStep, workflow.current_step_id)
        return session.get(Job, step.job_id) if step and step.job_id else None

    def _pause(self, session: Session, workflow: Workflow) -> None:
        if workflow.status not in {"pending", "running", "waiting"}:
            raise WorkflowError("INVALID_WORKFLOW_TRANSITION", "Workflow cannot be paused")
        job = self._active_job(session, workflow)
        if job and job.status not in {"succeeded", "failed", "cancelled"}:
            workflow.pause_requested_at = workflow.pause_requested_at or utc_now()
            workflow.transition_version += 1
            return
        transition_workflow(workflow, "paused")
        append_workflow_event(session, workflow, "workflow_paused")

    def _cancel(self, session: Session, workflow: Workflow) -> None:
        if workflow.status in {"succeeded", "failed", "cancelled"}:
            raise WorkflowError("INVALID_WORKFLOW_TRANSITION", "Terminal Workflow cannot be cancelled")
        if workflow.status == "draft":
            transition_workflow(workflow, "cancelled")
            for step in session.scalars(select(WorkflowStep).where(WorkflowStep.workflow_id == workflow.id)):
                transition_step(step, "cancelled")
            append_workflow_event(session, workflow, "workflow_cancelled")
            return
        if workflow.status == "cancelling":
            return
        transition_workflow(workflow, "cancelling")
        workflow.cancel_requested_at = workflow.cancel_requested_at or utc_now()
        append_workflow_event(session, workflow, "cancellation_requested")
        job = self._active_job(session, workflow)
        if job and job.status in {"pending", "retrying", "running", "cancelling"}:
            cancel_job(session, job, commit=False)

    def _retry(self, session: Session, workflow: Workflow) -> None:
        if workflow.status != "failed" or workflow.current_step_id is None:
            raise WorkflowError("INVALID_WORKFLOW_TRANSITION", "Only a failed Workflow step can be retried")
        step = session.get(WorkflowStep, workflow.current_step_id)
        if step is None or step.status != "failed" or step.job_id is None:
            raise WorkflowError("WORKFLOW_RETRY_UNAVAILABLE", "Workflow step cannot be retried")
        job = session.get(Job, step.job_id)
        if job is None or job.status != "failed":
            raise WorkflowError("WORKFLOW_RETRY_UNAVAILABLE", "Workflow Job cannot be retried")
        try:
            retry_failed_job(session, job, commit=False)
        except JobRetryLimitError as error:
            raise WorkflowError("WORKFLOW_RETRY_EXHAUSTED", "Workflow Job has no retries remaining") from error
        transition_step(step, "ready")
        transition_workflow(workflow, "pending")
        # A retried Workflow/step is no longer terminal. Clear the timestamps
        # from the failed attempt so API consumers do not observe a pending or
        # running execution that still appears completed.
        workflow.completed_at = None
        step.completed_at = None
        workflow.error_code = workflow.error_message = None
        step.error_code = step.error_message = None
        append_workflow_event(session, workflow, "retry_requested", step=step, job_id=job.id)
