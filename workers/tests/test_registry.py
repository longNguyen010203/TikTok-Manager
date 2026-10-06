"""Tests for job handler registration and dispatch."""

from typing import Any

import pytest

from worker.handlers import create_default_registry, echo
from datetime import datetime, timezone
from threading import Event
from worker.registry import HandlerRegistry, JobExecutionContext, UnknownJobTypeError


def context(payload: Any, job_type: str = "example") -> JobExecutionContext:
    return JobExecutionContext(1, job_type, 2, None, payload, 1, "t" * 32, datetime.now(timezone.utc), object(), Event())


def test_registered_handler_can_be_looked_up() -> None:
    registry = HandlerRegistry()
    registry.register("example", echo)

    assert registry.get("example") is echo


def test_unknown_handler_raises_specific_error() -> None:
    registry = HandlerRegistry()

    with pytest.raises(
        UnknownJobTypeError,
        match="no handler registered for job type 'missing'",
    ):
        registry.get("missing")


@pytest.mark.parametrize(
    "payload",
    [None, "hello", [1, 2], {"message": "hello", "nested": {"ok": True}}],
)
def test_echo_handler_returns_input_payload(payload: Any) -> None:
    assert echo(context(payload)) is payload


def test_registry_dispatches_payload_to_matching_handler() -> None:
    received: list[Any] = []

    def handler(execution: JobExecutionContext) -> dict[str, Any]:
        received.append(execution.payload)
        return {"handled": execution.payload}

    registry = HandlerRegistry()
    registry.register("example", handler)
    payload = {"value": 7}

    result = registry.dispatch(context(payload))

    assert received == [payload]
    assert result == {"handled": payload}


def test_content_inspect_is_registered_without_runtime_target() -> None:
    class Client:
        def execute_job(self, job_id, claim_token, attempt):
            return {"content_asset_id": 9, "processing_status": "ready"}

    execution = JobExecutionContext(
        4,
        "content.inspect",
        None,
        None,
        {"content_asset_id": 9, "content_asset_version_id": 11},
        1,
        "t" * 32,
        datetime.now(timezone.utc),
        Client(),
        Event(),
    )
    assert create_default_registry().dispatch(execution) == {
        "content_asset_id": 9,
        "processing_status": "ready",
    }


def test_content_deliver_is_registered_with_exact_runtime_target() -> None:
    class Client:
        def execute_job(self, job_id, claim_token, attempt):
            return {"content_delivery_id": 12, "runtime_id": 8, "status": "succeeded"}

    execution = JobExecutionContext(
        5, "content.deliver", 8, None, {"content_delivery_id": 12}, 1,
        "t" * 32, datetime.now(timezone.utc), Client(), Event(),
    )
    assert create_default_registry().dispatch(execution) == {
        "content_delivery_id": 12,
        "runtime_id": 8,
        "status": "succeeded",
    }


def test_content_thumbnail_is_registered_without_runtime_target() -> None:
    class Client:
        def execute_job(self, job_id, claim_token, attempt):
            return {"content_variant_id": 13, "status": "ready"}

    execution = JobExecutionContext(
        6, "content.thumbnail", None, None,
        {"content_asset_id": 9, "content_asset_version_id": 11, "content_variant_id": 13},
        1, "t" * 32, datetime.now(timezone.utc), Client(), Event(),
    )
    assert create_default_registry().dispatch(execution) == {
        "content_variant_id": 13, "status": "ready"
    }


def test_app_inspect_is_registered_without_runtime_target() -> None:
    class Client:
        def execute_job(self, job_id, claim_token, attempt):
            return {"managed_app_version_id": 4, "status": "ready"}

    execution = JobExecutionContext(
        7, "app.inspect", None, None, {"managed_app_version_id": 4}, 1,
        "t" * 32, datetime.now(timezone.utc), Client(), Event(),
    )
    assert create_default_registry().dispatch(execution) == {
        "managed_app_version_id": 4, "status": "ready"
    }


@pytest.mark.parametrize("job_type", ["app.install", "app.verify"])
def test_runtime_app_jobs_are_registered_with_exact_runtime(job_type: str) -> None:
    class Client:
        def execute_job(self, job_id, claim_token, attempt):
            return {"installation_id": 12, "status": "installed"}

    execution = JobExecutionContext(
        8, job_type, 19, None, {"runtime_app_installation_id": 12}, 1,
        "t" * 32, datetime.now(timezone.utc), Client(), Event(),
    )
    assert create_default_registry().dispatch(execution) == {
        "installation_id": 12, "status": "installed"
    }


@pytest.mark.parametrize("job_type", [
    "publishing.verify_runtime", "publishing.verify_app",
    "publishing.verify_app_state",
])
def test_publishing_jobs_are_registered_with_exact_runtime(job_type: str) -> None:
    class Client:
        def execute_job(self, job_id, claim_token, attempt):
            return {"publishing_ready": True}

    execution = JobExecutionContext(
        9, job_type, 19, 4, {"publishing_session_id": 3}, 1,
        "t" * 32, datetime.now(timezone.utc), Client(), Event(),
    )
    assert create_default_registry().dispatch(execution) == {"publishing_ready": True}
