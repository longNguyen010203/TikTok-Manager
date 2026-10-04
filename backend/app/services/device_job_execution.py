"""Lease-protected backend execution boundary for registered device Jobs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.config import load_application_config
from app.models import Job, JobStatus
from app.models.timestamps import utc_now
from app.services.adb_executor import AdbExecutor
from app.services.android_automation import AndroidAutomationService, require_network_ready
from app.services.automation_artifacts import AutomationArtifactStore
from app.services.automation_errors import AutomationError, automation_error
from app.services.device_jobs import get_device_job_definition, validate_device_job_payload
from app.services.device_screen import ScreenProcessManager
from app.services.job_lifecycle import JobClaimOwnershipError, validate_job_claim
from app.services.job_logs import append_job_log
from app.services.redroid_runtime import RedroidRuntimeAdapter
from app.services.runtime_operation_lock import RuntimeOperationGuard


class DeviceJobExecutionService:
    """Dispatch only allowlisted device Jobs to typed automation methods."""

    def __init__(self, session: Session, *, screen_manager: ScreenProcessManager) -> None:
        self.session = session
        self.screen_manager = screen_manager

    def execute(self, job: Job, claim_token: str, attempt: int) -> dict[str, Any]:
        validate_job_claim(job, claim_token, attempt)
        definition = get_device_job_definition(job.job_type)
        assert definition is not None
        if job.runtime_id is None:
            raise automation_error("INVALID_AUTOMATION_PAYLOAD")
        payload = validate_device_job_payload(job.job_type, job.payload)
        self._check_cancelled(job, claim_token)
        require_network_ready(
            self.session, job.runtime_id,
            requires_network=definition.requires_network,
        )
        if definition.requires_network:
            self._event(job, "network_validated", "Runtime network requirement validated")
        job.execution_started_at = job.execution_started_at or utc_now()
        job.execution_stage = "action_started"
        self._event(job, "automation_started", "Device automation started")
        self._event(job, "action_started", "Automation action started")
        self.session.commit()
        buffered_events: list[str] = []

        def cancellation_hook() -> bool:
            # Use an independent, short transaction. The execution Session may
            # otherwise retain a SQLite read snapshot and miss a cancellation
            # committed by the worker-facing endpoint.
            with Session(bind=self.session.get_bind()) as cancellation_session:
                current = cancellation_session.get(Job, job.id)
                if current is None or current.status == JobStatus.CANCELLING.value:
                    return True
                try:
                    validate_job_claim(current, claim_token, attempt)
                except JobClaimOwnershipError:
                    return True
                return False

        def event_callback(event_type: str) -> None:
            # SQLite permits one writer. Holding a flushed JobLog transaction
            # across ADB would block the independent heartbeat/cancel writer.
            buffered_events.append(event_type)

        config = load_application_config()
        service = AndroidAutomationService(
            self.session,
            adb=AdbExecutor(
                default_timeout=definition.command_timeout_seconds,
                cancellation_hook=cancellation_hook,
            ),
            runtime_adapter=RedroidRuntimeAdapter(),
            guard=RuntimeOperationGuard(config.bridge_lock_directory),
            artifacts=AutomationArtifactStore(
                config.artifact_root,
                max_size_bytes=config.artifact_max_size_bytes,
                max_total_bytes=config.artifact_max_total_bytes,
                retention_days=config.artifact_retention_days,
                upload_retention_days=config.artifact_upload_retention_days,
            ),
            screen_inspector=self.screen_manager,
            readiness_timeout=min(30, definition.handler_timeout_seconds),
            lock_timeout=0,
            event_callback=event_callback,
        )
        try:
            result = self._dispatch(service, job, payload)
            self._check_cancelled(job, claim_token)
            validated = definition.result_schema.model_validate(result).model_dump(mode="json")
            self._persist_buffered_events(job, buffered_events)
            if "artifact_id" in validated:
                self._event(job, "artifact_created", "Managed artifact created", {"artifact_id": validated["artifact_id"]})
            job.execution_stage = "action_completed"
            self._event(job, "action_completed", "Automation action completed")
            self.session.commit()
            return validated
        except AutomationError as error:
            self._persist_buffered_events(job, buffered_events)
            job.execution_stage = "action_failed"
            self._event(job, "action_failed", "Automation action failed", {"error_code": error.code, "retryable": error.retryable})
            self.session.commit()
            raise

    def _persist_buffered_events(self, job: Job, events: list[str]) -> None:
        for event_type in events:
            self._event(
                job,
                event_type,
                event_type.replace("_", " ").capitalize(),
            )

    def _dispatch(self, service: AndroidAutomationService, job: Job, payload: dict[str, Any]):
        runtime_id = job.runtime_id
        assert runtime_id is not None
        if job.job_type == "device.screenshot":
            return service.capture_screenshot(runtime_id, job_id=job.id)
        if job.job_type == "device.package_state":
            return service.get_package_state(runtime_id, payload["package_name"])
        if job.job_type == "device.launch_app":
            return service.launch_package(runtime_id, payload["package_name"])
        if job.job_type == "device.stop_app":
            return service.force_stop_package(runtime_id, payload["package_name"])
        if job.job_type == "device.push_file":
            return service.push_artifact(runtime_id, payload["artifact_id"], filename=payload.get("filename"))
        if job.job_type == "device.pull_file":
            return service.pull_file(runtime_id, payload["remote_path"], job_id=job.id)
        if job.job_type == "device.import_media":
            return service.import_media(runtime_id, payload["artifact_id"], filename=payload.get("filename"))
        raise automation_error("INVALID_AUTOMATION_PAYLOAD")

    def _check_cancelled(self, job: Job, claim_token: str) -> None:
        self.session.expire(job)
        if job.status == JobStatus.CANCELLING.value or job.claim_token_hash is None:
            raise automation_error("AUTOMATION_CANCELLED")

    def _event(self, job: Job, event_type: str, message: str, metadata: dict[str, Any] | None = None) -> None:
        append_job_log(self.session, job, level="info", event_type=event_type, message=message, metadata=metadata)
