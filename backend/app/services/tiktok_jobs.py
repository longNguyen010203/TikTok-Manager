"""Internal, typed TikTok Job definitions and server-side creation."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, ManagedApp, Runtime, RuntimeAppInstallation
from app.services.tiktok_errors import tiktok_error
from app.services.tiktok_ui_profiles import TikTokUiProfileRegistry


class TikTokDetectScreenPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runtime_id: int = Field(gt=0)
    managed_app_id: int = Field(gt=0)
    ui_profile_id: int = Field(gt=0)


@dataclass(frozen=True)
class TikTokJobDefinition:
    job_type: str
    retryable_codes: frozenset[str]
    idempotency: Literal["safe"] = "safe"

    @property
    def allows_post_dispatch_retry(self) -> bool:
        return True


_DEFINITION = TikTokJobDefinition(
    "tiktok.detect_screen",
    frozenset({"RUNTIME_BUSY", "DEVICE_NOT_READY", "ADB_UNAVAILABLE", "TIKTOK_SCREEN_TIMEOUT", "TIKTOK_ACTION_CANCELLED"}),
)


class TikTokJobValidationError(ValueError):
    pass


def is_tiktok_job_type(job_type: object) -> bool:
    return job_type == _DEFINITION.job_type


def get_tiktok_job_definition(job_type: str) -> TikTokJobDefinition | None:
    return _DEFINITION if is_tiktok_job_type(job_type) else None


def validate_tiktok_job_payload(payload: Any) -> dict[str, int]:
    try:
        return TikTokDetectScreenPayload.model_validate(payload).model_dump()
    except ValidationError as error:
        raise TikTokJobValidationError("Invalid TikTok Job payload") from error


def create_detect_screen_job(session: Session, *, runtime_id: int, managed_app_id: int) -> Job:
    runtime = session.get(Runtime, runtime_id)
    app = session.get(ManagedApp, managed_app_id)
    installation = session.scalar(select(RuntimeAppInstallation).where(
        RuntimeAppInstallation.runtime_id == runtime_id,
        RuntimeAppInstallation.managed_app_id == managed_app_id,
    ))
    if runtime is None or app is None or installation is None or installation.status != "installed":
        raise tiktok_error("TIKTOK_UI_PROFILE_NOT_FOUND")
    if installation.observed_package_name != app.android_package_name:
        raise tiktok_error("TIKTOK_UI_PROFILE_MISMATCH")
    profile, _ = TikTokUiProfileRegistry().select(
        session, package_name=app.android_package_name,
        version_code=installation.observed_version_code,
    )
    job = Job(
        job_type="tiktok.detect_screen", status="pending", runtime_id=runtime_id,
        payload={"runtime_id": runtime_id, "managed_app_id": managed_app_id, "ui_profile_id": profile.id},
        max_attempts=3,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job
