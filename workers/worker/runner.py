"""Worker polling loop."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from threading import Event
from typing import Any, Protocol

from worker.client import BackendClientError
from worker.config import WorkerConfig
from worker.handlers import create_default_registry
from worker.recovery import (
    LifecycleAction,
    LifecycleRecoveryStore,
    PendingLifecycleReport,
)
from worker.registry import HandlerRegistry

logger = logging.getLogger(__name__)


class JobClient(Protocol):
    """Backend operations needed by the worker."""

    def claim_job(self) -> dict[str, Any] | None:
        """Claim an eligible job, if one exists."""

    def report_succeeded(self, job_id: int, result: Any) -> None:
        """Report that a job handler completed successfully."""

    def report_failed(self, job_id: int, error_message: str) -> None:
        """Report that a job handler failed."""

    def retry_job(self, job_id: int, scheduled_at: str) -> None:
        """Schedule another attempt for a failed job."""


class Worker:
    """Poll the backend for work until a shutdown is requested."""

    def __init__(
        self,
        config: WorkerConfig,
        client: JobClient,
        stop_event: Event | None = None,
        registry: HandlerRegistry | None = None,
        clock: Callable[[], datetime] | None = None,
        recovery_store: LifecycleRecoveryStore | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._stop_event = stop_event or Event()
        self._registry = registry or create_default_registry()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._recovery_store = (
            recovery_store
            if recovery_store is not None
            else LifecycleRecoveryStore()
        )

    @property
    def stop_event(self) -> Event:
        """Event used to request and interrupt worker shutdown."""
        return self._stop_event

    def run(self) -> None:
        """Run the polling loop until the stop event is set."""
        logger.info(
            "worker startup backend_url=%s poll_interval_seconds=%s",
            self._config.backend_url,
            self._config.poll_interval_seconds,
        )
        try:
            while not self._stop_event.is_set():
                pending_report = self._recovery_store.next()
                if pending_report is not None:
                    self._recover_lifecycle_report(pending_report)
                    continue

                logger.info("polling for jobs")
                try:
                    job = self._client.claim_job()
                except BackendClientError as error:
                    logger.error("job polling failed: %s", error)
                    self._stop_event.wait(
                        self._config.poll_interval_seconds
                    )
                    continue

                if job is None:
                    logger.info("no job available")
                    self._stop_event.wait(
                        self._config.poll_interval_seconds
                    )
                    continue

                logger.info("job claimed job_id=%s", job["id"])
                job_type = job.get("job_type")
                logger.info(
                    "handler started job_id=%s job_type=%r",
                    job["id"],
                    job_type,
                )
                try:
                    result = self._registry.dispatch(
                        job_type, job.get("payload")
                    )
                except Exception as error:
                    error_message = self._format_handler_error(error)
                    logger.error(
                        "handler failed job_id=%s job_type=%r error=%s",
                        job["id"],
                        job_type,
                        error_message,
                    )
                    if self._report_failure(job, error_message):
                        self._retry_if_eligible(job)
                    continue
                logger.info(
                    "handler succeeded job_id=%s job_type=%r",
                    job["id"],
                    job_type,
                )
                self._report_success(job, result)
        finally:
            logger.info("worker shutdown")

    @staticmethod
    def _format_handler_error(error: Exception) -> str:
        detail = str(error)
        if detail:
            return f"{type(error).__name__}: {detail}"
        return type(error).__name__

    def _report_success(self, job: dict[str, Any], result: Any) -> None:
        job_id = job["id"]
        try:
            self._client.report_succeeded(job_id, result)
        except BackendClientError as error:
            logger.error(
                "lifecycle report failed job_id=%s action=succeed error=%s",
                job_id,
                error,
            )
            self._create_recovery_state(job, "succeed", result)

    def _report_failure(
        self, job: dict[str, Any], error_message: str
    ) -> bool:
        job_id = job["id"]
        try:
            self._client.report_failed(job_id, error_message)
        except BackendClientError as error:
            logger.error(
                "lifecycle report failed job_id=%s action=fail error=%s",
                job_id,
                error,
            )
            self._create_recovery_state(job, "fail", error_message)
            logger.info(
                "retry skipped job_id=%s reason=failure_report_failed",
                job_id,
            )
            return False
        return True

    def _create_recovery_state(
        self,
        job: dict[str, Any],
        action: LifecycleAction,
        value: Any,
    ) -> None:
        report = PendingLifecycleReport(dict(job), action, value)
        if self._recovery_store.add(report):
            logger.info(
                "recovery state created job_id=%s action=%s",
                report.job_id,
                action,
            )

    def _recover_lifecycle_report(
        self, report: PendingLifecycleReport
    ) -> None:
        logger.info(
            "recovery retry job_id=%s action=%s",
            report.job_id,
            report.action,
        )
        try:
            if report.action == "succeed":
                self._client.report_succeeded(report.job_id, report.value)
            else:
                self._client.report_failed(report.job_id, report.value)
        except BackendClientError as error:
            logger.error(
                "recovery still failing job_id=%s action=%s error=%s",
                report.job_id,
                report.action,
                error,
            )
            self._stop_event.wait(self._config.poll_interval_seconds)
            return

        self._recovery_store.complete(report.job_id)
        logger.info(
            "recovery succeeded job_id=%s action=%s",
            report.job_id,
            report.action,
        )
        if report.action == "fail":
            self._retry_if_eligible(report.job)

    def _retry_if_eligible(self, job: dict[str, Any]) -> None:
        job_id = job["id"]
        attempt_count = job.get("attempt_count")
        max_attempts = job.get("max_attempts")
        if (
            not isinstance(attempt_count, int)
            or isinstance(attempt_count, bool)
            or not isinstance(max_attempts, int)
            or isinstance(max_attempts, bool)
        ):
            logger.info(
                "retry skipped job_id=%s reason=invalid_attempt_metadata",
                job_id,
            )
            return
        if attempt_count >= max_attempts:
            logger.info(
                "retry skipped job_id=%s reason=max_attempts_reached "
                "attempt_count=%s max_attempts=%s",
                job_id,
                attempt_count,
                max_attempts,
            )
            return

        scheduled_at = (
            self._clock()
            + timedelta(seconds=self._config.retry_delay_seconds)
        ).isoformat()
        try:
            self._client.retry_job(job_id, scheduled_at)
        except BackendClientError as error:
            logger.error(
                "retry failed job_id=%s error=%s",
                job_id,
                error,
            )
            return
        logger.info(
            "retry scheduled job_id=%s scheduled_at=%s",
            job_id,
            scheduled_at,
        )
