"""Internal typed publishing-preparation Job definitions."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class PublishingJobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publishing_session_id: int = Field(gt=0)


@dataclass(frozen=True)
class PublishingJobDefinition:
    job_type: str
    retryable_codes: frozenset[str]
    idempotency: Literal["safe"] = "safe"

    @property
    def allows_post_dispatch_retry(self) -> bool:
        return True


_RETRYABLE = frozenset({"RUNTIME_BUSY", "DEVICE_NOT_READY", "ADB_UNAVAILABLE", "APP_VERIFY_FAILED"})
_DEFINITIONS = {
    name: PublishingJobDefinition(name, _RETRYABLE)
    for name in (
        "publishing.verify_runtime", "publishing.verify_app",
        "publishing.verify_app_state",
    )
}


class PublishingJobValidationError(ValueError):
    pass


def is_publishing_job_type(job_type: object) -> bool:
    return isinstance(job_type, str) and job_type in _DEFINITIONS


def get_publishing_job_definition(job_type: str):
    return _DEFINITIONS.get(job_type)


def validate_publishing_job_payload(payload: Any) -> dict[str, int]:
    try:
        return PublishingJobPayload.model_validate(payload).model_dump()
    except ValidationError as error:
        raise PublishingJobValidationError("Invalid publishing Job payload") from error

