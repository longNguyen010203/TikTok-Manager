"""Lease-fenced execution of generic publishing preparation checks."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import load_application_config
from app.models import (Job, JobStatus, ManagedApp, PublishingSession, Runtime,
                        RuntimeAppInstallation, WorkflowStep)
from app.models.timestamps import utc_now
from app.services.adb_executor import AdbExecutor
from app.services.android_app_management import AndroidAppManagementService, AppManagementError
from app.services.android_automation import AndroidAutomationService
from app.services.automation_artifacts import AutomationArtifactStore
from app.services.automation_errors import AutomationError
from app.services.content_storage import ContentStorageService
from app.services.device_screen import ScreenProcessManager
from app.services.job_lifecycle import JobClaimOwnershipError, validate_job_claim
from app.services.job_logs import append_job_log
from app.services.publishing_jobs import validate_publishing_job_payload
from app.services.redroid_runtime import RedroidRuntimeAdapter
from app.services.runtime_apps import RuntimeAppService
from app.services.runtime_operation_lock import RuntimeOperationGuard


class PublishingPreparationError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        self.code, self.safe_message, self.retryable = code, message, retryable
        super().__init__(message)


class PublishingJobExecutionService:
    def __init__(self, session: Session, *, screen_manager: ScreenProcessManager) -> None:
        self.session, self.screen_manager = session, screen_manager

    def execute(self, job: Job, claim_token: str, attempt: int) -> dict[str, Any]:
        validate_job_claim(job, claim_token, attempt)
        self._job_id, self._claim_token, self._attempt = job.id, claim_token, attempt
        payload = validate_publishing_job_payload(job.payload)
        record = self.session.get(PublishingSession, payload["publishing_session_id"])
        if record is None or record.runtime_id is None or job.runtime_id != record.runtime_id:
            raise PublishingPreparationError("APP_RUNTIME_UNAVAILABLE", "Pinned Runtime is unavailable")
        app = self.session.get(ManagedApp, record.managed_app_id)
        runtime = self.session.get(Runtime, record.runtime_id)
        if app is None or runtime is None or runtime.id != record.runtime_id_snapshot:
            raise PublishingPreparationError("APP_RUNTIME_UNAVAILABLE", "Pinned publishing binding is unavailable")
        job.execution_started_at = job.execution_started_at or utc_now()
        job.execution_stage = "publishing_verification"
        append_job_log(self.session, job, level="info", event_type="action_started",
                       message="Publishing preparation check started")
        self.session.commit()
        try:
            if job.job_type == "publishing.verify_runtime":
                state = self._automation().get_device_state(runtime.id)
                readiness = RuntimeAppService.readiness(self.session, runtime, runtime_ready=state.ready)
                if not readiness.publishing_ready:
                    raise PublishingPreparationError("APP_VERSION_MISMATCH", "Required managed applications are not ready")
                result = {
                    "runtime_id": runtime.id, "runtime_ready": state.ready,
                    "required_apps_ready": readiness.required_apps_ready,
                    "publishing_ready": readiness.publishing_ready,
                }
            elif job.job_type == "publishing.verify_app":
                installation = self._installation(record)
                observation = self._app_management().verify(runtime.id, record.managed_app_version_id)
                if observation.package_name != app.android_package_name:
                    raise PublishingPreparationError("APP_VERSION_MISMATCH", "Installed package does not match the pinned managed app")
                result = {
                    "managed_app_id": app.id, "managed_app_version_id": record.managed_app_version_id,
                    "expected_package": app.android_package_name, "installed": True,
                    "observed_version_name": observation.version_name,
                    "observed_version_code": observation.version_code,
                    "installation_id": installation.id,
                }
            elif job.job_type == "publishing.verify_app_state":
                launch_step = self.session.scalar(select(WorkflowStep).where(
                    WorkflowStep.workflow_id == record.workflow_id,
                    WorkflowStep.step_key == "launch_app",
                ))
                launch_job = self.session.get(Job, launch_step.job_id) if launch_step and launch_step.job_id else None
                if launch_job is None or launch_job.status != "succeeded":
                    raise PublishingPreparationError("APP_VERIFY_FAILED", "Managed app launch was not confirmed")
                state = self._automation().get_package_state(runtime.id, app.android_package_name)
                if not state.installed:
                    raise PublishingPreparationError("APP_NOT_INSTALLED", "Managed app is not installed")
                result = {
                    "managed_app_id": app.id, "expected_package": app.android_package_name,
                    "installed": state.installed, "running": state.running, "launched": True,
                }
            else:
                raise PublishingPreparationError("INVALID_WORKFLOW_PARAMETERS", "Publishing Job type is invalid")
            self._check_cancelled()
            job.execution_stage = "action_completed"
            append_job_log(self.session, job, level="info", event_type="action_completed",
                           message="Publishing preparation check completed")
            self.session.commit()
            return result
        except (AutomationError, AppManagementError) as error:
            raise PublishingPreparationError(error.code, error.safe_message, retryable=error.retryable) from error

    def _installation(self, record: PublishingSession) -> RuntimeAppInstallation:
        row = self.session.scalar(select(RuntimeAppInstallation).where(
            RuntimeAppInstallation.runtime_id == record.runtime_id,
            RuntimeAppInstallation.managed_app_id == record.managed_app_id,
        ))
        if (row is None or row.status != "installed"
                or row.desired_managed_app_version_id != record.managed_app_version_id
                or row.observed_managed_app_version_id != record.managed_app_version_id):
            raise PublishingPreparationError("APP_VERSION_MISMATCH", "Pinned managed app version is not installed")
        return row

    def _automation(self) -> AndroidAutomationService:
        config = load_application_config()
        return AndroidAutomationService(
            self.session, adb=AdbExecutor(default_timeout=30, cancellation_hook=self._cancelled),
            runtime_adapter=RedroidRuntimeAdapter(),
            guard=RuntimeOperationGuard(config.bridge_lock_directory),
            artifacts=AutomationArtifactStore(
                config.artifact_root, max_size_bytes=config.artifact_max_size_bytes,
                max_total_bytes=config.artifact_max_total_bytes,
                retention_days=config.artifact_retention_days,
                upload_retention_days=config.artifact_upload_retention_days,
            ), screen_inspector=self.screen_manager, lock_timeout=0,
        )

    def _app_management(self) -> AndroidAppManagementService:
        config = load_application_config()
        return AndroidAppManagementService(
            self.session, adb=AdbExecutor(default_timeout=30, cancellation_hook=self._cancelled),
            runtime_adapter=RedroidRuntimeAdapter(),
            guard=RuntimeOperationGuard(config.bridge_lock_directory),
            storage=ContentStorageService(
                config.content_root, max_upload_bytes=config.managed_app_max_apk_bytes,
                max_total_bytes=config.content_max_total_bytes,
            ), screen_inspector=self.screen_manager,
        )

    def _cancelled(self) -> bool:
        with Session(bind=self.session.get_bind()) as check_session:
            current = check_session.get(Job, self._job_id)
            if current is None or current.status == JobStatus.CANCELLING.value:
                return True
            try:
                validate_job_claim(current, self._claim_token, self._attempt)
            except JobClaimOwnershipError:
                return True
            return False

    def _check_cancelled(self) -> None:
        if self._cancelled():
            raise PublishingPreparationError(
                "AUTOMATION_CANCELLED", "Publishing preparation was cancelled"
            )
