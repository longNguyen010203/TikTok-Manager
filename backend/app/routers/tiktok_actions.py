"""Narrow typed entry points for server-created TikTok Jobs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job
from app.schemas.job import JobRead
from app.schemas.tiktok_action import TikTokDetectScreenRequest
from app.services.tiktok_errors import TikTokActionError
from app.services.tiktok_jobs import create_detect_screen_job

router = APIRouter(prefix="/runtimes", tags=["tiktok-actions"])
DatabaseSession = Annotated[Session, Depends(get_db)]
RuntimeId = Annotated[int, Path(gt=0)]


@router.post(
    "/{runtime_id}/tiktok/detect-screen",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def detect_screen(runtime_id: RuntimeId, payload: TikTokDetectScreenRequest, session: DatabaseSession) -> Job:
    """Create the only server-owned observational TikTok Job in Phase 2."""
    try:
        return create_detect_screen_job(
            session, runtime_id=runtime_id, managed_app_id=payload.managed_app_id
        )
    except TikTokActionError as error:
        session.rollback()
        code = 404 if error.code == "TIKTOK_UI_PROFILE_NOT_FOUND" else 409
        raise HTTPException(status_code=code, detail={
            "code": error.code, "message": error.safe_message,
            "retryable": error.retryable,
        }) from error
