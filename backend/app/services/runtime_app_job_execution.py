"""Lease-fenced execution boundary for app.install and app.verify Jobs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import load_application_config
from app.models import (
    Job,
    JobStatus,
    ManagedAppVersion,
    RuntimeAppInstallation,
    RuntimeAppInstallationRun,
)
from app.models.timestamps import utc_now
from app.services.adb_executor import AdbExecutor
from app.services.android_app_management import (
    AndroidAppManagementService,
    AppManagementError,
)
from app.services.automation_errors import AutomationError
from app.services.content_storage import ContentStorageService
from app.services.device_screen import ScreenProcessManager
from app.services.job_lifecycle import JobClaimOwnershipError, validate_job_claim
from app.services.job_logs import append_job_log
from app.services.managed_app_jobs import (
    RuntimeAppJobResult,
    validate_runtime_app_job_payload,
)
from app.services.redroid_runtime import RedroidRuntimeAdapter
from app.services.runtime_apps import _event
from app.services.runtime_operation_lock import RuntimeOperationGuard


class RuntimeAppJobExecutionService:
    def __init__(self, session: Session, *, screen_manager: ScreenProcessManager) -> None:
        self.session = session
        self.screen_manager = screen_manager

    def execute(self, job: Job, claim_token: str, attempt: int) -> dict[str, Any]:
        validate_job_claim(job, claim_token, attempt)
        if job.job_type not in {"app.install", "app.verify"} or job.runtime_id is None:
            raise AppManagementError("APP_RUNTIME_UNAVAILABLE")
        payload = validate_runtime_app_job_payload(job.payload)
        installation = self.session.get(
            RuntimeAppInstallation, payload["runtime_app_installation_id"]
        )
        run = self.session.scalar(select(RuntimeAppInstallationRun).where(
            RuntimeAppInstallationRun.job_id == job.id,
            RuntimeAppInstallationRun.runtime_app_installation_id == payload["runtime_app_installation_id"],
        ))
        if (
            installation is None
            or run is None
            or installation.runtime_id != job.runtime_id
            or installation.latest_job_id != job.id
            or run.desired_managed_app_version_id != installation.desired_managed_app_version_id
        ):
            raise AppManagementError("APP_VERSION_NOT_READY")
        self._check_cancelled(job, claim_token, attempt)
        known_installed = (
            installation.observed_managed_app_version_id
            == run.desired_managed_app_version_id
        )
        known_version_name = installation.observed_version_name
        known_version_code = installation.observed_version_code
        installation.status = "installing"
        installation.last_attempt_at = utc_now()
        installation.error_code = None
        installation.error_message = None
        job.execution_started_at = job.execution_started_at or utc_now()
        job.execution_stage = "app_installing" if job.job_type == "app.install" else "app_verifying"
        self.session.add(_event(
            installation,
            "install_started" if job.job_type == "app.install" else "verify_requested",
            job_id=job.id,
        ))
        append_job_log(
            self.session,
            job,
            level="info",
            event_type="app_install_started" if job.job_type == "app.install" else "app_verify_started",
            message="Managed application operation started",
            metadata={"installation_id": installation.id},
        )
        self.session.commit()

        def cancellation_hook() -> bool:
            with Session(bind=self.session.get_bind()) as check_session:
                current = check_session.get(Job, job.id)
                if current is None or current.status == JobStatus.CANCELLING.value:
                    return True
                try:
                    validate_job_claim(current, claim_token, attempt)
                except JobClaimOwnershipError:
                    return True
                return False

        config = load_application_config()
        service = AndroidAppManagementService(
            self.session,
            adb=AdbExecutor(default_timeout=30, cancellation_hook=cancellation_hook),
            runtime_adapter=RedroidRuntimeAdapter(),
            guard=RuntimeOperationGuard(config.bridge_lock_directory),
            storage=ContentStorageService(
                config.content_root,
                max_upload_bytes=config.managed_app_max_apk_bytes,
                max_total_bytes=config.content_max_total_bytes,
            ),
            screen_inspector=self.screen_manager,
        )
        try:
            observation = (
                service.install(
                    job.runtime_id,
                    run.desired_managed_app_version_id,
                    known_installed=known_installed,
                    known_version_name=known_version_name,
                    known_version_code=known_version_code,
                )
                if job.job_type == "app.install"
                else service.verify(job.runtime_id, run.desired_managed_app_version_id)
            )
            self._check_cancelled(job, claim_token, attempt)
            self.session.expire(installation)
            if (
                installation.desired_managed_app_version_id
                != run.desired_managed_app_version_id
            ):
                installation.status = "outdated"
                raise AppManagementError("APP_VERSION_NOT_READY")
            installation.status = "installed"
            installation.observed_managed_app_version_id = observation.observed_managed_app_version_id
            installation.observed_package_name = observation.package_name
            installation.observed_version_name = observation.version_name
            installation.observed_version_code = observation.version_code
            installation.observed_signer_fingerprint = observation.signer_fingerprint
            installation.verified_at = utc_now()
            if job.job_type == "app.install" and observation.changed:
                installation.installed_at = utc_now()
            installation.error_code = None
            installation.error_message = None
            event_type = "install_succeeded" if job.job_type == "app.install" else "verified"
            self.session.add(_event(installation, event_type, job_id=job.id))
            job.execution_stage = "app_installed" if job.job_type == "app.install" else "app_verified"
            append_job_log(
                self.session, job, level="info", event_type=event_type,
                message="Managed application operation completed",
                metadata={"installation_id": installation.id, "status": "installed"},
            )
            result = RuntimeAppJobResult(
                installation_id=installation.id,
                app_id=installation.managed_app_id,
                desired_version_id=installation.desired_managed_app_version_id,
                observed_package=installation.observed_package_name,
                observed_version_name=installation.observed_version_name,
                observed_version_code=installation.observed_version_code,
                status="installed",
                changed=observation.changed,
                inspection_level=observation.inspection_level,
                package_verification=observation.package_verification,
            ).model_dump(mode="json")
            self.session.commit()
            return result
        except (AppManagementError, AutomationError) as error:
            self.session.expire(installation)
            if isinstance(error, AppManagementError) and error.observation is not None:
                installation.observed_package_name = error.observation.package_name
                installation.observed_version_name = error.observation.version_name
                installation.observed_version_code = error.observation.version_code
                installation.observed_signer_fingerprint = error.observation.signer_fingerprint
                observed_version = self.session.scalar(select(ManagedAppVersion).where(
                    ManagedAppVersion.managed_app_id == installation.managed_app_id,
                    ManagedAppVersion.version_code == error.observation.version_code,
                    ManagedAppVersion.status.in_(["ready", "retired"]),
                ))
                installation.observed_managed_app_version_id = (
                    observed_version.id if observed_version is not None else None
                )
            if isinstance(error, AppManagementError) and error.code == "APP_NOT_INSTALLED":
                installation.status = "removed"
            elif isinstance(error, AppManagementError) and error.code == "APP_VERSION_NOT_READY":
                installation.status = "outdated"
            else:
                installation.status = "failed"
            installation.error_code = error.code
            installation.error_message = error.safe_message
            job.execution_stage = "app_operation_failed"
            self.session.add(_event(
                installation, "install_failed", job_id=job.id,
                metadata={"error_code": error.code},
            ))
            append_job_log(
                self.session, job,
                level="warning" if error.retryable else "error",
                event_type="app_operation_failed",
                message="Managed application operation failed",
                metadata={
                    "error_code": error.code,
                    "retryable": error.retryable,
                    **(
                        {"diagnostic_code": error.diagnostic_code}
                        if isinstance(error, AppManagementError)
                        and error.diagnostic_code is not None
                        else {}
                    ),
                },
            )
            self.session.commit()
            raise

    def _check_cancelled(self, job: Job, claim_token: str, attempt: int) -> None:
        self.session.expire(job)
        try:
            validate_job_claim(job, claim_token, attempt)
        except JobClaimOwnershipError as error:
            raise AppManagementError("APP_OPERATION_CANCELLED", retryable=True) from error
        if job.status == JobStatus.CANCELLING.value:
            raise AppManagementError("APP_OPERATION_CANCELLED", retryable=True)
