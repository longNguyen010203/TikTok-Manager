"""Tests for the worker polling loop."""

import logging
from collections import deque
from datetime import datetime, timezone
from threading import Event
from typing import Any

import pytest

from worker.client import BackendClientError
from worker.config import WorkerConfig
from worker.registry import HandlerRegistry
from worker.runner import Worker


class RecordingEvent(Event):
    def __init__(self) -> None:
        super().__init__()
        self.waits: list[float | None] = []

    def wait(self, timeout: float | None = None) -> bool:
        self.waits.append(timeout)
        self.set()
        return True


class StubClient:
    def __init__(
        self,
        responses: list[dict[str, Any] | None | Exception],
        stop_event: Event | None = None,
    ) -> None:
        self.responses = deque(responses)
        self.calls = 0
        self.stop_event = stop_event
        self.success_reports: list[tuple[int, Any]] = []
        self.failure_reports: list[tuple[int, str]] = []
        self.success_report_error: BackendClientError | None = None
        self.failure_report_error: BackendClientError | None = None
        self.success_report_outcomes: deque[BackendClientError | None] = deque()
        self.failure_report_outcomes: deque[BackendClientError | None] = deque()
        self.retry_reports: list[tuple[int, str]] = []
        self.retry_error: BackendClientError | None = None

    def claim_job(self) -> dict[str, Any] | None:
        self.calls += 1
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response

    def report_succeeded(self, job_id: int, result: Any) -> None:
        self.success_reports.append((job_id, result))
        if self.stop_event is not None:
            self.stop_event.set()
        if self.success_report_outcomes:
            outcome = self.success_report_outcomes.popleft()
            if outcome is not None:
                raise outcome
        if self.success_report_error is not None:
            raise self.success_report_error

    def report_failed(self, job_id: int, error_message: str) -> None:
        self.failure_reports.append((job_id, error_message))
        if self.stop_event is not None:
            self.stop_event.set()
        if self.failure_report_outcomes:
            outcome = self.failure_report_outcomes.popleft()
            if outcome is not None:
                raise outcome
        if self.failure_report_error is not None:
            raise self.failure_report_error

    def retry_job(self, job_id: int, scheduled_at: str) -> None:
        self.retry_reports.append((job_id, scheduled_at))
        if self.retry_error is not None:
            raise self.retry_error


def test_idle_worker_waits_for_configured_interval_and_shuts_down(
    caplog: Any,
) -> None:
    event = RecordingEvent()
    client = StubClient([None])
    worker = Worker(
        WorkerConfig("http://backend:8000", 3.5), client, event
    )

    with caplog.at_level(logging.INFO):
        worker.run()

    assert client.calls == 1
    assert event.waits == [3.5]
    assert "worker startup" in caplog.text
    assert "polling for jobs" in caplog.text
    assert "no job available" in caplog.text
    assert "worker shutdown" in caplog.text


def test_worker_logs_claimed_job(caplog: pytest.LogCaptureFixture) -> None:
    event = Event()
    client = StubClient(
        [{"id": 42, "job_type": "publish_video", "payload": None}],
        event,
    )

    worker = Worker(
        WorkerConfig("http://backend:8000", 1),
        client,
        event,
    )

    with caplog.at_level(logging.INFO):
        worker.run()

    assert "job claimed job_id=42" in caplog.text
    assert "handler started job_id=42 job_type='publish_video'" in caplog.text
    assert "handler failed job_id=42 job_type='publish_video'" in caplog.text
    assert client.failure_reports == [
        (
            42,
            "UnknownJobTypeError: no handler registered for job type "
            "'publish_video'",
        )
    ]


def test_worker_dispatches_claimed_job_to_registered_handler(
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = Event()
    received: list[Any] = []

    def handler(payload: Any) -> None:
        received.append(payload)
        event.set()

    registry = HandlerRegistry()
    registry.register("example", handler)
    client = StubClient(
        [{"id": 8, "job_type": "example", "payload": {"value": 42}}],
        event,
    )
    worker = Worker(
        WorkerConfig("http://backend:8000", 1),
        client,
        event,
        registry,
    )

    with caplog.at_level(logging.INFO):
        worker.run()

    assert received == [{"value": 42}]
    assert client.success_reports == [(8, None)]
    assert "handler started job_id=8 job_type='example'" in caplog.text
    assert "handler succeeded job_id=8 job_type='example'" in caplog.text


def test_failed_handler_is_reported_and_worker_continues_polling(
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = RecordingEvent()
    handled: list[Any] = []

    def failing_handler(payload: Any) -> None:
        handled.append(payload)
        raise RuntimeError("demo failure")

    registry = HandlerRegistry()
    registry.register("fails", failing_handler)
    client = StubClient(
        [
            {
                "id": 9,
                "job_type": "fails",
                "payload": {"attempt": 1},
                "attempt_count": 1,
                "max_attempts": 3,
            },
            None,
        ]
    )
    worker = Worker(
        WorkerConfig("http://backend:8000", 1), client, event, registry
    )

    with caplog.at_level(logging.INFO):
        worker.run()

    assert handled == [{"attempt": 1}]
    assert client.calls == 2
    assert client.failure_reports == [(9, "RuntimeError: demo failure")]
    assert len(client.retry_reports) == 1
    assert "handler failed job_id=9 job_type='fails'" in caplog.text


def test_failed_job_is_scheduled_for_delayed_retry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = Event()
    fixed_time = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
    registry = HandlerRegistry()

    def fail(payload: Any) -> None:
        raise RuntimeError("temporary")

    registry.register("fails", fail)
    client = StubClient(
        [
            {
                "id": 20,
                "job_type": "fails",
                "payload": None,
                "attempt_count": 1,
                "max_attempts": 3,
            }
        ],
        event,
    )
    worker = Worker(
        WorkerConfig("http://backend:8000", 1, 15),
        client,
        event,
        registry,
        lambda: fixed_time,
    )

    with caplog.at_level(logging.INFO):
        worker.run()

    assert client.retry_reports == [(20, "2026-09-18T12:00:15+00:00")]
    assert "retry scheduled job_id=20" in caplog.text


def test_retry_is_skipped_when_max_attempts_reached(
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = Event()
    registry = HandlerRegistry()

    def fail(payload: Any) -> None:
        raise ValueError("x")

    registry.register("fails", fail)
    client = StubClient(
        [
            {
                "id": 21,
                "job_type": "fails",
                "payload": None,
                "attempt_count": 3,
                "max_attempts": 3,
            }
        ],
        event,
    )
    worker = Worker(
        WorkerConfig("http://backend:8000", 1), client, event, registry
    )

    with caplog.at_level(logging.INFO):
        worker.run()

    assert client.retry_reports == []
    assert "retry skipped job_id=21 reason=max_attempts_reached" in caplog.text


def test_retry_api_failure_is_logged_and_does_not_crash_worker(
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = RecordingEvent()
    registry = HandlerRegistry()

    def fail(payload: Any) -> None:
        raise RuntimeError("temporary")

    registry.register("fails", fail)
    client = StubClient(
        [
            {
                "id": 22,
                "job_type": "fails",
                "payload": None,
                "attempt_count": 1,
                "max_attempts": 2,
            },
            None,
        ]
    )
    client.retry_error = BackendClientError("HTTP 409")
    worker = Worker(
        WorkerConfig("http://backend:8000", 1), client, event, registry
    )

    with caplog.at_level(logging.INFO):
        worker.run()

    assert client.calls == 2
    assert len(client.retry_reports) == 1
    assert "retry failed job_id=22 error=HTTP 409" in caplog.text


@pytest.mark.parametrize("report_action", ["succeed", "fail"])
def test_lifecycle_reporting_error_does_not_crash_worker(
    report_action: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = RecordingEvent()
    registry = HandlerRegistry()
    if report_action == "succeed":
        registry.register("example", lambda payload: payload)
        job_type = "example"
    else:
        job_type = "unknown"
    client = StubClient(
        [{"id": 10, "job_type": job_type, "payload": "value"}, None]
    )
    error = BackendClientError("backend unavailable")
    if report_action == "succeed":
        client.success_report_error = error
    else:
        client.failure_report_error = error
    worker = Worker(
        WorkerConfig("http://backend:8000", 1), client, event, registry
    )

    with caplog.at_level(logging.INFO):
        worker.run()

    assert client.calls == 1
    assert (
        f"lifecycle report failed job_id=10 action={report_action}"
        in caplog.text
    )
    assert "recovery state created job_id=10" in caplog.text
    assert f"recovery retry job_id=10 action={report_action}" in caplog.text
    assert "recovery still failing job_id=10" in caplog.text


@pytest.mark.parametrize("report_action", ["succeed", "fail"])
def test_failed_lifecycle_report_recovers_before_polling_again(
    report_action: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = RecordingEvent()
    handler_calls: list[Any] = []
    registry = HandlerRegistry()

    if report_action == "succeed":
        def handler(payload: Any) -> Any:
            handler_calls.append(payload)
            return {"handled": payload}

        registry.register("example", handler)
        job_type = "example"
    else:
        def handler(payload: Any) -> None:
            handler_calls.append(payload)
            raise RuntimeError("handler error")

        registry.register("example", handler)
        job_type = "example"

    client = StubClient(
        [
            {
                "id": 30,
                "job_type": job_type,
                "payload": "value",
                "attempt_count": 1,
                "max_attempts": 1,
            },
            None,
        ]
    )
    outcomes = deque([BackendClientError("temporary"), None])
    if report_action == "succeed":
        client.success_report_outcomes = outcomes
    else:
        client.failure_report_outcomes = outcomes
    worker = Worker(
        WorkerConfig("http://backend:8000", 1), client, event, registry
    )

    with caplog.at_level(logging.INFO):
        worker.run()

    assert handler_calls == ["value"]
    assert client.calls == 2
    if report_action == "succeed":
        assert client.success_reports == [
            (30, {"handled": "value"}),
            (30, {"handled": "value"}),
        ]
    else:
        assert client.failure_reports == [
            (30, "RuntimeError: handler error"),
            (30, "RuntimeError: handler error"),
        ]
    assert f"recovery retry job_id=30 action={report_action}" in caplog.text
    assert f"recovery succeeded job_id=30 action={report_action}" in caplog.text


def test_polling_failure_waits_before_retry(caplog: Any) -> None:
    event = RecordingEvent()
    client = StubClient([BackendClientError("backend unavailable")])
    worker = Worker(WorkerConfig("http://backend:8000", 2), client, event)

    with caplog.at_level(logging.INFO):
        worker.run()

    assert event.waits == [2]
    assert "job polling failed: backend unavailable" in caplog.text
