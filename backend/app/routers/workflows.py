"""Public control plane for server-owned Workflow templates."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path as ApiPath, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import load_application_config
from app.models import Workflow, WorkflowEvent, WorkflowStep
from app.schemas.workflow import (
    ApprovalDecision, WorkflowCreate, WorkflowEventList, WorkflowEventRead,
    WorkflowList, WorkflowRead, WorkflowStepRead, WorkflowTemplateRead,
)
from app.services.workflow_lock import WorkflowOperationGuard
from app.services.workflow_service import WorkflowError, WorkflowService
from app.services.workflow_templates import list_workflow_templates


template_router = APIRouter(prefix="/workflow-templates", tags=["workflows"])
router = APIRouter(prefix="/workflows", tags=["workflows"])
DatabaseSession = Annotated[Session, Depends(get_db)]
WorkflowId = Annotated[int, ApiPath(gt=0)]


def _service() -> WorkflowService:
    return WorkflowService(WorkflowOperationGuard(load_application_config().workflow_lock_directory))


def _raise(error: WorkflowError) -> None:
    raise HTTPException(error.status_code, detail={"code": error.code, "message": error.safe_message}) from error


def _read(session: Session, workflow: Workflow) -> WorkflowRead:
    steps = list(session.scalars(
        select(WorkflowStep).where(WorkflowStep.workflow_id == workflow.id).order_by(WorkflowStep.step_index)
    ))
    return WorkflowRead(
        id=workflow.id, name=workflow.name, description=workflow.description,
        template_key=workflow.template_key, template_version=workflow.template_version,
        status=workflow.status, parameters=workflow.parameters_json,
        account_id=workflow.account_id, runtime_id=workflow.runtime_id,
        runtime_id_snapshot=workflow.runtime_id_snapshot,
        content_asset_id=workflow.content_asset_id,
        content_asset_version_id=workflow.content_asset_version_id,
        current_step_id=workflow.current_step_id,
        transition_version=workflow.transition_version,
        pause_requested_at=workflow.pause_requested_at,
        cancel_requested_at=workflow.cancel_requested_at,
        created_at=workflow.created_at, updated_at=workflow.updated_at,
        started_at=workflow.started_at, completed_at=workflow.completed_at,
        cancelled_at=workflow.cancelled_at, error_code=workflow.error_code,
        error_message=workflow.error_message,
        steps=[WorkflowStepRead.model_validate(step) for step in steps],
    )


@template_router.get("", response_model=list[WorkflowTemplateRead])
def templates() -> list[WorkflowTemplateRead]:
    return [WorkflowTemplateRead(
        key=item.key, version=item.version, label=item.label,
        description=item.description,
        required_bindings=["runtime_id", "content_asset_id"],
        parameters_schema=item.parameter_schema.model_json_schema(),
    ) for item in list_workflow_templates()]


@router.post("", response_model=WorkflowRead, status_code=status.HTTP_201_CREATED)
def create_workflow(body: WorkflowCreate, session: DatabaseSession, response: Response) -> WorkflowRead:
    try:
        workflow, created = _service().create(session, **body.model_dump())
    except WorkflowError as error:
        _raise(error)
    if not created:
        response.status_code = status.HTTP_200_OK
    return _read(session, workflow)


@router.get("", response_model=WorkflowList)
def list_workflows(
    session: DatabaseSession,
    workflow_status: Annotated[str | None, Query(alias="status")] = None,
    template: Annotated[str | None, Query(max_length=100)] = None,
    runtime_id: Annotated[int | None, Query(gt=0)] = None,
    account_id: Annotated[int | None, Query(gt=0)] = None,
    content_asset_id: Annotated[int | None, Query(gt=0)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WorkflowList:
    filters = []
    if workflow_status: filters.append(Workflow.status == workflow_status)
    if template: filters.append(Workflow.template_key == template)
    if runtime_id: filters.append(Workflow.runtime_id_snapshot == runtime_id)
    if account_id: filters.append(Workflow.account_id == account_id)
    if content_asset_id: filters.append(Workflow.content_asset_id == content_asset_id)
    total = session.scalar(select(func.count()).select_from(Workflow).where(*filters)) or 0
    items = list(session.scalars(
        select(Workflow).where(*filters)
        .order_by(Workflow.created_at.desc(), Workflow.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ))
    return WorkflowList(items=[_read(session, item) for item in items], total=total, page=page, page_size=page_size)


@router.get("/{workflow_id}", response_model=WorkflowRead)
def get_workflow(workflow_id: WorkflowId, session: DatabaseSession) -> WorkflowRead:
    workflow = session.get(Workflow, workflow_id)
    if workflow is None:
        _raise(WorkflowError("WORKFLOW_NOT_FOUND", "Workflow was not found", status_code=404))
    return _read(session, workflow)


def _command(session: Session, workflow_id: int, action: str) -> WorkflowRead:
    try:
        workflow = _service().command(session, workflow_id, action)
    except WorkflowError as error:
        _raise(error)
    return _read(session, workflow)


@router.post("/{workflow_id}/start", response_model=WorkflowRead)
def start(workflow_id: WorkflowId, session: DatabaseSession) -> WorkflowRead: return _command(session, workflow_id, "start")

@router.post("/{workflow_id}/pause", response_model=WorkflowRead)
def pause(workflow_id: WorkflowId, session: DatabaseSession) -> WorkflowRead: return _command(session, workflow_id, "pause")

@router.post("/{workflow_id}/resume", response_model=WorkflowRead)
def resume(workflow_id: WorkflowId, session: DatabaseSession) -> WorkflowRead: return _command(session, workflow_id, "resume")

@router.post("/{workflow_id}/cancel", response_model=WorkflowRead)
def cancel(workflow_id: WorkflowId, session: DatabaseSession) -> WorkflowRead: return _command(session, workflow_id, "cancel")

@router.post("/{workflow_id}/retry", response_model=WorkflowRead)
def retry(workflow_id: WorkflowId, session: DatabaseSession) -> WorkflowRead: return _command(session, workflow_id, "retry")


def _approval(session: Session, workflow_id: int, step_id: int, body: ApprovalDecision, approved: bool) -> WorkflowRead:
    try:
        workflow = _service().decide_approval(
            session, workflow_id, step_id, approved=approved,
            actor=body.actor, comment=body.comment,
        )
    except WorkflowError as error:
        _raise(error)
    return _read(session, workflow)


@router.post("/{workflow_id}/steps/{step_id}/approve", response_model=WorkflowRead)
def approve(workflow_id: WorkflowId, step_id: Annotated[int, ApiPath(gt=0)], body: ApprovalDecision, session: DatabaseSession) -> WorkflowRead:
    return _approval(session, workflow_id, step_id, body, True)

@router.post("/{workflow_id}/steps/{step_id}/reject", response_model=WorkflowRead)
def reject(workflow_id: WorkflowId, step_id: Annotated[int, ApiPath(gt=0)], body: ApprovalDecision, session: DatabaseSession) -> WorkflowRead:
    return _approval(session, workflow_id, step_id, body, False)


@router.get("/{workflow_id}/events", response_model=WorkflowEventList)
def events(
    workflow_id: WorkflowId, session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> WorkflowEventList:
    if session.get(Workflow, workflow_id) is None:
        _raise(WorkflowError("WORKFLOW_NOT_FOUND", "Workflow was not found", status_code=404))
    total = session.scalar(select(func.count()).select_from(WorkflowEvent).where(WorkflowEvent.workflow_id == workflow_id)) or 0
    rows = list(session.scalars(
        select(WorkflowEvent).where(WorkflowEvent.workflow_id == workflow_id)
        .order_by(WorkflowEvent.created_at, WorkflowEvent.id)
        .offset((page - 1) * page_size).limit(page_size)
    ))
    return WorkflowEventList(items=[WorkflowEventRead(
        id=row.id, workflow_id=row.workflow_id, workflow_step_id=row.workflow_step_id,
        job_id=row.job_id, event_type=row.event_type,
        metadata=row.metadata_json, created_at=row.created_at,
    ) for row in rows], total=total, page=page, page_size=page_size)
