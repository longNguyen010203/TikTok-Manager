"""Worker configuration loaded from CLI options and environment variables."""

from __future__ import annotations

import argparse
import os
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

BACKEND_URL_ENV = "WORKER_BACKEND_URL"
POLL_INTERVAL_ENV = "WORKER_POLL_INTERVAL_SECONDS"
RETRY_DELAY_ENV = "WORKER_RETRY_DELAY_SECONDS"
HEARTBEAT_INTERVAL_ENV = "WORKER_HEARTBEAT_INTERVAL_SECONDS"
BACKEND_BACKOFF_INITIAL_ENV = "WORKER_BACKEND_BACKOFF_INITIAL_SECONDS"
BACKEND_BACKOFF_MAX_ENV = "WORKER_BACKEND_BACKOFF_MAX_SECONDS"
WORKER_ID_ENV = "WORKER_ID"
DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_RETRY_DELAY_SECONDS = 30.0
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 15.0
DEFAULT_BACKEND_BACKOFF_INITIAL_SECONDS = 1.0
DEFAULT_BACKEND_BACKOFF_MAX_SECONDS = 30.0


@dataclass(frozen=True)
class WorkerConfig:
    """Runtime settings for the polling worker."""

    backend_url: str = DEFAULT_BACKEND_URL
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS
    retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS
    heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    backend_backoff_initial_seconds: float = DEFAULT_BACKEND_BACKOFF_INITIAL_SECONDS
    backend_backoff_max_seconds: float = DEFAULT_BACKEND_BACKOFF_MAX_SECONDS
    worker_id: str = socket.gethostname()

    def __post_init__(self) -> None:
        normalized_url = self.backend_url.rstrip("/")
        parsed_url = urlparse(normalized_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("backend URL must be an absolute HTTP(S) URL")
        if self.poll_interval_seconds <= 0:
            raise ValueError("polling interval must be greater than zero")
        if self.retry_delay_seconds < 0:
            raise ValueError("retry delay must not be negative")
        if self.heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat interval must be greater than zero")
        if (
            self.backend_backoff_initial_seconds <= 0
            or self.backend_backoff_max_seconds
            < self.backend_backoff_initial_seconds
        ):
            raise ValueError("backend reconnect backoff is invalid")
        if not self.worker_id or len(self.worker_id) > 100:
            raise ValueError("worker ID must contain 1 to 100 characters")
        object.__setattr__(self, "backend_url", normalized_url)

    @classmethod
    def from_environment(cls) -> WorkerConfig:
        """Build configuration from worker environment variables."""
        backend_url = os.getenv(BACKEND_URL_ENV, DEFAULT_BACKEND_URL)
        interval_text = os.getenv(
            POLL_INTERVAL_ENV, str(DEFAULT_POLL_INTERVAL_SECONDS)
        )
        retry_delay_text = os.getenv(
            RETRY_DELAY_ENV, str(DEFAULT_RETRY_DELAY_SECONDS)
        )
        heartbeat_text = os.getenv(HEARTBEAT_INTERVAL_ENV, str(DEFAULT_HEARTBEAT_INTERVAL_SECONDS))
        backoff_initial_text = os.getenv(
            BACKEND_BACKOFF_INITIAL_ENV,
            str(DEFAULT_BACKEND_BACKOFF_INITIAL_SECONDS),
        )
        backoff_max_text = os.getenv(
            BACKEND_BACKOFF_MAX_ENV,
            str(DEFAULT_BACKEND_BACKOFF_MAX_SECONDS),
        )
        try:
            poll_interval = float(interval_text)
        except ValueError as error:
            raise ValueError(
                f"{POLL_INTERVAL_ENV} must be a number"
            ) from error
        try:
            retry_delay = float(retry_delay_text)
        except ValueError as error:
            raise ValueError(f"{RETRY_DELAY_ENV} must be a number") from error
        try:
            heartbeat_interval = float(heartbeat_text)
        except ValueError as error:
            raise ValueError(f"{HEARTBEAT_INTERVAL_ENV} must be a number") from error
        try:
            backoff_initial = float(backoff_initial_text)
            backoff_max = float(backoff_max_text)
        except ValueError as error:
            raise ValueError("worker backend backoff must be numeric") from error
        return cls(
            backend_url=backend_url,
            poll_interval_seconds=poll_interval,
            retry_delay_seconds=retry_delay,
            heartbeat_interval_seconds=heartbeat_interval,
            backend_backoff_initial_seconds=backoff_initial,
            backend_backoff_max_seconds=backoff_max,
            worker_id=os.getenv(WORKER_ID_ENV, socket.gethostname()),
        )


def parse_config(arguments: list[str] | None = None) -> WorkerConfig:
    """Load environment configuration and apply command-line overrides."""
    try:
        environment = WorkerConfig.from_environment()
    except ValueError as error:
        raise SystemExit(f"configuration error: {error}") from error

    parser = argparse.ArgumentParser(description="Run the TikTok Manager worker")
    parser.add_argument(
        "--backend-url",
        default=environment.backend_url,
        help=f"backend base URL (environment: {BACKEND_URL_ENV})",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=environment.poll_interval_seconds,
        help=(
            "seconds to wait after an idle or failed poll "
            f"(environment: {POLL_INTERVAL_ENV})"
        ),
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=environment.retry_delay_seconds,
        help=(
            "seconds before a failed job becomes retryable "
            f"(environment: {RETRY_DELAY_ENV})"
        ),
    )
    options = parser.parse_args(arguments)
    try:
        return WorkerConfig(
            backend_url=options.backend_url,
            poll_interval_seconds=options.poll_interval,
            retry_delay_seconds=options.retry_delay,
            heartbeat_interval_seconds=environment.heartbeat_interval_seconds,
            backend_backoff_initial_seconds=environment.backend_backoff_initial_seconds,
            backend_backoff_max_seconds=environment.backend_backoff_max_seconds,
            worker_id=environment.worker_id,
        )
    except ValueError as error:
        parser.error(str(error))
