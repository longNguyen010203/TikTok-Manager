"""HTTP client for lease-protected worker-facing backend operations."""

from __future__ import annotations

import json
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BackendClientError(RuntimeError):
    pass


class BackendExecutionError(BackendClientError):
    def __init__(self, code: str, safe_message: str, retryable: bool) -> None:
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable
        super().__init__(safe_message)


class BackendClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 30.0,
        *,
        worker_id: str | None = None,
        execute_timeout_seconds: float = 300.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._execute_timeout_seconds = execute_timeout_seconds
        self._worker_id = worker_id or socket.gethostname()

    def claim_job(self) -> dict[str, Any] | None:
        try:
            job = self._request("/jobs/claim", {"claimed_by": self._worker_id}, allow_empty=True)
            if job is not None and "id" not in job:
                raise BackendClientError("invalid job object")
            return job
        except BackendClientError as error:
            raise BackendClientError(f"job claim failed: {error}") from error

    def heartbeat(self, job_id: int, claim_token: str, attempt: int) -> dict[str, Any]:
        return self._request(f"/jobs/{job_id}/heartbeat", {}, claim_token=claim_token, attempt=attempt)

    def execute_job(self, job_id: int, claim_token: str, attempt: int) -> Any:
        try:
            response = self._request(
                f"/jobs/{job_id}/execute",
                {},
                claim_token=claim_token,
                attempt=attempt,
                timeout_seconds=self._execute_timeout_seconds,
            )
            return response["result"]
        except BackendClientError as error:
            if isinstance(error, BackendExecutionError):
                raise
            raise BackendExecutionError("BACKEND_UNAVAILABLE", "Backend automation execution failed", True) from error

    def report_succeeded(self, job_id: int, result: Any, claim_token: str, attempt: int) -> None:
        self._request(f"/jobs/{job_id}/succeed", {"result": result}, claim_token=claim_token, attempt=attempt)

    def report_failed(self, job_id: int, error_message: str, claim_token: str, attempt: int, *, error_code: str = "JOB_EXECUTION_FAILED", retryable: bool = False) -> None:
        self._request(f"/jobs/{job_id}/fail", {"error_message": error_message, "error_code": error_code, "retryable": retryable}, claim_token=claim_token, attempt=attempt)

    def acknowledge_cancel(self, job_id: int, claim_token: str, attempt: int) -> None:
        self._request(f"/jobs/{job_id}/cancel/acknowledge", {}, claim_token=claim_token, attempt=attempt)

    def retry_job(self, job_id: int, scheduled_at: str) -> None:
        self._request(f"/jobs/{job_id}/retry", {"scheduled_at": scheduled_at})

    def _request(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        claim_token: str | None = None,
        attempt: int | None = None,
        allow_empty: bool = False,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any] | None:
        try:
            body = json.dumps(payload).encode()
        except (TypeError, ValueError) as error:
            raise BackendClientError("request contains invalid JSON") from error
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if claim_token is not None:
            headers["X-Job-Claim-Token"] = claim_token
        if attempt is not None:
            headers["X-Job-Attempt"] = str(attempt)
        request = Request(f"{self._base_url}{path}", data=body, headers=headers, method="POST")
        try:
            with urlopen(
                request,
                timeout=self._timeout_seconds
                if timeout_seconds is None
                else timeout_seconds,
            ) as response:
                if response.status == 204 and allow_empty:
                    return None
                raw = response.read()
        except HTTPError as error:
            raw = error.read()
            try:
                detail = json.loads(raw).get("detail", {})
            except Exception:
                detail = {}
            if isinstance(detail, dict) and detail.get("code"):
                raise BackendExecutionError(str(detail["code"]), str(detail.get("message", "Backend execution failed")), bool(detail.get("retryable"))) from error
            raise BackendClientError(f"HTTP {error.code}") from error
        except (URLError, TimeoutError) as error:
            raise BackendClientError("backend is unavailable") from error
        try:
            result = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise BackendClientError("backend returned invalid JSON") from error
        if not isinstance(result, dict):
            raise BackendClientError("backend returned an invalid job object")
        return result
