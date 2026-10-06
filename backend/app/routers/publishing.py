"""Read-only publishing preparation history."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PublishingSession
from app.schemas.publishing import PublishingSessionList, PublishingSessionRead

router = APIRouter(prefix="/publishing-sessions", tags=["publishing"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=PublishingSessionList)
def list_sessions(
    session: DatabaseSession,
    session_status: Annotated[str | None, Query(alias="status")] = None,
    runtime_id: Annotated[int | None, Query(gt=0)] = None,
    account_id: Annotated[int | None, Query(gt=0)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PublishingSessionList:
    filters = []
    if session_status: filters.append(PublishingSession.status == session_status)
    if runtime_id: filters.append(PublishingSession.runtime_id_snapshot == runtime_id)
    if account_id: filters.append(PublishingSession.account_id_snapshot == account_id)
    total = session.scalar(select(func.count()).select_from(PublishingSession).where(*filters)) or 0
    rows = list(session.scalars(
        select(PublishingSession).where(*filters)
        .order_by(PublishingSession.created_at.desc(), PublishingSession.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ))
    return PublishingSessionList(items=[PublishingSessionRead.model_validate(row) for row in rows], total=total, page=page, page_size=page_size)


@router.get("/{session_id}", response_model=PublishingSessionRead)
def get_session(session_id: Annotated[int, Path(gt=0)], session: DatabaseSession) -> PublishingSessionRead:
    row = session.get(PublishingSession, session_id)
    if row is None:
        raise HTTPException(404, detail={"code": "PUBLISHING_SESSION_NOT_FOUND", "message": "Publishing session was not found"})
    return PublishingSessionRead.model_validate(row)
