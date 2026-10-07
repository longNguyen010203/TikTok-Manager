"""Internal, typed TikTok Job definitions and server-side creation."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentDelivery, Job, ManagedApp, Runtime, RuntimeAppInstallation
from app.services.tiktok_errors import tiktok_error
from app.services.tiktok_action_service import normalize_caption
from app.services.tiktok_ui_profiles import TikTokUiProfileRegistry


class TikTokDetectScreenPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runtime_id: int = Field(gt=0)
    managed_app_id: int = Field(gt=0)
    ui_profile_id: int = Field(gt=0)


class TikTokSelectMediaPayload(TikTokDetectScreenPayload):
    content_delivery_id: int = Field(gt=0)


class TikTokSetCaptionPayload(TikTokDetectScreenPayload):
    caption: str = Field(max_length=150)


class TikTokSetPostOptionsPayload(TikTokDetectScreenPayload):
    privacy: Literal["everyone", "only_you"] | None


class TikTokPreparePublishPayload(TikTokDetectScreenPayload):
    content_delivery_id: int = Field(gt=0)
    expected_caption: str = Field(max_length=150)
    expected_privacy: Literal["everyone", "only_you"]


@dataclass(frozen=True)
class TikTokJobDefinition:
    job_type: str
    retryable_codes: frozenset[str]
    idempotency: Literal["safe", "uncertain"] = "safe"

    @property
    def allows_post_dispatch_retry(self) -> bool:
        return self.idempotency == "safe"


_DEFINITIONS = {
    job_type: TikTokJobDefinition(
        job_type,
        frozenset({
            "RUNTIME_BUSY", "DEVICE_NOT_READY", "ADB_UNAVAILABLE",
            "TIKTOK_SCREEN_TIMEOUT", "TIKTOK_ACTION_CANCELLED",
        }),
    )
    for job_type in (
        "tiktok.detect_screen", "tiktok.open_create",
        "tiktok.open_media_picker",
    )
}
_DEFINITIONS["tiktok.select_media"] = TikTokJobDefinition(
    "tiktok.select_media",
    frozenset(),
    idempotency="uncertain",
)
_DEFINITIONS["tiktok.open_caption"] = TikTokJobDefinition(
    "tiktok.open_caption", frozenset(), idempotency="uncertain",
)
_DEFINITIONS["tiktok.set_caption"] = TikTokJobDefinition(
    "tiktok.set_caption", frozenset(), idempotency="uncertain",
)
_DEFINITIONS["tiktok.set_post_options"] = TikTokJobDefinition(
    "tiktok.set_post_options", frozenset(), idempotency="uncertain",
)
_DEFINITIONS["tiktok.prepare_publish"] = TikTokJobDefinition(
    "tiktok.prepare_publish",
    frozenset({
        "RUNTIME_BUSY", "DEVICE_NOT_READY", "ADB_UNAVAILABLE",
        "TIKTOK_UI_DUMP_INVALID", "TIKTOK_ACTION_CANCELLED",
    }),
    idempotency="safe",
)


class TikTokJobValidationError(ValueError):
    pass


def is_tiktok_job_type(job_type: object) -> bool:
    return isinstance(job_type, str) and job_type in _DEFINITIONS


def get_tiktok_job_definition(job_type: str) -> TikTokJobDefinition | None:
    return _DEFINITIONS.get(job_type)


def validate_tiktok_job_payload(job_type: str, payload: Any) -> dict[str, Any]:
    try:
        schema = (
            TikTokSelectMediaPayload
            if job_type == "tiktok.select_media"
            else TikTokSetCaptionPayload
            if job_type == "tiktok.set_caption"
            else TikTokSetPostOptionsPayload
            if job_type == "tiktok.set_post_options"
            else TikTokPreparePublishPayload
            if job_type == "tiktok.prepare_publish"
            else TikTokDetectScreenPayload
        )
        return schema.model_validate(payload).model_dump()
    except ValidationError as error:
        raise TikTokJobValidationError("Invalid TikTok Job payload") from error


def _create_tiktok_job(
    session: Session, *, job_type: str, runtime_id: int, managed_app_id: int,
    extra_payload: dict[str, Any] | None = None, max_attempts: int = 3,
) -> Job:
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
    payload = {
        "runtime_id": runtime_id,
        "managed_app_id": managed_app_id,
        "ui_profile_id": profile.id,
    }
    payload.update(extra_payload or {})
    job = Job(
        job_type=job_type, status="pending", runtime_id=runtime_id,
        payload=payload,
        max_attempts=max_attempts,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def create_detect_screen_job(session: Session, *, runtime_id: int, managed_app_id: int) -> Job:
    return _create_tiktok_job(
        session, job_type="tiktok.detect_screen", runtime_id=runtime_id,
        managed_app_id=managed_app_id,
    )


def create_open_create_job(session: Session, *, runtime_id: int, managed_app_id: int) -> Job:
    return _create_tiktok_job(
        session, job_type="tiktok.open_create", runtime_id=runtime_id,
        managed_app_id=managed_app_id,
    )


def create_open_media_picker_job(
    session: Session, *, runtime_id: int, managed_app_id: int
) -> Job:
    return _create_tiktok_job(
        session, job_type="tiktok.open_media_picker", runtime_id=runtime_id,
        managed_app_id=managed_app_id,
    )


def create_select_media_job(
    session: Session, *, runtime_id: int, managed_app_id: int,
    content_delivery_id: int,
) -> Job:
    delivery = session.get(ContentDelivery, content_delivery_id)
    if (
        delivery is None
        or delivery.status != "succeeded"
        or delivery.runtime_id != runtime_id
        or delivery.runtime_id_snapshot != runtime_id
        or not delivery.import_media
        or not delivery.media_uri
    ):
        raise tiktok_error("TIKTOK_MEDIA_DELIVERY_INVALID")
    job = _create_tiktok_job(
        session, job_type="tiktok.select_media", runtime_id=runtime_id,
        managed_app_id=managed_app_id,
        extra_payload={"content_delivery_id": content_delivery_id},
        max_attempts=1,
    )
    # Media selection is not safely replayable after dispatch. The one-attempt
    # Job and its complete server-owned payload are committed atomically.
    return job


def create_open_caption_job(
    session: Session, *, runtime_id: int, managed_app_id: int,
) -> Job:
    return _create_tiktok_job(
        session, job_type="tiktok.open_caption", runtime_id=runtime_id,
        managed_app_id=managed_app_id, max_attempts=1,
    )


def create_set_caption_job(
    session: Session, *, runtime_id: int, managed_app_id: int, caption: str,
) -> Job:
    normalized = normalize_caption(caption)
    return _create_tiktok_job(
        session, job_type="tiktok.set_caption", runtime_id=runtime_id,
        managed_app_id=managed_app_id,
        extra_payload={"caption": normalized}, max_attempts=1,
    )


def create_set_post_options_job(
    session: Session, *, runtime_id: int, managed_app_id: int,
    privacy: str | None,
) -> Job:
    if privacy not in {None, "everyone", "only_you"}:
        raise tiktok_error("TIKTOK_OPTION_UNSUPPORTED")
    return _create_tiktok_job(
        session, job_type="tiktok.set_post_options", runtime_id=runtime_id,
        managed_app_id=managed_app_id,
        extra_payload={"privacy": privacy}, max_attempts=1,
    )


def create_prepare_publish_job(
    session: Session, *, runtime_id: int, managed_app_id: int,
    content_delivery_id: int, expected_caption: str, expected_privacy: str,
) -> Job:
    delivery = session.get(ContentDelivery, content_delivery_id)
    if (
        delivery is None
        or delivery.status != "succeeded"
        or delivery.runtime_id != runtime_id
        or delivery.runtime_id_snapshot != runtime_id
        or not delivery.import_media
        or not delivery.media_uri
    ):
        raise tiktok_error("TIKTOK_MEDIA_DELIVERY_INVALID")
    normalized = normalize_caption(expected_caption)
    if expected_privacy not in {"everyone", "only_you"}:
        raise tiktok_error("TIKTOK_OPTION_UNSUPPORTED")
    return _create_tiktok_job(
        session, job_type="tiktok.prepare_publish", runtime_id=runtime_id,
        managed_app_id=managed_app_id,
        extra_payload={
            "content_delivery_id": content_delivery_id,
            "expected_caption": normalized,
            "expected_privacy": expected_privacy,
        },
        max_attempts=3,
    )
