"""Lease-aware worker execution tests."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Event
from typing import Any

from worker.client import BackendExecutionError
from worker.config import WorkerConfig
from worker.registry import HandlerRegistry, JobExecutionContext
from worker.runner import Worker


def claimed(job_type: str = "example") -> dict[str, Any]:
    return {
        "id": 8, "job_type": job_type, "runtime_id": 4, "account_id": None,
        "payload": {"value": 42}, "attempt_count": 1, "max_attempts": 3,
        "claim_token": "t" * 43,
        "lease_expires_at": datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat(),
    }


class StubClient:
    def __init__(self, job: dict[str, Any] | None, stop: Event) -> None:
        self.job = job
        self.stop = stop
        self.successes: list[tuple] = []
        self.failures: list[tuple] = []
        self.acks: list[tuple] = []
        self.executions: list[tuple] = []

    def claim_job(self):
        value, self.job = self.job, None
        if value is None:
            self.stop.set()
        return value

    def heartbeat(self, job_id, claim_token, attempt):
        return {"cancellation_requested": False}

    def execute_job(self, job_id, claim_token, attempt):
        self.executions.append((job_id, claim_token, attempt))
        return {"runtime_id": 4}

    def report_succeeded(self, job_id, result, claim_token, attempt):
        self.successes.append((job_id, result, claim_token, attempt)); self.stop.set()

    def report_failed(self, job_id, message, claim_token, attempt, *, error_code, retryable):
        self.failures.append((job_id, message, error_code, retryable, claim_token, attempt)); self.stop.set()

    def acknowledge_cancel(self, job_id, claim_token, attempt):
        self.acks.append((job_id, claim_token, attempt)); self.stop.set()


def test_worker_dispatches_execution_context_and_reports_with_claim() -> None:
    stop = Event(); client = StubClient(claimed(), stop); received = []
    registry = HandlerRegistry()
    def handler(context: JobExecutionContext):
        received.append(context)
        return {"ok": True}
    registry.register("example", handler)
    Worker(WorkerConfig(heartbeat_interval_seconds=0.01), client, stop, registry).run()
    assert received[0].runtime_id == 4
    assert received[0].claim_token == "t" * 43
    assert client.successes == [(8, {"ok": True}, "t" * 43, 1)]


def test_unknown_worker_exception_is_non_retryable() -> None:
    stop = Event(); client = StubClient(claimed("unknown"), stop)
    Worker(WorkerConfig(heartbeat_interval_seconds=0.01), client, stop, HandlerRegistry()).run()
    assert client.failures[0][2:4] == ("UNKNOWN_HANDLER_ERROR", False)


def test_backend_retry_classification_is_forwarded() -> None:
    stop = Event(); client = StubClient(claimed(), stop); registry = HandlerRegistry()
    def handler(_context):
        raise BackendExecutionError("ADB_UNAVAILABLE", "ADB unavailable", True)
    registry.register("example", handler)
    Worker(WorkerConfig(heartbeat_interval_seconds=0.01), client, stop, registry).run()
    assert client.failures[0][2:4] == ("ADB_UNAVAILABLE", True)


def test_device_handler_calls_backend_not_adb() -> None:
    stop = Event(); client = StubClient(claimed("device.screenshot"), stop)
    Worker(WorkerConfig(heartbeat_interval_seconds=0.01), client, stop).run()
    assert client.executions == [(8, "t" * 43, 1)]
    assert client.successes[0][1] == {"runtime_id": 4}


def test_automation_cancelled_is_acknowledged() -> None:
    stop = Event(); client = StubClient(claimed(), stop); registry = HandlerRegistry()
    def handler(_context):
        raise BackendExecutionError("AUTOMATION_CANCELLED", "cancelled", False)
    registry.register("example", handler)
    Worker(WorkerConfig(heartbeat_interval_seconds=0.01), client, stop, registry).run()
    assert client.acks == [(8, "t" * 43, 1)]
