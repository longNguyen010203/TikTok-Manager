"""HTTP client for worker-facing backend operations."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BackendClientError(RuntimeError):
    """Raised when the worker cannot complete a backend request."""


class BackendClient:
    """Minimal client for the backend job API."""

    def __init__(self, base_url: str, timeout_seconds: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._claim_url = f"{self._base_url}/jobs/claim"
        self._timeout_seconds = timeout_seconds

    def claim_job(self) -> dict[str, Any] | None:
        """Claim the next eligible job, or return None when the queue is idle."""
        request = Request(
            self._claim_url,
            data=b"",
            headers={"Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                if response.status == 204:
                    return None
                if response.status != 200:
                    raise BackendClientError(
                        f"unexpected response from job claim: HTTP {response.status}"
                    )
                body = response.read()
        except HTTPError as error:
            raise BackendClientError(
                f"job claim failed: HTTP {error.code}"
            ) from error
        except URLError as error:
            raise BackendClientError(f"job claim failed: {error.reason}") from error

        try:
            job = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise BackendClientError("job claim returned invalid JSON") from error
        if not isinstance(job, dict) or "id" not in job:
            raise BackendClientError("job claim returned an invalid job object")
        return job

    def report_succeeded(self, job_id: int, result: Any) -> None:
        """Report a successful handler result to the backend."""
        self._post_lifecycle(
            job_id,
            "succeed",
            {"result": result},
            "success",
        )

    def report_failed(self, job_id: int, error_message: str) -> None:
        """Report a handler failure to the backend."""
        self._post_lifecycle(
            job_id,
            "fail",
            {"error_message": error_message},
            "failure",
        )

    def retry_job(self, job_id: int, scheduled_at: str) -> None:
        """Requeue a failed job for a later attempt."""
        self._post_lifecycle(
            job_id,
            "retry",
            {"scheduled_at": scheduled_at},
            "retry",
        )

    def _post_lifecycle(
        self,
        job_id: int,
        action: str,
        payload: dict[str, Any],
        report_name: str,
    ) -> None:
        try:
            body = json.dumps(payload).encode()
        except (TypeError, ValueError) as error:
            raise BackendClientError(
                f"job {report_name} report contains invalid JSON"
            ) from error

        request = Request(
            f"{self._base_url}/jobs/{job_id}/{action}",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                if response.status != 200:
                    raise BackendClientError(
                        f"job {report_name} report returned HTTP {response.status}"
                    )
        except HTTPError as error:
            raise BackendClientError(
                f"job {report_name} report failed: HTTP {error.code}"
            ) from error
        except URLError as error:
            raise BackendClientError(
                f"job {report_name} report failed: {error.reason}"
            ) from error
