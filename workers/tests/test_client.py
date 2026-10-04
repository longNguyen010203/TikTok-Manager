"""Tests for the backend job client."""

import json
from email.message import Message
from typing import Any

import pytest

from worker.client import BackendClient, BackendClientError


class StubResponse:
    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status = status
        self._body = body
        self.headers = Message()

    def __enter__(self) -> "StubResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_claim_job_posts_to_claim_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claimed_job = {"id": 7, "job_type": "publish_video"}
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> StubResponse:
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["timeout"] = timeout
        return StubResponse(200, json.dumps(claimed_job).encode())

    monkeypatch.setattr("worker.client.urlopen", fake_urlopen)

    result = BackendClient("http://backend:8000/", timeout_seconds=4).claim_job()

    assert result == claimed_job
    assert captured == {
        "url": "http://backend:8000/jobs/claim",
        "method": "POST",
        "timeout": 4,
    }


def test_claim_job_returns_none_for_no_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "worker.client.urlopen", lambda request, timeout: StubResponse(204)
    )

    assert BackendClient("http://backend:8000").claim_job() is None


def test_claim_job_rejects_invalid_job_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "worker.client.urlopen",
        lambda request, timeout: StubResponse(200, b"[]"),
    )

    with pytest.raises(BackendClientError, match="invalid job object"):
        BackendClient("http://backend:8000").claim_job()


def test_execute_job_uses_dedicated_long_request_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, float] = {}

    def fake_urlopen(request: Any, timeout: float) -> StubResponse:
        captured["timeout"] = timeout
        return StubResponse(200, b'{"result":{"ok":true}}')

    monkeypatch.setattr("worker.client.urlopen", fake_urlopen)
    result = BackendClient(
        "http://backend:8000",
        timeout_seconds=4,
        execute_timeout_seconds=123,
    ).execute_job(9, "t" * 32, 1)

    assert result == {"ok": True}
    assert captured == {"timeout": 123}


@pytest.mark.parametrize(
    ("method_name", "job_id", "value", "path", "expected_body"),
    [
        (
            "report_succeeded",
            12,
            {"echo": "hello"},
            "/jobs/12/succeed",
            {"result": {"echo": "hello"}},
        ),
        (
            "report_failed",
            13,
            "handler exploded",
            "/jobs/13/fail",
            {"error_message": "handler exploded"},
        ),
        (
            "retry_job",
            14,
            "2026-09-18T12:00:30+00:00",
            "/jobs/14/retry",
            {"scheduled_at": "2026-09-18T12:00:30+00:00"},
        ),
    ],
)
def test_lifecycle_report_posts_json_to_expected_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    job_id: int,
    value: Any,
    path: str,
    expected_body: dict[str, Any],
) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> StubResponse:
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data)
        captured["content_type"] = request.get_header("Content-type")
        captured["claim_token"] = request.get_header("X-job-claim-token")
        captured["attempt"] = request.get_header("X-job-attempt")
        return StubResponse(200, b"{}")

    monkeypatch.setattr("worker.client.urlopen", fake_urlopen)
    client = BackendClient("http://backend:8000")

    if method_name == "report_succeeded":
        client.report_succeeded(job_id, value, "t" * 32, 2)
    elif method_name == "report_failed":
        client.report_failed(job_id, value, "t" * 32, 2)
        expected_body |= {"error_code": "JOB_EXECUTION_FAILED", "retryable": False}
    else:
        getattr(client, method_name)(job_id, value)

    expected = {
        "url": f"http://backend:8000{path}",
        "method": "POST",
        "body": expected_body,
        "content_type": "application/json",
    }
    if method_name != "retry_job":
        expected |= {"claim_token": "t" * 32, "attempt": "2"}
    else:
        expected |= {"claim_token": None, "attempt": None}
    assert captured == expected
