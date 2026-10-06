"""Lease-fenced execution boundary for observational TikTok UI Jobs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import load_application_config
from app.models import Job, JobStatus, ManagedApp, RuntimeAppInstallation
from app.models.timestamps import utc_now
from app.schemas.tiktok_action import TikTokDetectScreenResult
from app.services.adb_executor import AdbExecutor, AdbExecutorError
from app.services.android_automation import AutomationReadinessService
from app.services.automation_errors import AutomationError
from app.services.android_ui_automation import AndroidUiAutomationService
from app.services.android_ui_hierarchy import UiHierarchyParser, UiParserLimits
from app.services.device_screen import ScreenProcessManager
from app.services.job_lifecycle import JobClaimOwnershipError, validate_job_claim
from app.services.job_logs import append_job_log
from app.services.redroid_runtime import RedroidRuntimeAdapter
from app.services.runtime_operation_lock import RuntimeOperationGuard
from app.services.tiktok_errors import TikTokActionError, tiktok_error
from app.services.tiktok_jobs import validate_tiktok_job_payload
from app.services.tiktok_screen_resolver import TikTokScreen, TikTokScreenResolver, TikTokSelectorResolver
from app.services.tiktok_ui_profiles import TikTokUiProfileRegistry


class TikTokJobExecutionService:
    def __init__(self, session: Session, *, screen_manager: ScreenProcessManager) -> None:
        self.session = session
        self.screen_manager = screen_manager

    def execute(self, job: Job, claim_token: str, attempt: int) -> dict[str, Any]:
        validate_job_claim(job, claim_token, attempt)
        payload = validate_tiktok_job_payload(job.payload)
        if job.job_type != "tiktok.detect_screen" or job.runtime_id != payload["runtime_id"]:
            raise tiktok_error("TIKTOK_UI_PROFILE_MISMATCH")
        app = self.session.get(ManagedApp, payload["managed_app_id"])
        installation = self.session.scalar(select(RuntimeAppInstallation).where(
            RuntimeAppInstallation.runtime_id == job.runtime_id,
            RuntimeAppInstallation.managed_app_id == payload["managed_app_id"],
        ))
        if app is None or installation is None or installation.status != "installed":
            raise tiktok_error("TIKTOK_UI_PROFILE_NOT_FOUND")
        profile, definition = TikTokUiProfileRegistry().pinned(self.session, payload["ui_profile_id"])
        if profile.package_name != app.android_package_name or installation.observed_version_code is None:
            raise tiktok_error("TIKTOK_UI_PROFILE_MISMATCH")
        if ((profile.min_version_code is not None and installation.observed_version_code < profile.min_version_code)
                or (profile.max_version_code is not None and installation.observed_version_code > profile.max_version_code)):
            raise tiktok_error("TIKTOK_UI_PROFILE_MISMATCH")
        self._check_cancelled(job, claim_token, attempt)
        job.execution_started_at = job.execution_started_at or utc_now()
        job.execution_stage = "tiktok_action_started"
        append_job_log(self.session, job, level="info", event_type="tiktok_action_started", message="TikTok screen detection started")
        append_job_log(self.session, job, level="info", event_type="ui_profile_selected", message="TikTok UI profile selected",
                       metadata={"profile_id": profile.id, "profile_version": profile.version, "profile_fingerprint": profile.profile_fingerprint})
        self.session.commit()
        config = load_application_config()

        def cancelled() -> bool:
            with Session(bind=self.session.get_bind()) as check:
                current = check.get(Job, job.id)
                if current is None or current.status == JobStatus.CANCELLING.value:
                    return True
                try:
                    validate_job_claim(current, claim_token, attempt)
                except JobClaimOwnershipError:
                    return True
                return False

        adb = AdbExecutor(default_timeout=30, cancellation_hook=cancelled)
        parser = UiHierarchyParser(UiParserLimits(
            config.android_ui_max_xml_bytes, config.android_ui_max_nodes,
            config.android_ui_max_depth, config.android_ui_max_text_length,
            config.android_ui_max_attribute_length,
        ))
        ui = AndroidUiAutomationService(
            self.session, adb=adb,
            readiness=AutomationReadinessService(RedroidRuntimeAdapter(), adb, screen_inspector=self.screen_manager),
            guard=RuntimeOperationGuard(config.bridge_lock_directory), parser=parser,
            lock_timeout=0,
        )
        try:
            with ui.open_session(job.runtime_id) as action:
                foreground = action.get_foreground_app()
                if foreground.package_name != app.android_package_name:
                    raise tiktok_error("TIKTOK_APP_NOT_FOREGROUND")
                hierarchy = action.dump_ui_hierarchy()
                screen = TikTokScreenResolver().classify(hierarchy, definition, foreground.package_name)
                display = action.get_display_state()
            self._check_cancelled(job, claim_token, attempt)
            result = TikTokDetectScreenResult(**{
                "screen": screen.value, "foreground_package": foreground.package_name,
                "profile_id": profile.id, "profile_version": profile.version,
                "profile_fingerprint": profile.profile_fingerprint,
                "node_count": len(hierarchy.nodes), "display_category": display.category,
                "changed": False,
            }).model_dump(mode="json")
            job.execution_stage = "tiktok_action_completed"
            append_job_log(self.session, job, level="info", event_type="screen_detected", message="TikTok screen classified",
                           metadata={"screen": screen.value, "profile_id": profile.id, "node_count": len(hierarchy.nodes), "display_category": display.category})
            if screen != TikTokScreen.UNKNOWN:
                screen_definition = next(item for item in definition.screens if item.key == screen.value)
                selector_map = {item.key: item for item in definition.selectors}
                resolver = TikTokSelectorResolver()
                for selector_key in screen_definition.required_selectors:
                    resolved = resolver.resolve(hierarchy, selector_map[selector_key])
                    append_job_log(
                        self.session, job, level="debug",
                        event_type="selector_resolved",
                        message="Server-owned UI selector resolved",
                        metadata={
                            "selector_key": resolved.selector_key,
                            "resolution_method": resolved.method,
                            "snapshot_fingerprint": resolved.snapshot_fingerprint,
                        },
                    )
            append_job_log(self.session, job, level="info", event_type="tiktok_action_completed", message="TikTok screen detection completed")
            self.session.commit()
            return result
        except AdbExecutorError as error:
            mapped = tiktok_error("TIKTOK_ACTION_CANCELLED", retryable=True) if error.kind == "cancelled" else tiktok_error("TIKTOK_UI_DUMP_INVALID", retryable=error.kind in {"timeout", "unavailable"})
            self._log_failure(job, mapped)
            raise mapped from error
        except TikTokActionError as error:
            self._log_failure(job, error)
            raise
        except AutomationError as error:
            append_job_log(
                self.session, job,
                level="warning" if error.retryable else "error",
                event_type="tiktok_action_cancelled" if error.code == "AUTOMATION_CANCELLED" else "tiktok_action_failed",
                message="TikTok screen detection did not complete",
                metadata={"error_code": error.code, "retryable": error.retryable},
            )
            job.execution_stage = "tiktok_action_failed"
            self.session.commit()
            raise

    def _check_cancelled(self, job: Job, token: str, attempt: int) -> None:
        self.session.expire(job)
        try:
            validate_job_claim(job, token, attempt)
        except JobClaimOwnershipError as error:
            raise tiktok_error("TIKTOK_ACTION_CANCELLED", retryable=True) from error
        if job.status == JobStatus.CANCELLING.value:
            raise tiktok_error("TIKTOK_ACTION_CANCELLED", retryable=True)

    def _log_failure(self, job: Job, error: TikTokActionError) -> None:
        event = "tiktok_action_cancelled" if error.code == "TIKTOK_ACTION_CANCELLED" else "tiktok_action_failed"
        append_job_log(self.session, job, level="warning" if error.retryable else "error", event_type=event,
                       message="TikTok screen detection did not complete", metadata={"error_code": error.code, "retryable": error.retryable})
        job.execution_stage = event
        self.session.commit()
