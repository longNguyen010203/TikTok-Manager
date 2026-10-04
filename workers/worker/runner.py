"""Lease-aware worker polling and backend execution dispatch."""

from __future__ import annotations

import logging
from datetime import datetime
from threading import Event, Thread
from typing import Any, Protocol

from worker.client import BackendClientError, BackendExecutionError
from worker.config import WorkerConfig
from worker.handlers import create_default_registry
from worker.recovery import LifecycleRecoveryStore, PendingLifecycleReport
from worker.registry import HandlerRegistry, JobExecutionContext

logger = logging.getLogger(__name__)


class JobClient(Protocol):
    def claim_job(self) -> dict[str, Any] | None: ...
    def heartbeat(self, job_id: int, claim_token: str, attempt: int) -> dict[str, Any]: ...
    def execute_job(self, job_id: int, claim_token: str, attempt: int) -> Any: ...
    def report_succeeded(self, job_id: int, result: Any, claim_token: str, attempt: int) -> None: ...
    def report_failed(self, job_id: int, error_message: str, claim_token: str, attempt: int, *, error_code: str, retryable: bool) -> None: ...
    def acknowledge_cancel(self, job_id: int, claim_token: str, attempt: int) -> None: ...


class Worker:
    def __init__(self, config: WorkerConfig, client: JobClient, stop_event: Event | None = None, registry: HandlerRegistry | None = None, clock=None, recovery_store: LifecycleRecoveryStore | None = None) -> None:
        self._config = config
        self._client = client
        self._stop_event = stop_event or Event()
        self._registry = registry or create_default_registry()
        self._recovery_store = recovery_store or LifecycleRecoveryStore()

    @property
    def stop_event(self) -> Event:
        return self._stop_event

    def run(self) -> None:
        logger.info("worker startup backend_url=%s", self._config.backend_url)
        try:
            while not self._stop_event.is_set():
                pending = self._recovery_store.next()
                if pending is not None:
                    self._recover_lifecycle_report(pending)
                    continue
                try:
                    job = self._client.claim_job()
                except BackendClientError as error:
                    logger.error("job polling failed: %s", error)
                    self._stop_event.wait(self._config.poll_interval_seconds)
                    continue
                if job is None:
                    self._stop_event.wait(self._config.poll_interval_seconds)
                    continue
                self._execute_claim(job)
        finally:
            logger.info("worker shutdown")

    def _execute_claim(self, job: dict[str, Any]) -> None:
        job_id = int(job["id"])
        token = str(job["claim_token"])
        attempt = int(job["attempt_count"])
        cancelled = Event()
        heartbeat_stop = Event()
        heartbeat = Thread(target=self._heartbeat_loop, args=(job_id, token, attempt, cancelled, heartbeat_stop), daemon=True)
        heartbeat.start()
        try:
            if cancelled.is_set():
                self._client.acknowledge_cancel(job_id, token, attempt)
                return
            context = JobExecutionContext(
                job_id=job_id, job_type=str(job.get("job_type")), runtime_id=job.get("runtime_id"),
                account_id=job.get("account_id"), payload=job.get("payload"), attempt=attempt,
                claim_token=token, lease_deadline=datetime.fromisoformat(str(job["lease_expires_at"])),
                backend_client=self._client, cancellation_token=cancelled,
            )
            result = self._registry.dispatch(context)
            if cancelled.is_set():
                self._client.acknowledge_cancel(job_id, token, attempt)
            else:
                self._client.report_succeeded(job_id, result, token, attempt)
        except BackendExecutionError as error:
            if error.code == "AUTOMATION_CANCELLED":
                try:
                    self._client.acknowledge_cancel(job_id, token, attempt)
                except BackendClientError:
                    logger.error("cancellation acknowledgement failed job_id=%s", job_id)
            else:
                self._report_failure(job, error.safe_message, error.code, error.retryable)
        except Exception as error:
            self._report_failure(job, f"{type(error).__name__}: worker handler failed", "UNKNOWN_HANDLER_ERROR", False)
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=self._config.heartbeat_interval_seconds + 1)

    def _heartbeat_loop(self, job_id: int, token: str, attempt: int, cancelled: Event, stop: Event) -> None:
        while not stop.wait(self._config.heartbeat_interval_seconds):
            try:
                response = self._client.heartbeat(job_id, token, attempt)
                if response.get("cancellation_requested"):
                    cancelled.set()
            except BackendClientError as error:
                logger.warning("job heartbeat failed job_id=%s error=%s", job_id, error)

    def _report_failure(self, job: dict[str, Any], message: str, code: str, retryable: bool) -> None:
        try:
            self._client.report_failed(int(job["id"]), message, str(job["claim_token"]), int(job["attempt_count"]), error_code=code, retryable=retryable)
        except BackendClientError as error:
            logger.error("lifecycle report failed job_id=%s action=fail error=%s", job["id"], error)
            self._recovery_store.add(PendingLifecycleReport(dict(job), "fail", {"message": message, "code": code, "retryable": retryable}))

    def _recover_lifecycle_report(self, report: PendingLifecycleReport) -> None:
        job = report.job
        try:
            if report.action == "succeed":
                self._client.report_succeeded(report.job_id, report.value, job["claim_token"], job["attempt_count"])
            else:
                value = report.value
                self._client.report_failed(report.job_id, value["message"], job["claim_token"], job["attempt_count"], error_code=value["code"], retryable=value["retryable"])
        except BackendClientError:
            self._stop_event.wait(self._config.poll_interval_seconds)
            return
        self._recovery_store.complete(report.job_id)
