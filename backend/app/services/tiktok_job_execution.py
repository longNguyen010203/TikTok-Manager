"""Lease-fenced execution boundary for observational TikTok UI Jobs."""

from __future__ import annotations

import time
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import load_application_config
from app.models import (
    Account, ContentAssetVersion, ContentDelivery, Job, JobStatus, ManagedApp,
    RuntimeAppInstallation,
)
from app.models.timestamps import utc_now
from app.schemas.tiktok_action import (
    TikTokDetectScreenResult,
    TikTokOpenCreateResult,
    TikTokOpenCaptionResult,
    TikTokOpenMediaPickerResult,
    TikTokOpenProfileResult,
    TikTokChooseEmailSignupResult,
    TikTokSetRegistrationEmailResult,
    TikTokContinueRegistrationEmailResult,
    TikTokSelectMediaResult,
    TikTokSetCaptionResult,
    TikTokSetPostOptionsResult,
    TikTokSkipInterestsResult,
    TikTokPreparePublishResult,
)
from app.services.adb_executor import AdbExecutor, AdbExecutorError, AdbMediaRecord
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
from app.services.tiktok_action_service import (
    TikTokActionService, caption_fingerprint,
)
from app.services.tiktok_jobs import validate_tiktok_job_payload
from app.services.tiktok_screen_resolver import TikTokScreenResolver
from app.services.tiktok_ui_profiles import TikTokUiProfileRegistry
from app.schemas.account import normalize_account_email


class TikTokJobExecutionService:
    def __init__(self, session: Session, *, screen_manager: ScreenProcessManager) -> None:
        self.session = session
        self.screen_manager = screen_manager

    def execute(self, job: Job, claim_token: str, attempt: int) -> dict[str, Any]:
        validate_job_claim(job, claim_token, attempt)
        payload = validate_tiktok_job_payload(job.job_type, job.payload)
        if job.job_type not in {
            "tiktok.detect_screen", "tiktok.open_create",
            "tiktok.open_media_picker",
            "tiktok.select_media",
            "tiktok.open_caption",
            "tiktok.skip_interests",
            "tiktok.open_profile",
            "tiktok.choose_email_signup",
            "tiktok.set_registration_email",
            "tiktok.continue_registration_email",
            "tiktok.set_caption",
            "tiktok.set_post_options",
            "tiktok.prepare_publish",
        } or job.runtime_id != payload["runtime_id"]:
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
        registration_email: str | None = None
        if job.job_type in {
            "tiktok.set_registration_email",
            "tiktok.continue_registration_email",
        }:
            account = self.session.get(Account, payload["account_id"])
            if account is None or job.account_id != account.id:
                raise tiktok_error("TIKTOK_ACCOUNT_NOT_FOUND")
            if account.runtime_id != job.runtime_id:
                raise tiktok_error("TIKTOK_ACCOUNT_RUNTIME_MISMATCH")
            try:
                registration_email = normalize_account_email(account.email)
            except ValueError as error:
                raise tiktok_error("TIKTOK_ACCOUNT_EMAIL_REQUIRED") from error
            if registration_email is None:
                raise tiktok_error("TIKTOK_ACCOUNT_EMAIL_REQUIRED")
        self._check_cancelled(job, claim_token, attempt)
        job.execution_started_at = job.execution_started_at or utc_now()
        job.execution_stage = "tiktok_action_started"
        action_label = {
            "tiktok.detect_screen": "screen detection",
            "tiktok.open_create": "open Create",
            "tiktok.open_media_picker": "open media picker",
            "tiktok.select_media": "select delivered media",
            "tiktok.open_caption": "open caption screen",
            "tiktok.skip_interests": "skip interests onboarding",
            "tiktok.open_profile": "activate Profile tab",
            "tiktok.choose_email_signup": "choose email signup",
            "tiktok.set_registration_email": "set registration email",
            "tiktok.continue_registration_email": "continue registration email",
            "tiktok.set_caption": "set caption",
            "tiktok.set_post_options": "set post options",
            "tiktok.prepare_publish": "prepare publish verification",
        }[job.job_type]
        start_metadata = None
        if job.job_type == "tiktok.set_caption":
            caption = payload["caption"]
            start_metadata = {
                "caption_length": len(caption),
                "caption_sha256": caption_fingerprint(caption),
            }
        elif job.job_type == "tiktok.prepare_publish":
            caption = payload["expected_caption"]
            start_metadata = {
                "content_delivery_id": payload["content_delivery_id"],
                "caption_length": len(caption),
                "caption_sha256": caption_fingerprint(caption),
                "expected_privacy": payload["expected_privacy"],
            }
        elif job.job_type in {
            "tiktok.set_registration_email",
            "tiktok.continue_registration_email",
        }:
            assert registration_email is not None
            start_metadata = {
                "account_id": payload["account_id"],
                "email_present": True,
                "email_length": len(registration_email),
                "email_sha256": caption_fingerprint(registration_email),
            }
        append_job_log(self.session, job, level="info", event_type="tiktok_action_started", message=f"TikTok {action_label} started", metadata=start_metadata)
        append_job_log(self.session, job, level="info", event_type="ui_profile_selected", message="TikTok UI profile selected",
                       metadata={"profile_id": profile.id, "profile_version": profile.version, "profile_fingerprint": profile.profile_fingerprint})
        self.session.commit()
        config = load_application_config()

        expected_media = (
            self._resolve_delivery_media(job, payload["content_delivery_id"])
            if job.job_type in {"tiktok.select_media", "tiktok.prepare_publish"}
            else None
        )

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
        started = time.monotonic()

        def record_tap_dispatched(resolved) -> None:
            append_job_log(
                self.session, job, level="info",
                event_type="selector_resolved",
                message="Server-owned TikTok selector dispatched",
                metadata={
                    "selector_key": resolved.selector_key,
                    "resolution_method": resolved.method,
                },
            )
            self.session.commit()

        try:
            with ui.open_session(job.runtime_id) as action:
                if job.job_type == "tiktok.detect_screen":
                    result = self._detect_screen(
                        job, action, app.android_package_name, profile, definition
                    )
                elif job.job_type in {
                    "tiktok.open_create", "tiktok.open_media_picker"
                }:
                    action_service = TikTokActionService()
                    outcome = (
                        action_service.open_create(
                            action,
                            definition,
                            expected_package=app.android_package_name,
                            cancelled=cancelled,
                            on_tap_dispatched=record_tap_dispatched,
                        )
                        if job.job_type == "tiktok.open_create"
                        else action_service.open_media_picker(
                            action,
                            definition,
                            expected_package=app.android_package_name,
                            cancelled=cancelled,
                            on_tap_dispatched=record_tap_dispatched,
                        )
                    )
                    result_model = (
                        TikTokOpenCreateResult
                        if job.job_type == "tiktok.open_create"
                        else TikTokOpenMediaPickerResult
                    )
                    result = result_model(
                        screen_before=outcome.screen_before.value,
                        screen_after=outcome.screen_after.value,
                        foreground_package=outcome.foreground_package,
                        profile_id=profile.id,
                        profile_version=profile.version,
                        profile_fingerprint=profile.profile_fingerprint,
                        selector_key=outcome.selector_key,
                        resolution_method=outcome.resolution_method,
                        changed=outcome.changed,
                    ).model_dump(mode="json")
                elif job.job_type == "tiktok.select_media":
                    assert expected_media is not None
                    action_service = TikTokActionService()
                    outcome = action_service.select_media(
                        action,
                        definition,
                        expected_package=app.android_package_name,
                        expected_media=expected_media,
                        cancelled=cancelled,
                        on_tap_dispatched=record_tap_dispatched,
                    )
                    result = TikTokSelectMediaResult(
                        content_delivery_id=payload["content_delivery_id"],
                        screen_before=outcome.screen_before.value,
                        screen_after=outcome.screen_after.value,
                        foreground_package=outcome.foreground_package,
                        foreground_activity=outcome.foreground_activity,
                        profile_id=profile.id,
                        profile_version=profile.version,
                        profile_fingerprint=profile.profile_fingerprint,
                        resolution_method=outcome.resolution_method,
                        changed=outcome.changed,
                        tap_dispatched=outcome.tap_dispatched,
                        calibration_required=outcome.calibration_required,
                        node_count=outcome.node_count,
                        hierarchy_fingerprint=outcome.hierarchy_fingerprint,
                    ).model_dump(mode="json")
                elif job.job_type == "tiktok.open_caption":
                    action_service = TikTokActionService()
                    outcome = action_service.open_caption(
                        action,
                        definition,
                        expected_package=app.android_package_name,
                        cancelled=cancelled,
                        on_tap_dispatched=record_tap_dispatched,
                    )
                    result = TikTokOpenCaptionResult(
                        screen_before=outcome.screen_before.value,
                        screen_after=outcome.screen_after.value,
                        foreground_package=outcome.foreground_package,
                        foreground_activity=outcome.foreground_activity,
                        profile_id=profile.id,
                        profile_version=profile.version,
                        profile_fingerprint=profile.profile_fingerprint,
                        selector_key=outcome.selector_key,
                        resolution_method=outcome.resolution_method,
                        changed=outcome.changed,
                        tap_dispatched=outcome.tap_dispatched,
                        calibration_required=outcome.calibration_required,
                        node_count=outcome.node_count,
                        hierarchy_fingerprint=outcome.hierarchy_fingerprint,
                    ).model_dump(mode="json")
                elif job.job_type == "tiktok.skip_interests":
                    action_service = TikTokActionService()
                    outcome = action_service.skip_interests(
                        action,
                        definition,
                        expected_package=app.android_package_name,
                        cancelled=cancelled,
                        on_tap_dispatched=record_tap_dispatched,
                    )
                    result = TikTokSkipInterestsResult(
                        screen_before=outcome.screen_before.value,
                        screen_after=outcome.screen_after.value,
                        foreground_package=outcome.foreground_package,
                        foreground_activity=outcome.foreground_activity,
                        profile_id=profile.id,
                        profile_version=profile.version,
                        profile_fingerprint=profile.profile_fingerprint,
                        selector_key=outcome.selector_key,
                        resolution_method=outcome.resolution_method,
                        changed=outcome.changed,
                        tap_dispatched=outcome.tap_dispatched,
                        calibration_required=outcome.calibration_required,
                        node_count=outcome.node_count,
                        hierarchy_fingerprint=outcome.hierarchy_fingerprint,
                    ).model_dump(mode="json")
                elif job.job_type == "tiktok.open_profile":
                    action_service = TikTokActionService()
                    outcome = action_service.open_profile(
                        action,
                        definition,
                        expected_package=app.android_package_name,
                        cancelled=cancelled,
                        on_tap_dispatched=record_tap_dispatched,
                    )
                    result = TikTokOpenProfileResult(
                        screen_before=outcome.screen_before.value,
                        screen_after=outcome.screen_after.value,
                        foreground_package=outcome.foreground_package,
                        foreground_activity=outcome.foreground_activity,
                        profile_id=profile.id,
                        profile_version=profile.version,
                        profile_fingerprint=profile.profile_fingerprint,
                        selector_key=outcome.selector_key,
                        resolution_method=outcome.resolution_method,
                        changed=outcome.changed,
                        tap_dispatched=outcome.tap_dispatched,
                        calibration_required=outcome.calibration_required,
                        node_count=outcome.node_count,
                        hierarchy_fingerprint=outcome.hierarchy_fingerprint,
                    ).model_dump(mode="json")
                elif job.job_type == "tiktok.choose_email_signup":
                    action_service = TikTokActionService()
                    outcome = action_service.choose_email_signup(
                        action,
                        definition,
                        expected_package=app.android_package_name,
                        cancelled=cancelled,
                        on_tap_dispatched=record_tap_dispatched,
                    )
                    result = TikTokChooseEmailSignupResult(
                        screen_before=outcome.screen_before.value,
                        screen_after=outcome.screen_after.value,
                        foreground_package=outcome.foreground_package,
                        foreground_activity=outcome.foreground_activity,
                        profile_id=profile.id,
                        profile_version=profile.version,
                        profile_fingerprint=profile.profile_fingerprint,
                        selector_key=outcome.selector_key,
                        resolution_method=outcome.resolution_method,
                        changed=outcome.changed,
                        tap_dispatched=outcome.tap_dispatched,
                        calibration_required=outcome.calibration_required,
                        node_count=outcome.node_count,
                        hierarchy_fingerprint=outcome.hierarchy_fingerprint,
                    ).model_dump(mode="json")
                elif job.job_type == "tiktok.set_registration_email":
                    assert registration_email is not None
                    action_service = TikTokActionService()
                    outcome = action_service.set_registration_email(
                        action,
                        definition,
                        expected_package=app.android_package_name,
                        email=registration_email,
                        cancelled=cancelled,
                        on_focus_dispatched=record_tap_dispatched,
                    )
                    result = TikTokSetRegistrationEmailResult(
                        account_id=payload["account_id"],
                        screen_before=outcome.screen_before.value,
                        screen_after=outcome.screen_after.value,
                        foreground_package=outcome.foreground_package,
                        profile_id=profile.id,
                        profile_version=profile.version,
                        profile_fingerprint=profile.profile_fingerprint,
                        changed=outcome.changed,
                        verification=outcome.verification,
                        email_length=outcome.email_length,
                        continue_enabled=outcome.continue_enabled,
                        hierarchy_fingerprint=outcome.hierarchy_fingerprint,
                    ).model_dump(mode="json")
                elif job.job_type == "tiktok.continue_registration_email":
                    assert registration_email is not None
                    action_service = TikTokActionService()
                    outcome = action_service.continue_registration_email(
                        action,
                        definition,
                        expected_package=app.android_package_name,
                        email=registration_email,
                        cancelled=cancelled,
                        on_tap_dispatched=record_tap_dispatched,
                    )
                    result = TikTokContinueRegistrationEmailResult(
                        account_id=payload["account_id"],
                        screen_before=outcome.screen_before.value,
                        screen_after=outcome.screen_after.value,
                        foreground_package=outcome.foreground_package,
                        foreground_activity=outcome.foreground_activity,
                        profile_id=profile.id,
                        profile_version=profile.version,
                        profile_fingerprint=profile.profile_fingerprint,
                        selector_key=outcome.selector_key,
                        resolution_method=outcome.resolution_method,
                        changed=outcome.changed,
                        tap_dispatched=outcome.tap_dispatched,
                        calibration_required=outcome.calibration_required,
                        node_count=outcome.node_count,
                        hierarchy_fingerprint=outcome.hierarchy_fingerprint,
                    ).model_dump(mode="json")
                elif job.job_type == "tiktok.set_caption":
                    action_service = TikTokActionService()
                    outcome = action_service.set_caption(
                        action,
                        definition,
                        expected_package=app.android_package_name,
                        caption=payload["caption"],
                        cancelled=cancelled,
                        on_focus_dispatched=record_tap_dispatched,
                    )
                    result = TikTokSetCaptionResult(
                        screen_before=outcome.screen_before.value,
                        screen_after=outcome.screen_after.value,
                        foreground_package=outcome.foreground_package,
                        profile_id=profile.id,
                        profile_version=profile.version,
                        profile_fingerprint=profile.profile_fingerprint,
                        changed=outcome.changed,
                        caption_length=outcome.caption_length,
                        verification=outcome.verification,
                        keyboard_appeared=outcome.keyboard_appeared,
                        hierarchy_fingerprint=outcome.hierarchy_fingerprint,
                    ).model_dump(mode="json")
                elif job.job_type == "tiktok.set_post_options":
                    action_service = TikTokActionService()
                    outcome = action_service.set_post_options(
                        action,
                        definition,
                        expected_package=app.android_package_name,
                        privacy=payload["privacy"],
                        cancelled=cancelled,
                        on_tap_dispatched=record_tap_dispatched,
                    )
                    result = TikTokSetPostOptionsResult(
                        screen_before=outcome.screen_before.value,
                        screen_after=outcome.screen_after.value,
                        foreground_package=outcome.foreground_package,
                        profile_id=profile.id,
                        profile_version=profile.version,
                        profile_fingerprint=profile.profile_fingerprint,
                        changed=outcome.changed,
                        tap_dispatched=outcome.tap_dispatched,
                        calibration_required=outcome.calibration_required,
                        privacy=outcome.privacy,
                        verification=outcome.verification,
                        node_count=outcome.node_count,
                        hierarchy_fingerprint=outcome.hierarchy_fingerprint,
                    ).model_dump(mode="json")
                else:
                    assert expected_media is not None
                    action_service = TikTokActionService()
                    outcome = action_service.prepare_publish(
                        action,
                        definition,
                        expected_package=app.android_package_name,
                        expected_media=expected_media,
                        expected_caption=payload["expected_caption"],
                        expected_privacy=payload["expected_privacy"],
                        cancelled=cancelled,
                    )
                    result = TikTokPreparePublishResult(
                        prepared=True,
                        screen=outcome.screen.value,
                        content_delivery_id=payload["content_delivery_id"],
                        caption_verified=True,
                        privacy_verified=True,
                        privacy=outcome.privacy,
                        media_verified=True,
                        media_resolution_method=outcome.media_resolution_method,
                        post_control_present=True,
                        drafts_control_present=True,
                        changed=False,
                        foreground_package=outcome.foreground_package,
                        profile_id=profile.id,
                        profile_version=profile.version,
                        profile_fingerprint=profile.profile_fingerprint,
                        node_count=outcome.node_count,
                        hierarchy_fingerprint=outcome.hierarchy_fingerprint,
                    ).model_dump(mode="json")
            self._check_cancelled(job, claim_token, attempt)
            job.execution_stage = "tiktok_action_completed"
            if job.job_type in {
                "tiktok.open_create", "tiktok.open_media_picker"
                , "tiktok.select_media"
                , "tiktok.open_caption"
                , "tiktok.skip_interests"
                , "tiktok.open_profile"
                , "tiktok.choose_email_signup"
                , "tiktok.set_registration_email"
                , "tiktok.continue_registration_email"
                , "tiktok.set_caption"
                , "tiktok.set_post_options"
            }:
                append_job_log(
                    self.session, job, level="info",
                    event_type="screen_detected",
                    message="TikTok navigation postcondition observed",
                    metadata={
                        "screen_before": result["screen_before"],
                        "screen_after": result["screen_after"],
                        "changed": result["changed"],
                    },
                )
            append_job_log(
                self.session, job, level="info",
                event_type="tiktok_action_completed",
                message=f"TikTok {action_label} completed",
                metadata={"duration_ms": int((time.monotonic() - started) * 1000)},
            )
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
                message="TikTok action did not complete",
                metadata={"error_code": error.code, "retryable": error.retryable},
            )
            job.execution_stage = "tiktok_action_failed"
            self.session.commit()
            raise

    def _resolve_delivery_media(
        self, job: Job, delivery_id: int
    ) -> AdbMediaRecord:
        delivery = self.session.get(ContentDelivery, delivery_id)
        if (
            delivery is None
            or delivery.status != "succeeded"
            or delivery.runtime_id != job.runtime_id
            or delivery.runtime_id_snapshot != job.runtime_id
            or not delivery.import_media
            or delivery.media_uri is None
        ):
            raise tiktok_error("TIKTOK_MEDIA_DELIVERY_INVALID")
        version = self.session.get(
            ContentAssetVersion, delivery.content_asset_version_id
        )
        if (
            version is None
            or version.content_asset_id != delivery.content_asset_id
            or version.processing_status != "ready"
            or version.asset.purpose != "library"
            or version.asset.status == "deleted"
            or version.blob.status != "active"
            or delivery.delivered_sha256 != version.blob.sha256
        ):
            raise tiktok_error("TIKTOK_MEDIA_DELIVERY_INVALID")
        match = re.fullmatch(
            r"content://media/external/file/([1-9][0-9]*)", delivery.media_uri
        )
        if match is None:
            raise tiktok_error("TIKTOK_MEDIA_DELIVERY_INVALID")
        return AdbMediaRecord(
            media_id=int(match.group(1)),
            display_name=delivery.remote_filename,
            size_bytes=version.blob.size_bytes,
            mime_type=version.detected_mime_type,
            duration_ms=version.duration_ms,
            relative_path="Download/TikTokManager/",
            bucket_display_name="TikTokManager",
        )
    def _detect_screen(self, job, action, package_name, profile, definition) -> dict[str, Any]:
        foreground = action.get_foreground_app()
        if foreground.package_name != package_name:
            raise tiktok_error("TIKTOK_APP_NOT_FOREGROUND")
        hierarchy = action.dump_ui_hierarchy()
        screen = TikTokScreenResolver().classify(
            hierarchy, definition, foreground.package_name
        )
        display = action.get_display_state()
        result = TikTokDetectScreenResult(**{
            "screen": screen.value,
            "foreground_package": foreground.package_name,
            "profile_id": profile.id,
            "profile_version": profile.version,
            "profile_fingerprint": profile.profile_fingerprint,
            "node_count": len(hierarchy.nodes),
            "display_category": display.category,
            "changed": False,
        }).model_dump(mode="json")
        append_job_log(
            self.session, job, level="info", event_type="screen_detected",
            message="TikTok screen classified",
            metadata={
                "screen": screen.value,
                "profile_id": profile.id,
                "node_count": len(hierarchy.nodes),
                "display_category": display.category,
            },
        )
        return result

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
        metadata = {"error_code": error.code, "retryable": error.retryable}
        metadata.update(error.safe_metadata)
        append_job_log(self.session, job, level="warning" if error.retryable else "error", event_type=event,
                       message="TikTok action did not complete", metadata=metadata)
        job.execution_stage = event
        self.session.commit()
