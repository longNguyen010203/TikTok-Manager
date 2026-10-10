"""Narrow typed entry points for server-created TikTok Jobs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job
from app.schemas.job import JobRead
from app.schemas.tiktok_action import (
    TikTokDetectScreenRequest,
    TikTokOpenCreateRequest,
    TikTokOpenCaptionRequest,
    TikTokOpenMediaPickerRequest,
    TikTokOpenProfileRequest,
    TikTokChooseEmailSignupRequest,
    TikTokSetRegistrationEmailRequest,
    TikTokContinueRegistrationEmailRequest,
    TikTokSelectMediaRequest,
    TikTokSkipInterestsRequest,
    TikTokSetCaptionRequest,
    TikTokSetPostOptionsRequest,
    TikTokPreparePublishRequest,
)
from app.services.tiktok_errors import TikTokActionError
from app.services.tiktok_jobs import (
    create_detect_screen_job,
    create_open_create_job,
    create_open_caption_job,
    create_open_media_picker_job,
    create_open_profile_job,
    create_choose_email_signup_job,
    create_set_registration_email_job,
    create_continue_registration_email_job,
    create_select_media_job,
    create_skip_interests_job,
    create_set_caption_job,
    create_set_post_options_job,
    create_prepare_publish_job,
)

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


@router.post(
    "/{runtime_id}/tiktok/open-create",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def open_create(runtime_id: RuntimeId, payload: TikTokOpenCreateRequest, session: DatabaseSession) -> Job:
    """Create a server-owned, profile-pinned Create-navigation Job."""
    try:
        return create_open_create_job(
            session, runtime_id=runtime_id, managed_app_id=payload.managed_app_id
        )
    except TikTokActionError as error:
        session.rollback()
        code = 404 if error.code == "TIKTOK_UI_PROFILE_NOT_FOUND" else 409
        raise HTTPException(status_code=code, detail={
            "code": error.code, "message": error.safe_message,
            "retryable": error.retryable,
        }) from error


@router.post(
    "/{runtime_id}/tiktok/open-media-picker",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def open_media_picker(
    runtime_id: RuntimeId,
    payload: TikTokOpenMediaPickerRequest,
    session: DatabaseSession,
) -> Job:
    """Create a server-owned camera-to-media-picker navigation Job."""
    try:
        return create_open_media_picker_job(
            session, runtime_id=runtime_id, managed_app_id=payload.managed_app_id
        )
    except TikTokActionError as error:
        session.rollback()
        code = 404 if error.code == "TIKTOK_UI_PROFILE_NOT_FOUND" else 409
        raise HTTPException(status_code=code, detail={
            "code": error.code, "message": error.safe_message,
            "retryable": error.retryable,
        }) from error


@router.post(
    "/{runtime_id}/tiktok/select-media",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def select_media(
    runtime_id: RuntimeId,
    payload: TikTokSelectMediaRequest,
    session: DatabaseSession,
) -> Job:
    """Create a one-attempt, delivery-bound media-selection Job."""
    try:
        return create_select_media_job(
            session,
            runtime_id=runtime_id,
            managed_app_id=payload.managed_app_id,
            content_delivery_id=payload.content_delivery_id,
        )
    except TikTokActionError as error:
        session.rollback()
        code = 404 if error.code == "TIKTOK_UI_PROFILE_NOT_FOUND" else 409
        raise HTTPException(status_code=code, detail={
            "code": error.code,
            "message": error.safe_message,
            "retryable": error.retryable,
        }) from error


@router.post(
    "/{runtime_id}/tiktok/open-caption",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def open_caption(
    runtime_id: RuntimeId,
    payload: TikTokOpenCaptionRequest,
    session: DatabaseSession,
) -> Job:
    """Create a one-attempt, profile-owned editor Next Job."""
    try:
        return create_open_caption_job(
            session, runtime_id=runtime_id,
            managed_app_id=payload.managed_app_id,
        )
    except TikTokActionError as error:
        session.rollback()
        code = 404 if error.code == "TIKTOK_UI_PROFILE_NOT_FOUND" else 409
        raise HTTPException(status_code=code, detail={
            "code": error.code,
            "message": error.safe_message,
            "retryable": error.retryable,
        }) from error


@router.post(
    "/{runtime_id}/tiktok/skip-interests",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def skip_interests(
    runtime_id: RuntimeId,
    payload: TikTokSkipInterestsRequest,
    session: DatabaseSession,
) -> Job:
    """Create a one-attempt, profile-owned onboarding Skip Job."""
    try:
        return create_skip_interests_job(
            session, runtime_id=runtime_id,
            managed_app_id=payload.managed_app_id,
        )
    except TikTokActionError as error:
        session.rollback()
        code = 404 if error.code == "TIKTOK_UI_PROFILE_NOT_FOUND" else 409
        raise HTTPException(status_code=code, detail={
            "code": error.code,
            "message": error.safe_message,
            "retryable": error.retryable,
        }) from error


@router.post(
    "/{runtime_id}/tiktok/open-profile",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def open_profile(
    runtime_id: RuntimeId,
    payload: TikTokOpenProfileRequest,
    session: DatabaseSession,
) -> Job:
    """Create a one-attempt Job that activates the state-dependent Profile tab."""
    try:
        return create_open_profile_job(
            session, runtime_id=runtime_id,
            managed_app_id=payload.managed_app_id,
        )
    except TikTokActionError as error:
        session.rollback()
        code = 404 if error.code == "TIKTOK_UI_PROFILE_NOT_FOUND" else 409
        raise HTTPException(status_code=code, detail={
            "code": error.code,
            "message": error.safe_message,
            "retryable": error.retryable,
        }) from error


@router.post(
    "/{runtime_id}/tiktok/choose-email-signup",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def choose_email_signup(
    runtime_id: RuntimeId,
    payload: TikTokChooseEmailSignupRequest,
    session: DatabaseSession,
) -> Job:
    """Create a one-attempt Job for the calibrated email signup method."""
    try:
        return create_choose_email_signup_job(
            session, runtime_id=runtime_id,
            managed_app_id=payload.managed_app_id,
        )
    except TikTokActionError as error:
        session.rollback()
        code = 404 if error.code == "TIKTOK_UI_PROFILE_NOT_FOUND" else 409
        raise HTTPException(status_code=code, detail={
            "code": error.code,
            "message": error.safe_message,
            "retryable": error.retryable,
        }) from error


@router.post(
    "/{runtime_id}/tiktok/set-registration-email",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def set_registration_email(
    runtime_id: RuntimeId,
    payload: TikTokSetRegistrationEmailRequest,
    session: DatabaseSession,
) -> Job:
    """Create a one-attempt Account-bound registration email Job."""
    try:
        return create_set_registration_email_job(
            session, runtime_id=runtime_id,
            managed_app_id=payload.managed_app_id,
            account_id=payload.account_id,
        )
    except TikTokActionError as error:
        session.rollback()
        code = 404 if error.code in {
            "TIKTOK_UI_PROFILE_NOT_FOUND", "TIKTOK_ACCOUNT_NOT_FOUND",
        } else 409
        raise HTTPException(status_code=code, detail={
            "code": error.code,
            "message": error.safe_message,
            "retryable": error.retryable,
        }) from error


@router.post(
    "/{runtime_id}/tiktok/continue-registration-email",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def continue_registration_email(
    runtime_id: RuntimeId,
    payload: TikTokContinueRegistrationEmailRequest,
    session: DatabaseSession,
) -> Job:
    """Create a one-attempt Account-bound registration Continue Job."""
    try:
        return create_continue_registration_email_job(
            session, runtime_id=runtime_id,
            managed_app_id=payload.managed_app_id,
            account_id=payload.account_id,
        )
    except TikTokActionError as error:
        session.rollback()
        code = 404 if error.code in {
            "TIKTOK_UI_PROFILE_NOT_FOUND", "TIKTOK_ACCOUNT_NOT_FOUND",
        } else 409
        raise HTTPException(status_code=code, detail={
            "code": error.code,
            "message": error.safe_message,
            "retryable": error.retryable,
        }) from error


@router.post(
    "/{runtime_id}/tiktok/set-caption",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def set_caption(
    runtime_id: RuntimeId,
    payload: TikTokSetCaptionRequest,
    session: DatabaseSession,
) -> Job:
    """Create a one-attempt caption replacement Job."""
    try:
        return create_set_caption_job(
            session, runtime_id=runtime_id,
            managed_app_id=payload.managed_app_id, caption=payload.caption,
        )
    except TikTokActionError as error:
        session.rollback()
        code = 404 if error.code == "TIKTOK_UI_PROFILE_NOT_FOUND" else 409
        raise HTTPException(status_code=code, detail={
            "code": error.code,
            "message": error.safe_message,
            "retryable": error.retryable,
        }) from error


@router.post(
    "/{runtime_id}/tiktok/set-post-options",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def set_post_options(
    runtime_id: RuntimeId,
    payload: TikTokSetPostOptionsRequest,
    session: DatabaseSession,
) -> Job:
    """Create a one-attempt, profile-owned post-options Job."""
    try:
        return create_set_post_options_job(
            session, runtime_id=runtime_id,
            managed_app_id=payload.managed_app_id,
            privacy=payload.privacy,
        )
    except TikTokActionError as error:
        session.rollback()
        code = 404 if error.code == "TIKTOK_UI_PROFILE_NOT_FOUND" else 409
        raise HTTPException(status_code=code, detail={
            "code": error.code,
            "message": error.safe_message,
            "retryable": error.retryable,
        }) from error


@router.post(
    "/{runtime_id}/tiktok/prepare-publish",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def prepare_publish(
    runtime_id: RuntimeId,
    payload: TikTokPreparePublishRequest,
    session: DatabaseSession,
) -> Job:
    """Create a read-only final pre-publish verification Job."""
    try:
        return create_prepare_publish_job(
            session,
            runtime_id=runtime_id,
            managed_app_id=payload.managed_app_id,
            content_delivery_id=payload.content_delivery_id,
            expected_caption=payload.expected_caption,
            expected_privacy=payload.expected_privacy,
        )
    except TikTokActionError as error:
        session.rollback()
        code = 404 if error.code == "TIKTOK_UI_PROFILE_NOT_FOUND" else 409
        raise HTTPException(status_code=code, detail={
            "code": error.code,
            "message": error.safe_message,
            "retryable": error.retryable,
        }) from error
