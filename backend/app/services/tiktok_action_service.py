"""Typed TikTok UI actions built on one locked Android UI session."""

from __future__ import annotations

import time
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Protocol

from app.services.adb_executor import AdbExecutorError, AdbForegroundApp, AdbMediaRecord
from app.services.android_ui_hierarchy import UiHierarchy
from app.services.tiktok_errors import TikTokActionError, tiktok_error
from app.services.tiktok_media_identity import MediaIdentityResolver
from app.services.tiktok_overlay_resolver import TikTokOverlay, TikTokOverlayResolver
from app.services.tiktok_screen_resolver import (
    ResolvedUiElement,
    TikTokScreen,
    TikTokScreenResolver,
    TikTokSelectorResolver,
)
from app.services.tiktok_ui_profiles import TikTokUiProfileDefinition


class TikTokUiActionSession(Protocol):
    def get_foreground_app(self) -> AdbForegroundApp: ...
    def get_foreground_activity(self) -> AdbForegroundApp: ...
    def get_media_inventory(self) -> tuple[AdbMediaRecord, ...]: ...
    def dump_ui_hierarchy(self) -> UiHierarchy: ...
    def tap_element(self, element: ResolvedUiElement) -> None: ...
    def focus_element(self, element: ResolvedUiElement) -> None: ...
    def replace_focused_text(self, current_length: int, value: str) -> None: ...
    def validate_text_entry(self, value: str) -> None: ...
    def is_keyboard_visible(self) -> bool: ...
    def back(self) -> None: ...


_CAPTION_MAX_LENGTH = 150


def normalize_caption(value: object) -> str:
    """Normalize a bounded Unicode caption without destroying valid text."""
    if not isinstance(value, str):
        raise tiktok_error("TIKTOK_CAPTION_INVALID")
    normalized = unicodedata.normalize("NFKC", value)
    if any(
        unicodedata.category(character) in {"Cc", "Cs", "Co", "Cn"}
        for character in normalized
    ):
        raise tiktok_error("TIKTOK_CAPTION_INVALID")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if len(normalized) > _CAPTION_MAX_LENGTH:
        raise tiktok_error("TIKTOK_CAPTION_INVALID")
    return normalized


def caption_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OpenCreateOutcome:
    screen_before: TikTokScreen
    screen_after: TikTokScreen
    foreground_package: str
    changed: bool
    selector_key: str | None = None
    resolution_method: str | None = None


@dataclass(frozen=True)
class SelectMediaOutcome:
    screen_before: TikTokScreen
    screen_after: TikTokScreen
    foreground_package: str
    foreground_activity: str | None
    resolution_method: str
    changed: bool
    tap_dispatched: bool
    calibration_required: bool
    node_count: int
    hierarchy_fingerprint: str


@dataclass(frozen=True)
class OpenCaptionOutcome:
    screen_before: TikTokScreen
    screen_after: TikTokScreen
    foreground_package: str
    foreground_activity: str | None
    selector_key: str | None
    resolution_method: str
    changed: bool
    tap_dispatched: bool
    calibration_required: bool
    node_count: int
    hierarchy_fingerprint: str


@dataclass(frozen=True)
class SkipInterestsOutcome(OpenCaptionOutcome):
    pass


@dataclass(frozen=True)
class OpenProfileOutcome(OpenCaptionOutcome):
    pass


@dataclass(frozen=True)
class ChooseEmailSignupOutcome(OpenCaptionOutcome):
    pass


@dataclass(frozen=True)
class SetRegistrationEmailOutcome:
    screen_before: TikTokScreen
    screen_after: TikTokScreen
    foreground_package: str
    changed: bool
    verification: bool
    email_length: int
    continue_enabled: bool
    hierarchy_fingerprint: str


@dataclass(frozen=True)
class ContinueRegistrationEmailOutcome(OpenCaptionOutcome):
    pass


@dataclass(frozen=True)
class SetCaptionOutcome:
    screen_before: TikTokScreen
    screen_after: TikTokScreen
    foreground_package: str
    changed: bool
    caption_length: int
    verification: bool
    keyboard_appeared: bool
    hierarchy_fingerprint: str


@dataclass(frozen=True)
class SetPostOptionsOutcome:
    screen_before: TikTokScreen
    screen_after: TikTokScreen
    foreground_package: str
    changed: bool
    tap_dispatched: bool
    calibration_required: bool
    privacy: str | None
    verification: bool
    node_count: int
    hierarchy_fingerprint: str


@dataclass(frozen=True)
class PreparePublishOutcome:
    screen: TikTokScreen
    foreground_package: str
    privacy: str
    media_resolution_method: str
    node_count: int
    hierarchy_fingerprint: str


class TikTokActionService:
    """Execute profile-owned actions without accepting selectors or coordinates."""

    def __init__(
        self,
        *,
        screen_resolver: TikTokScreenResolver | None = None,
        selector_resolver: TikTokSelectorResolver | None = None,
        overlay_resolver: TikTokOverlayResolver | None = None,
        media_resolver: MediaIdentityResolver | None = None,
        timeout_seconds: float = 10.0,
        poll_interval_seconds: float = 0.5,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout_seconds <= 0 or poll_interval_seconds <= 0:
            raise ValueError("TikTok action timing must be positive")
        self.selectors = selector_resolver or TikTokSelectorResolver()
        self.screens = screen_resolver or TikTokScreenResolver(self.selectors)
        self.overlays = overlay_resolver or TikTokOverlayResolver()
        self.media = media_resolver or MediaIdentityResolver(self.selectors)
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.monotonic = monotonic
        self.sleep = sleep

    def open_create(
        self,
        session: TikTokUiActionSession,
        profile: TikTokUiProfileDefinition,
        *,
        expected_package: str,
        cancelled: Callable[[], bool] | None = None,
        on_tap_dispatched: Callable[[ResolvedUiElement], None] | None = None,
    ) -> OpenCreateOutcome:
        check_cancelled = cancelled or (lambda: False)
        foreground = session.get_foreground_app()
        hierarchy = session.dump_ui_hierarchy()
        overlay = self.overlays.detect(foreground, hierarchy)
        self._raise_for_overlay(overlay, action="create", changed=False)
        if foreground.package_name != expected_package:
            raise tiktok_error("TIKTOK_APP_NOT_FOREGROUND")
        screen_before = self.screens.classify(
            hierarchy, profile, foreground.package_name
        )
        if screen_before in {
            TikTokScreen.CAMERA_CREATE, TikTokScreen.MEDIA_PICKER
        }:
            return OpenCreateOutcome(
                screen_before, screen_before, foreground.package_name, False
            )
        if screen_before == TikTokScreen.UNKNOWN:
            raise tiktok_error("TIKTOK_UNKNOWN_SCREEN")
        if screen_before != TikTokScreen.HOME:
            raise tiktok_error("TIKTOK_UNEXPECTED_SCREEN")

        selector_map = {item.key: item for item in profile.selectors}
        try:
            create_selector = selector_map["create_button"]
        except KeyError as error:
            raise tiktok_error("TIKTOK_ELEMENT_NOT_FOUND") from error
        resolved = self.selectors.resolve(hierarchy, create_selector)
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED", retryable=True)

        # Recheck foreground immediately before the stale-snapshot-protected tap.
        if session.get_foreground_app().package_name != expected_package:
            raise tiktok_error("TIKTOK_APP_NOT_FOREGROUND")
        session.tap_element(resolved)
        if on_tap_dispatched is not None:
            on_tap_dispatched(resolved)

        deadline = self.monotonic() + self.timeout_seconds
        last_screen = TikTokScreen.UNKNOWN
        while True:
            if check_cancelled():
                raise tiktok_error("TIKTOK_ACTION_CANCELLED", retryable=True)
            foreground = session.get_foreground_app()
            hierarchy = session.dump_ui_hierarchy()
            overlay = self.overlays.detect(foreground, hierarchy)
            self._raise_for_overlay(overlay, action="create", changed=True)
            if foreground.package_name != expected_package:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            last_screen = self.screens.classify(
                hierarchy, profile, foreground.package_name
            )
            if last_screen in {
                TikTokScreen.CREATE_ENTRY,
                TikTokScreen.CAMERA_CREATE,
                TikTokScreen.MEDIA_PICKER,
            }:
                return OpenCreateOutcome(
                    screen_before,
                    last_screen,
                    foreground.package_name,
                    True,
                    resolved.selector_key,
                    resolved.method,
                )
            if last_screen not in {TikTokScreen.HOME, TikTokScreen.UNKNOWN}:
                raise tiktok_error("TIKTOK_UNEXPECTED_SCREEN")
            if self.monotonic() >= deadline:
                # A tap was dispatched, but neither success nor a safe unchanged
                # state can be proven. A worker retry must observe before acting.
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            self.sleep(self.poll_interval_seconds)

    def open_media_picker(
        self,
        session: TikTokUiActionSession,
        profile: TikTokUiProfileDefinition,
        *,
        expected_package: str,
        cancelled: Callable[[], bool] | None = None,
        on_tap_dispatched: Callable[[ResolvedUiElement], None] | None = None,
    ) -> OpenCreateOutcome:
        check_cancelled = cancelled or (lambda: False)
        foreground = session.get_foreground_app()
        hierarchy = session.dump_ui_hierarchy()
        overlay = self.overlays.detect(foreground, hierarchy)
        self._raise_for_overlay(
            overlay, action="open_media_picker", changed=False
        )
        if foreground.package_name != expected_package:
            raise tiktok_error("TIKTOK_APP_NOT_FOREGROUND")
        screen_before = self.screens.classify(
            hierarchy, profile, foreground.package_name
        )
        if screen_before == TikTokScreen.MEDIA_PICKER:
            return OpenCreateOutcome(
                screen_before, screen_before, foreground.package_name, False
            )
        if screen_before == TikTokScreen.UNKNOWN:
            raise tiktok_error("TIKTOK_UNKNOWN_SCREEN")
        if screen_before != TikTokScreen.CAMERA_CREATE:
            raise tiktok_error("TIKTOK_UNEXPECTED_SCREEN")

        selector_map = {item.key: item for item in profile.selectors}
        try:
            selector = selector_map["gallery_entry"]
        except KeyError as error:
            raise tiktok_error("TIKTOK_ELEMENT_NOT_FOUND") from error
        resolved = self.selectors.resolve(hierarchy, selector)
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED", retryable=True)
        if session.get_foreground_app().package_name != expected_package:
            raise tiktok_error("TIKTOK_APP_NOT_FOREGROUND")
        session.tap_element(resolved)
        if on_tap_dispatched is not None:
            on_tap_dispatched(resolved)

        deadline = self.monotonic() + self.timeout_seconds
        while True:
            if check_cancelled():
                raise tiktok_error("TIKTOK_ACTION_CANCELLED", retryable=True)
            foreground = session.get_foreground_app()
            hierarchy = session.dump_ui_hierarchy()
            overlay = self.overlays.detect(foreground, hierarchy)
            self._raise_for_overlay(
                overlay, action="open_media_picker", changed=True
            )
            if foreground.package_name != expected_package:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            screen_after = self.screens.classify(
                hierarchy, profile, foreground.package_name
            )
            if screen_after == TikTokScreen.MEDIA_PICKER:
                return OpenCreateOutcome(
                    screen_before,
                    screen_after,
                    foreground.package_name,
                    True,
                    resolved.selector_key,
                    resolved.method,
                )
            if screen_after not in {
                TikTokScreen.CAMERA_CREATE, TikTokScreen.UNKNOWN
            }:
                raise tiktok_error("TIKTOK_UNEXPECTED_SCREEN")
            if self.monotonic() >= deadline:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            self.sleep(self.poll_interval_seconds)

    def select_media(
        self,
        session: TikTokUiActionSession,
        profile: TikTokUiProfileDefinition,
        *,
        expected_package: str,
        expected_media: AdbMediaRecord,
        cancelled: Callable[[], bool] | None = None,
        on_tap_dispatched: Callable[[ResolvedUiElement], None] | None = None,
    ) -> SelectMediaOutcome:
        """Select one delivery only after two identical, independent observations."""
        check_cancelled = cancelled or (lambda: False)
        foreground, hierarchy, screen_before = self._observe(
            session, profile, expected_package
        )
        overlay = self.overlays.detect(foreground, hierarchy)
        self._raise_for_overlay(overlay, action="select_media", changed=False)
        if screen_before == TikTokScreen.EDIT_MEDIA:
            activity = session.get_foreground_activity()
            return SelectMediaOutcome(
                screen_before=screen_before,
                screen_after=screen_before,
                foreground_package=foreground.package_name,
                foreground_activity=activity.activity_name,
                resolution_method="calibrated_postcondition",
                changed=False,
                tap_dispatched=False,
                calibration_required=False,
                node_count=len(hierarchy.nodes),
                hierarchy_fingerprint=hierarchy.fingerprint,
            )
        if screen_before != TikTokScreen.MEDIA_PICKER:
            # No attempt is made to infer whether an uncalibrated later screen
            # means a previous selection succeeded. Replaying would be unsafe.
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        inventory = session.get_media_inventory()
        resolved = self.media.resolve(
            hierarchy, profile, expected=expected_media,
            media_inventory=inventory,
        )
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        # Immediately before mutation, independently recapture every source of
        # identity. A changed picker or MediaStore inventory invalidates the
        # prior candidate; this action never falls back to grid position.
        foreground2, hierarchy2, screen2 = self._observe(
            session, profile, expected_package
        )
        inventory2 = session.get_media_inventory()
        if (
            screen2 != TikTokScreen.MEDIA_PICKER
            or hierarchy2.fingerprint != hierarchy.fingerprint
            or inventory2 != inventory
        ):
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        resolved2 = self.media.resolve(
            hierarchy2, profile, expected=expected_media,
            media_inventory=inventory2,
        )
        if (
            resolved2.media_id != resolved.media_id
            or resolved2.node_index != resolved.node_index
            or resolved2.bounds != resolved.bounds
            or resolved2.resolution_method != resolved.resolution_method
        ):
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        element = ResolvedUiElement(
            selector_key="delivered_media",
            node_index=resolved2.node_index,
            bounds=resolved2.bounds,
            method=resolved2.resolution_method,
            snapshot_fingerprint=resolved2.snapshot_fingerprint,
            confidence="independently_verified",
            actionable=True,
        )
        session.tap_element(element)
        if on_tap_dispatched is not None:
            on_tap_dispatched(element)

        deadline = self.monotonic() + self.timeout_seconds
        while True:
            if check_cancelled():
                # Selection may already have happened. Never label this safe to
                # retry, and never dispatch a second tap.
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_foreground = session.get_foreground_app()
            after_hierarchy = session.dump_ui_hierarchy()
            if after_foreground.package_name != expected_package:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_screen = self.screens.classify(
                after_hierarchy, profile, after_foreground.package_name
            )
            changed = after_hierarchy.fingerprint != hierarchy2.fingerprint
            if changed and after_screen != TikTokScreen.MEDIA_PICKER:
                activity = session.get_foreground_activity()
                return SelectMediaOutcome(
                    screen_before=screen_before,
                    screen_after=after_screen,
                    foreground_package=after_foreground.package_name,
                    foreground_activity=activity.activity_name,
                    resolution_method=resolved2.resolution_method,
                    changed=True,
                    tap_dispatched=True,
                    calibration_required=after_screen == TikTokScreen.UNKNOWN,
                    node_count=len(after_hierarchy.nodes),
                    hierarchy_fingerprint=after_hierarchy.fingerprint,
                )
            if self.monotonic() >= deadline:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            self.sleep(self.poll_interval_seconds)

    def open_caption(
        self,
        session: TikTokUiActionSession,
        profile: TikTokUiProfileDefinition,
        *,
        expected_package: str,
        cancelled: Callable[[], bool] | None = None,
        on_tap_dispatched: Callable[[ResolvedUiElement], None] | None = None,
    ) -> OpenCaptionOutcome:
        """Advance from the calibrated editor with one stale-safe Next tap."""
        check_cancelled = cancelled or (lambda: False)
        foreground, hierarchy, screen_before = self._observe(
            session, profile, expected_package
        )
        overlay = self.overlays.detect(foreground, hierarchy)
        self._raise_for_overlay(overlay, action="open_caption", changed=False)
        if screen_before in {
            TikTokScreen.CAPTION,
            TikTokScreen.POST_SETTINGS,
            TikTokScreen.READY_TO_PUBLISH,
        }:
            activity = session.get_foreground_activity()
            return OpenCaptionOutcome(
                screen_before, screen_before, foreground.package_name,
                activity.activity_name, None, "calibrated_postcondition",
                False, False, False, len(hierarchy.nodes), hierarchy.fingerprint,
            )
        if screen_before == TikTokScreen.UNKNOWN:
            raise tiktok_error("TIKTOK_UNKNOWN_SCREEN")
        if screen_before != TikTokScreen.EDIT_MEDIA:
            raise tiktok_error("TIKTOK_UNEXPECTED_SCREEN")

        selector_map = {item.key: item for item in profile.selectors}
        try:
            selector = selector_map["editor_next_action"]
        except KeyError as error:
            raise tiktok_error("TIKTOK_ELEMENT_NOT_FOUND") from error
        resolved = self.selectors.resolve(hierarchy, selector)
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        # Re-observe the full semantic snapshot immediately before mutation.
        foreground2, hierarchy2, screen2 = self._observe(
            session, profile, expected_package
        )
        if screen2 != TikTokScreen.EDIT_MEDIA or hierarchy2.fingerprint != hierarchy.fingerprint:
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        resolved2 = self.selectors.resolve(hierarchy2, selector)
        if (
            resolved2.node_index != resolved.node_index
            or resolved2.bounds != resolved.bounds
            or resolved2.method != resolved.method
            or resolved2.snapshot_fingerprint != resolved.snapshot_fingerprint
        ):
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        session.tap_element(resolved2)
        if on_tap_dispatched is not None:
            on_tap_dispatched(resolved2)

        deadline = self.monotonic() + self.timeout_seconds
        while True:
            if check_cancelled():
                # The mutation may have completed. This is deliberately not
                # retryable and never dispatches a second tap.
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_foreground = session.get_foreground_app()
            after_hierarchy = session.dump_ui_hierarchy()
            if after_foreground.package_name != expected_package:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_screen = self.screens.classify(
                after_hierarchy, profile, after_foreground.package_name
            )
            changed = after_hierarchy.fingerprint != hierarchy2.fingerprint
            if changed and after_screen != TikTokScreen.EDIT_MEDIA:
                activity = session.get_foreground_activity()
                return OpenCaptionOutcome(
                    screen_before, after_screen, after_foreground.package_name,
                    activity.activity_name, resolved2.selector_key,
                    resolved2.method, True, True,
                    after_screen == TikTokScreen.UNKNOWN,
                    len(after_hierarchy.nodes), after_hierarchy.fingerprint,
                )
            if self.monotonic() >= deadline:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            self.sleep(self.poll_interval_seconds)

    def skip_interests(
        self,
        session: TikTokUiActionSession,
        profile: TikTokUiProfileDefinition,
        *,
        expected_package: str,
        cancelled: Callable[[], bool] | None = None,
        on_tap_dispatched: Callable[[ResolvedUiElement], None] | None = None,
    ) -> SkipInterestsOutcome:
        """Leave calibrated interests onboarding with one stale-safe Skip tap."""
        check_cancelled = cancelled or (lambda: False)
        foreground, hierarchy, screen_before = self._observe(
            session, profile, expected_package
        )
        overlay = self.overlays.detect(foreground, hierarchy)
        self._raise_for_overlay(overlay, action="skip_interests", changed=False)
        if screen_before == TikTokScreen.HOME:
            activity = session.get_foreground_activity()
            return SkipInterestsOutcome(
                screen_before, screen_before, foreground.package_name,
                activity.activity_name, None, "calibrated_postcondition",
                False, False, False, len(hierarchy.nodes), hierarchy.fingerprint,
            )
        if screen_before == TikTokScreen.UNKNOWN:
            raise tiktok_error("TIKTOK_UNKNOWN_SCREEN")
        if screen_before != TikTokScreen.ONBOARDING_INTERESTS:
            raise tiktok_error("TIKTOK_UNEXPECTED_SCREEN")

        selector_map = {item.key: item for item in profile.selectors}
        try:
            selector = selector_map["interests_skip_control"]
        except KeyError as error:
            raise tiktok_error("TIKTOK_ELEMENT_NOT_FOUND") from error
        resolved = self.selectors.resolve(hierarchy, selector)
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        foreground2, hierarchy2, screen2 = self._observe(
            session, profile, expected_package
        )
        overlay2 = self.overlays.detect(foreground2, hierarchy2)
        self._raise_for_overlay(overlay2, action="skip_interests", changed=False)
        if (
            screen2 != TikTokScreen.ONBOARDING_INTERESTS
            or hierarchy2.fingerprint != hierarchy.fingerprint
        ):
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        resolved2 = self.selectors.resolve(hierarchy2, selector)
        if (
            resolved2.node_index != resolved.node_index
            or resolved2.bounds != resolved.bounds
            or resolved2.method != resolved.method
            or resolved2.snapshot_fingerprint != resolved.snapshot_fingerprint
        ):
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        session.tap_element(resolved2)
        if on_tap_dispatched is not None:
            on_tap_dispatched(resolved2)

        deadline = self.monotonic() + self.timeout_seconds
        while True:
            if check_cancelled():
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_foreground = session.get_foreground_app()
            after_hierarchy = session.dump_ui_hierarchy()
            if after_foreground.package_name != expected_package:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_screen = self.screens.classify(
                after_hierarchy, profile, after_foreground.package_name
            )
            changed = after_hierarchy.fingerprint != hierarchy2.fingerprint
            if changed and after_screen != TikTokScreen.ONBOARDING_INTERESTS:
                activity = session.get_foreground_activity()
                return SkipInterestsOutcome(
                    screen_before, after_screen, after_foreground.package_name,
                    activity.activity_name, resolved2.selector_key,
                    resolved2.method, True, True,
                    after_screen == TikTokScreen.UNKNOWN,
                    len(after_hierarchy.nodes), after_hierarchy.fingerprint,
                )
            if self.monotonic() >= deadline:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            self.sleep(self.poll_interval_seconds)

    def open_profile(
        self,
        session: TikTokUiActionSession,
        profile: TikTokUiProfileDefinition,
        *,
        expected_package: str,
        cancelled: Callable[[], bool] | None = None,
        on_tap_dispatched: Callable[[ResolvedUiElement], None] | None = None,
    ) -> OpenProfileOutcome:
        """Activate the Profile tab and accept its calibrated session-dependent destination."""
        check_cancelled = cancelled or (lambda: False)
        foreground, hierarchy, screen_before = self._observe(
            session, profile, expected_package
        )
        overlay = self.overlays.detect(foreground, hierarchy)
        self._raise_for_overlay(overlay, action="open_profile", changed=False)
        if screen_before in {TikTokScreen.PROFILE, TikTokScreen.SIGNUP_METHOD}:
            activity = session.get_foreground_activity()
            return OpenProfileOutcome(
                screen_before, screen_before, foreground.package_name,
                activity.activity_name, None, "calibrated_postcondition",
                False, False, False, len(hierarchy.nodes), hierarchy.fingerprint,
            )
        if screen_before == TikTokScreen.UNKNOWN:
            raise tiktok_error("TIKTOK_UNKNOWN_SCREEN")
        if screen_before != TikTokScreen.HOME:
            raise tiktok_error("TIKTOK_UNEXPECTED_SCREEN")

        selector_map = {item.key: item for item in profile.selectors}
        try:
            selector = selector_map["profile_tab"]
        except KeyError as error:
            raise tiktok_error("TIKTOK_ELEMENT_NOT_FOUND") from error
        resolved = self.selectors.resolve(hierarchy, selector)
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        foreground2, hierarchy2, screen2 = self._observe(
            session, profile, expected_package
        )
        overlay2 = self.overlays.detect(foreground2, hierarchy2)
        self._raise_for_overlay(overlay2, action="open_profile", changed=False)
        if screen2 != TikTokScreen.HOME or hierarchy2.fingerprint != hierarchy.fingerprint:
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        resolved2 = self.selectors.resolve(hierarchy2, selector)
        if (
            resolved2.node_index != resolved.node_index
            or resolved2.bounds != resolved.bounds
            or resolved2.method != resolved.method
            or resolved2.snapshot_fingerprint != resolved.snapshot_fingerprint
        ):
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        session.tap_element(resolved2)
        if on_tap_dispatched is not None:
            on_tap_dispatched(resolved2)

        deadline = self.monotonic() + self.timeout_seconds
        while True:
            if check_cancelled():
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_foreground = session.get_foreground_app()
            after_hierarchy = session.dump_ui_hierarchy()
            if after_foreground.package_name != expected_package:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_screen = self.screens.classify(
                after_hierarchy, profile, after_foreground.package_name
            )
            changed = after_hierarchy.fingerprint != hierarchy2.fingerprint
            if changed and after_screen in {
                TikTokScreen.PROFILE, TikTokScreen.SIGNUP_METHOD,
            }:
                activity = session.get_foreground_activity()
                return OpenProfileOutcome(
                    screen_before, after_screen, after_foreground.package_name,
                    activity.activity_name, resolved2.selector_key,
                    resolved2.method, True, True,
                    False,
                    len(after_hierarchy.nodes), after_hierarchy.fingerprint,
                )
            if changed and after_screen == TikTokScreen.UNKNOWN:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            if self.monotonic() >= deadline:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            self.sleep(self.poll_interval_seconds)

    def choose_email_signup(
        self,
        session: TikTokUiActionSession,
        profile: TikTokUiProfileDefinition,
        *,
        expected_package: str,
        cancelled: Callable[[], bool] | None = None,
        on_tap_dispatched: Callable[[ResolvedUiElement], None] | None = None,
    ) -> ChooseEmailSignupOutcome:
        """Choose the calibrated email method once, then stop for calibration."""
        check_cancelled = cancelled or (lambda: False)
        foreground, hierarchy, screen_before = self._observe(
            session, profile, expected_package
        )
        overlay = self.overlays.detect(foreground, hierarchy)
        self._raise_for_overlay(
            overlay, action="choose_email_signup", changed=False
        )
        if screen_before == TikTokScreen.EMAIL_ENTRY:
            activity = session.get_foreground_activity()
            return ChooseEmailSignupOutcome(
                screen_before, screen_before, foreground.package_name,
                activity.activity_name, None, "calibrated_postcondition",
                False, False, False, len(hierarchy.nodes), hierarchy.fingerprint,
            )
        if screen_before == TikTokScreen.UNKNOWN:
            raise tiktok_error("TIKTOK_UNKNOWN_SCREEN")
        if screen_before != TikTokScreen.SIGNUP_METHOD:
            raise tiktok_error("TIKTOK_UNEXPECTED_SCREEN")

        selector_map = {item.key: item for item in profile.selectors}
        try:
            selector = selector_map["signup_email_method"]
        except KeyError as error:
            raise tiktok_error("TIKTOK_ELEMENT_NOT_FOUND") from error
        resolved = self.selectors.resolve(hierarchy, selector)
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        foreground2, hierarchy2, screen2 = self._observe(
            session, profile, expected_package
        )
        overlay2 = self.overlays.detect(foreground2, hierarchy2)
        self._raise_for_overlay(
            overlay2, action="choose_email_signup", changed=False
        )
        if (
            screen2 != TikTokScreen.SIGNUP_METHOD
            or hierarchy2.fingerprint != hierarchy.fingerprint
        ):
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        resolved2 = self.selectors.resolve(hierarchy2, selector)
        if (
            resolved2.node_index != resolved.node_index
            or resolved2.bounds != resolved.bounds
            or resolved2.method != resolved.method
            or resolved2.snapshot_fingerprint != resolved.snapshot_fingerprint
        ):
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        session.tap_element(resolved2)
        if on_tap_dispatched is not None:
            on_tap_dispatched(resolved2)

        deadline = self.monotonic() + self.timeout_seconds
        while True:
            if check_cancelled():
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_foreground = session.get_foreground_app()
            after_hierarchy = session.dump_ui_hierarchy()
            if after_foreground.package_name != expected_package:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_screen = self.screens.classify(
                after_hierarchy, profile, after_foreground.package_name
            )
            changed = after_hierarchy.fingerprint != hierarchy2.fingerprint
            if changed and after_screen != TikTokScreen.SIGNUP_METHOD:
                calibrated_successor = after_screen == TikTokScreen.EMAIL_ENTRY
                profile_knows_successor = any(
                    screen.key == TikTokScreen.EMAIL_ENTRY.value
                    and screen.calibrated
                    for screen in profile.screens
                )
                if profile_knows_successor and not calibrated_successor:
                    raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
                activity = session.get_foreground_activity()
                return ChooseEmailSignupOutcome(
                    screen_before, after_screen, after_foreground.package_name,
                    activity.activity_name, resolved2.selector_key,
                    resolved2.method, True, True,
                    not calibrated_successor,
                    len(after_hierarchy.nodes), after_hierarchy.fingerprint,
                )
            if self.monotonic() >= deadline:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            self.sleep(self.poll_interval_seconds)

    def set_caption(
        self,
        session: TikTokUiActionSession,
        profile: TikTokUiProfileDefinition,
        *,
        expected_package: str,
        caption: str,
        cancelled: Callable[[], bool] | None = None,
        on_focus_dispatched: Callable[[ResolvedUiElement], None] | None = None,
    ) -> SetCaptionOutcome:
        """Replace and verify the exact profile-owned caption field."""
        requested = normalize_caption(caption)
        session.validate_text_entry(requested)
        check_cancelled = cancelled or (lambda: False)
        foreground, hierarchy, screen_before = self._observe(
            session, profile, expected_package
        )
        overlay = self.overlays.detect(foreground, hierarchy)
        self._raise_for_overlay(overlay, action="set_caption", changed=False)
        if screen_before != TikTokScreen.READY_TO_PUBLISH:
            if screen_before == TikTokScreen.UNKNOWN:
                raise tiktok_error("TIKTOK_UNKNOWN_SCREEN")
            raise tiktok_error("TIKTOK_UNEXPECTED_SCREEN")
        selector_map = {item.key: item for item in profile.selectors}
        try:
            selector = selector_map["caption_input"]
        except KeyError as error:
            raise tiktok_error("TIKTOK_ELEMENT_NOT_FOUND") from error
        resolved = self.selectors.resolve(hierarchy, selector)
        current_text = hierarchy.nodes[resolved.node_index].text
        if current_text == requested:
            try:
                keyboard = session.is_keyboard_visible()
            except AdbExecutorError as error:
                raise tiktok_error("TIKTOK_KEYBOARD_UNAVAILABLE") from error
            return SetCaptionOutcome(
                screen_before, screen_before, foreground.package_name, False,
                len(requested), True, keyboard, hierarchy.fingerprint,
            )
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        foreground2, hierarchy2, screen2 = self._observe(
            session, profile, expected_package
        )
        if screen2 != TikTokScreen.READY_TO_PUBLISH or hierarchy2.fingerprint != hierarchy.fingerprint:
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        resolved2 = self.selectors.resolve(hierarchy2, selector)
        if (
            resolved2.node_index != resolved.node_index
            or resolved2.bounds != resolved.bounds
            or resolved2.method != resolved.method
            or resolved2.snapshot_fingerprint != resolved.snapshot_fingerprint
        ):
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        session.focus_element(resolved2)
        if on_focus_dispatched is not None:
            on_focus_dispatched(resolved2)
        try:
            keyboard_appeared = session.is_keyboard_visible()
        except AdbExecutorError as error:
            raise tiktok_error("TIKTOK_KEYBOARD_UNAVAILABLE") from error
        if not keyboard_appeared:
            raise tiktok_error("TIKTOK_KEYBOARD_UNAVAILABLE")
        if check_cancelled():
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")

        # Clearing uses fixed backend-owned MOVE_END/DEL keycodes. The caller
        # supplies neither keycodes nor an encoded shell fragment.
        session.replace_focused_text(len(current_text), requested)

        deadline = self.monotonic() + self.timeout_seconds
        while True:
            if check_cancelled():
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_foreground = session.get_foreground_app()
            after_hierarchy = session.dump_ui_hierarchy()
            if after_foreground.package_name != expected_package:
                raise tiktok_error("TIKTOK_CAPTION_VERIFICATION_FAILED")
            try:
                after_element = self.selectors.resolve(after_hierarchy, selector)
            except TikTokActionError as error:
                if self.monotonic() >= deadline:
                    raise tiktok_error("TIKTOK_CAPTION_VERIFICATION_FAILED") from error
            else:
                if after_hierarchy.nodes[after_element.node_index].text == requested:
                    break
            if self.monotonic() >= deadline:
                raise tiktok_error("TIKTOK_CAPTION_VERIFICATION_FAILED")
            self.sleep(self.poll_interval_seconds)

        # Restore the post screen only when the typed IME observation proved
        # that Back will close a keyboard rather than navigate away.
        session.back()
        deadline = self.monotonic() + self.timeout_seconds
        while True:
            after_foreground, after_hierarchy, screen_after = self._observe(
                session, profile, expected_package
            )
            try:
                after_element = self.selectors.resolve(after_hierarchy, selector)
            except TikTokActionError as error:
                if self.monotonic() >= deadline:
                    raise tiktok_error("TIKTOK_CAPTION_VERIFICATION_FAILED") from error
            else:
                exact = after_hierarchy.nodes[after_element.node_index].text == requested
                if screen_after == TikTokScreen.READY_TO_PUBLISH and exact:
                    return SetCaptionOutcome(
                        screen_before, screen_after, after_foreground.package_name,
                        True, len(requested), True, keyboard_appeared,
                        after_hierarchy.fingerprint,
                    )
            if self.monotonic() >= deadline:
                raise tiktok_error("TIKTOK_CAPTION_VERIFICATION_FAILED")
            self.sleep(self.poll_interval_seconds)

    def set_registration_email(
        self,
        session: TikTokUiActionSession,
        profile: TikTokUiProfileDefinition,
        *,
        expected_package: str,
        email: str,
        cancelled: Callable[[], bool] | None = None,
        on_focus_dispatched: Callable[[ResolvedUiElement], None] | None = None,
    ) -> SetRegistrationEmailOutcome:
        """Set and verify one server-resolved Account email without submitting it."""
        session.validate_text_entry(email)
        check_cancelled = cancelled or (lambda: False)
        foreground, hierarchy, screen_before = self._observe(
            session, profile, expected_package
        )
        overlay = self.overlays.detect(foreground, hierarchy)
        self._raise_for_overlay(
            overlay, action="set_registration_email", changed=False
        )
        if screen_before != TikTokScreen.EMAIL_ENTRY:
            if screen_before == TikTokScreen.UNKNOWN:
                raise tiktok_error("TIKTOK_UNKNOWN_SCREEN")
            raise tiktok_error("TIKTOK_UNEXPECTED_SCREEN")
        selector_map = {item.key: item for item in profile.selectors}
        try:
            field_selector = selector_map["email_input"]
            continue_selector = selector_map["email_continue"]
        except KeyError as error:
            raise tiktok_error("TIKTOK_ELEMENT_NOT_FOUND") from error
        resolved = self.selectors.resolve(hierarchy, field_selector)
        current_text = hierarchy.nodes[resolved.node_index].text

        def continue_enabled(snapshot: UiHierarchy) -> bool:
            control = self.selectors.resolve(snapshot, continue_selector)
            return snapshot.nodes[control.node_index].enabled

        if current_text == email:
            return SetRegistrationEmailOutcome(
                screen_before, screen_before, foreground.package_name, False,
                True, len(email), continue_enabled(hierarchy), hierarchy.fingerprint,
            )
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        foreground2, hierarchy2, screen2 = self._observe(
            session, profile, expected_package
        )
        overlay2 = self.overlays.detect(foreground2, hierarchy2)
        self._raise_for_overlay(
            overlay2, action="set_registration_email", changed=False
        )
        if screen2 != TikTokScreen.EMAIL_ENTRY or hierarchy2.fingerprint != hierarchy.fingerprint:
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        resolved2 = self.selectors.resolve(hierarchy2, field_selector)
        if (
            resolved2.node_index != resolved.node_index
            or resolved2.bounds != resolved.bounds
            or resolved2.method != resolved.method
            or resolved2.snapshot_fingerprint != resolved.snapshot_fingerprint
        ):
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        session.focus_element(resolved2)
        if on_focus_dispatched is not None:
            on_focus_dispatched(resolved2)
        try:
            keyboard_appeared = session.is_keyboard_visible()
        except AdbExecutorError as error:
            raise tiktok_error("TIKTOK_KEYBOARD_UNAVAILABLE") from error
        if not keyboard_appeared:
            raise tiktok_error("TIKTOK_KEYBOARD_UNAVAILABLE")
        if check_cancelled():
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")

        session.replace_focused_text(len(current_text), email)
        deadline = self.monotonic() + self.timeout_seconds
        while True:
            if check_cancelled():
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_foreground = session.get_foreground_app()
            after_hierarchy = session.dump_ui_hierarchy()
            if after_foreground.package_name != expected_package:
                raise tiktok_error("TIKTOK_EMAIL_VERIFICATION_FAILED")
            try:
                after_element = self.selectors.resolve(
                    after_hierarchy, field_selector
                )
                exact = after_hierarchy.nodes[after_element.node_index].text == email
                screen_after = self.screens.classify(
                    after_hierarchy, profile, after_foreground.package_name
                )
                enabled = continue_enabled(after_hierarchy)
            except TikTokActionError as error:
                if self.monotonic() >= deadline:
                    raise tiktok_error("TIKTOK_EMAIL_VERIFICATION_FAILED") from error
            else:
                if screen_after == TikTokScreen.EMAIL_ENTRY and exact:
                    return SetRegistrationEmailOutcome(
                        screen_before, screen_after,
                        after_foreground.package_name, True, True, len(email),
                        enabled, after_hierarchy.fingerprint,
                    )
            if self.monotonic() >= deadline:
                raise tiktok_error("TIKTOK_EMAIL_VERIFICATION_FAILED")
            self.sleep(self.poll_interval_seconds)

    def continue_registration_email(
        self,
        session: TikTokUiActionSession,
        profile: TikTokUiProfileDefinition,
        *,
        expected_package: str,
        email: str,
        cancelled: Callable[[], bool] | None = None,
        on_tap_dispatched: Callable[[ResolvedUiElement], None] | None = None,
    ) -> ContinueRegistrationEmailOutcome:
        """Verify the Account-bound email and activate Continue exactly once."""
        check_cancelled = cancelled or (lambda: False)
        foreground, hierarchy, screen_before = self._observe(
            session, profile, expected_package
        )
        overlay = self.overlays.detect(foreground, hierarchy)
        self._raise_for_overlay(
            overlay, action="continue_registration_email", changed=False
        )
        if screen_before == TikTokScreen.VERIFICATION_REQUIRED:
            activity = session.get_foreground_activity()
            return ContinueRegistrationEmailOutcome(
                screen_before, screen_before, foreground.package_name,
                activity.activity_name, None, "calibrated_postcondition",
                False, False, False, len(hierarchy.nodes), hierarchy.fingerprint,
            )
        if screen_before == TikTokScreen.UNKNOWN:
            raise tiktok_error("TIKTOK_UNKNOWN_SCREEN")
        if screen_before != TikTokScreen.EMAIL_ENTRY:
            raise tiktok_error("TIKTOK_UNEXPECTED_SCREEN")
        selector_map = {item.key: item for item in profile.selectors}
        try:
            field_selector = selector_map["email_input"]
            continue_selector = selector_map["email_continue"]
        except KeyError as error:
            raise tiktok_error("TIKTOK_ELEMENT_NOT_FOUND") from error
        field = self.selectors.resolve(hierarchy, field_selector)
        control = self.selectors.resolve(hierarchy, continue_selector)
        if hierarchy.nodes[field.node_index].text != email:
            raise tiktok_error("TIKTOK_REGISTRATION_EMAIL_MISMATCH")
        if not hierarchy.nodes[control.node_index].enabled:
            raise tiktok_error("TIKTOK_REGISTRATION_CONTINUE_DISABLED")
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        foreground2, hierarchy2, screen2 = self._observe(
            session, profile, expected_package
        )
        overlay2 = self.overlays.detect(foreground2, hierarchy2)
        self._raise_for_overlay(
            overlay2, action="continue_registration_email", changed=False
        )
        if screen2 != TikTokScreen.EMAIL_ENTRY or hierarchy2.fingerprint != hierarchy.fingerprint:
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        field2 = self.selectors.resolve(hierarchy2, field_selector)
        control2 = self.selectors.resolve(hierarchy2, continue_selector)
        if hierarchy2.nodes[field2.node_index].text != email:
            raise tiktok_error("TIKTOK_REGISTRATION_EMAIL_MISMATCH")
        if not hierarchy2.nodes[control2.node_index].enabled:
            raise tiktok_error("TIKTOK_REGISTRATION_CONTINUE_DISABLED")
        if (
            control2.node_index != control.node_index
            or control2.bounds != control.bounds
            or control2.method != control.method
            or control2.snapshot_fingerprint != control.snapshot_fingerprint
        ):
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        session.tap_element(control2)
        if on_tap_dispatched is not None:
            on_tap_dispatched(control2)

        deadline = self.monotonic() + self.timeout_seconds
        while True:
            if check_cancelled():
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_foreground = session.get_foreground_app()
            after_hierarchy = session.dump_ui_hierarchy()
            if after_foreground.package_name != expected_package:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_screen = self.screens.classify(
                after_hierarchy, profile, after_foreground.package_name
            )
            changed = after_hierarchy.fingerprint != hierarchy2.fingerprint
            if changed and after_screen != TikTokScreen.EMAIL_ENTRY:
                profile_knows_verification = any(
                    screen.key == TikTokScreen.VERIFICATION_REQUIRED.value
                    and screen.calibrated
                    for screen in profile.screens
                )
                if (
                    profile_knows_verification
                    and after_screen != TikTokScreen.VERIFICATION_REQUIRED
                ):
                    raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
                activity = session.get_foreground_activity()
                return ContinueRegistrationEmailOutcome(
                    screen_before, after_screen, after_foreground.package_name,
                    activity.activity_name, control2.selector_key,
                    control2.method, True, True,
                    after_screen == TikTokScreen.UNKNOWN,
                    len(after_hierarchy.nodes), after_hierarchy.fingerprint,
                )
            if self.monotonic() >= deadline:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            self.sleep(self.poll_interval_seconds)

    def set_post_options(
        self,
        session: TikTokUiActionSession,
        profile: TikTokUiProfileDefinition,
        *,
        expected_package: str,
        privacy: str | None,
        cancelled: Callable[[], bool] | None = None,
        on_tap_dispatched: Callable[[ResolvedUiElement], None] | None = None,
    ) -> SetPostOptionsOutcome:
        """Open and optionally set one server-owned calibrated privacy value."""
        privacy_selectors = {
            "everyone": "privacy_everyone",
            "only_you": "privacy_only_you",
        }
        if privacy is not None and privacy not in privacy_selectors:
            raise tiktok_error("TIKTOK_OPTION_UNSUPPORTED")
        check_cancelled = cancelled or (lambda: False)
        foreground, hierarchy, screen_before = self._observe(
            session, profile, expected_package
        )
        overlay = self.overlays.detect(foreground, hierarchy)
        self._raise_for_overlay(
            overlay, action="set_post_options", changed=False
        )
        if screen_before not in {
            TikTokScreen.READY_TO_PUBLISH, TikTokScreen.POST_SETTINGS,
        }:
            if screen_before == TikTokScreen.UNKNOWN:
                raise tiktok_error("TIKTOK_UNKNOWN_SCREEN")
            raise tiktok_error("TIKTOK_UNEXPECTED_SCREEN")
        selector_map = {item.key: item for item in profile.selectors}
        opened = False
        if screen_before == TikTokScreen.READY_TO_PUBLISH:
            try:
                entry_selector = selector_map["privacy_entry_action"]
            except KeyError as error:
                raise tiktok_error("TIKTOK_ELEMENT_NOT_FOUND") from error
            resolved = self.selectors.resolve(hierarchy, entry_selector)
            if check_cancelled():
                raise tiktok_error("TIKTOK_ACTION_CANCELLED")
            foreground2, hierarchy2, screen2 = self._observe(
                session, profile, expected_package
            )
            if screen2 != screen_before or hierarchy2.fingerprint != hierarchy.fingerprint:
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            resolved2 = self.selectors.resolve(hierarchy2, entry_selector)
            if (
                resolved2.node_index != resolved.node_index
                or resolved2.bounds != resolved.bounds
                or resolved2.method != resolved.method
            ):
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            session.tap_element(resolved2)
            if on_tap_dispatched is not None:
                on_tap_dispatched(resolved2)
            opened = True
            deadline = self.monotonic() + self.timeout_seconds
            while True:
                if check_cancelled():
                    raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
                after_foreground = session.get_foreground_app()
                after_hierarchy = session.dump_ui_hierarchy()
                if after_foreground.package_name != expected_package:
                    raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
                screen_after = self.screens.classify(
                    after_hierarchy, profile, after_foreground.package_name
                )
                if screen_after == TikTokScreen.POST_SETTINGS:
                    hierarchy = after_hierarchy
                    foreground = after_foreground
                    break
                if (
                    after_hierarchy.fingerprint != hierarchy2.fingerprint
                    and screen_after == TikTokScreen.UNKNOWN
                ):
                    return SetPostOptionsOutcome(
                        screen_before, screen_after,
                        after_foreground.package_name, True, True, True,
                        None, False, len(after_hierarchy.nodes),
                        after_hierarchy.fingerprint,
                    )
                if self.monotonic() >= deadline:
                    raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
                self.sleep(self.poll_interval_seconds)

        current_privacy = self._observed_privacy(
            hierarchy, selector_map
        )
        if privacy is None or privacy == current_privacy:
            return SetPostOptionsOutcome(
                screen_before, TikTokScreen.POST_SETTINGS,
                foreground.package_name, False, opened, False,
                current_privacy, current_privacy is not None,
                len(hierarchy.nodes), hierarchy.fingerprint,
            )

        try:
            target_selector = selector_map[privacy_selectors[privacy]]
        except KeyError as error:
            raise tiktok_error("TIKTOK_OPTION_UNSUPPORTED") from error
        target = self.selectors.resolve(hierarchy, target_selector)
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")
        foreground2, hierarchy2, screen2 = self._observe(
            session, profile, expected_package
        )
        if screen2 != TikTokScreen.POST_SETTINGS or hierarchy2.fingerprint != hierarchy.fingerprint:
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        target2 = self.selectors.resolve(hierarchy2, target_selector)
        if target2.node_index != target.node_index or target2.bounds != target.bounds:
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")
        session.tap_element(target2)
        if on_tap_dispatched is not None:
            on_tap_dispatched(target2)
        deadline = self.monotonic() + self.timeout_seconds
        while True:
            if check_cancelled():
                raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
            after_foreground, after_hierarchy, screen_after = self._observe(
                session, profile, expected_package
            )
            if (
                screen_after == TikTokScreen.POST_SETTINGS
                and self._observed_privacy(after_hierarchy, selector_map) == privacy
            ):
                return SetPostOptionsOutcome(
                    screen_before, screen_after, after_foreground.package_name,
                    True, True, False, privacy, True,
                    len(after_hierarchy.nodes), after_hierarchy.fingerprint,
                )
            if (
                screen_after == TikTokScreen.READY_TO_PUBLISH
                and self._observed_privacy_summary(
                    after_hierarchy, selector_map
                ) == privacy
            ):
                return SetPostOptionsOutcome(
                    screen_before, screen_after, after_foreground.package_name,
                    True, True, False, privacy, True,
                    len(after_hierarchy.nodes), after_hierarchy.fingerprint,
                )
            if self.monotonic() >= deadline:
                raise tiktok_error("TIKTOK_OPTION_VERIFICATION_FAILED")
            self.sleep(self.poll_interval_seconds)

    def prepare_publish(
        self,
        session: TikTokUiActionSession,
        profile: TikTokUiProfileDefinition,
        *,
        expected_package: str,
        expected_media: AdbMediaRecord,
        expected_caption: str,
        expected_privacy: str,
        cancelled: Callable[[], bool] | None = None,
    ) -> PreparePublishOutcome:
        """Verify an unchanged final pre-publish state without UI mutation."""
        requested_caption = normalize_caption(expected_caption)
        if expected_privacy not in {"everyone", "only_you"}:
            raise tiktok_error("TIKTOK_OPTION_UNSUPPORTED")
        check_cancelled = cancelled or (lambda: False)
        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")

        foreground = session.get_foreground_app()
        hierarchy = session.dump_ui_hierarchy()
        self._raise_for_overlay(
            self.overlays.detect(foreground, hierarchy),
            action="prepare_publish", changed=False,
        )
        if foreground.package_name != expected_package:
            raise tiktok_error("TIKTOK_APP_NOT_FOREGROUND")
        screen = self.screens.classify(
            hierarchy, profile, foreground.package_name
        )
        if screen != TikTokScreen.READY_TO_PUBLISH:
            if screen == TikTokScreen.UNKNOWN:
                raise tiktok_error("TIKTOK_UNKNOWN_SCREEN")
            raise tiktok_error("TIKTOK_UNEXPECTED_SCREEN")
        selector_map = {item.key: item for item in profile.selectors}
        self._verify_prepared_hierarchy(
            hierarchy, selector_map,
            expected_caption=requested_caption,
            expected_privacy=expected_privacy,
        )
        media_method = self.media.verify_inventory(
            expected=expected_media,
            media_inventory=session.get_media_inventory(),
        )

        if check_cancelled():
            raise tiktok_error("TIKTOK_ACTION_CANCELLED")
        foreground2 = session.get_foreground_app()
        hierarchy2 = session.dump_ui_hierarchy()
        self._raise_for_overlay(
            self.overlays.detect(foreground2, hierarchy2),
            action="prepare_publish", changed=False,
        )
        if foreground2.package_name != expected_package:
            raise tiktok_error("TIKTOK_APP_NOT_FOREGROUND")
        screen2 = self.screens.classify(
            hierarchy2, profile, foreground2.package_name
        )
        if (
            screen2 != TikTokScreen.READY_TO_PUBLISH
            or hierarchy2.fingerprint != hierarchy.fingerprint
        ):
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        self._verify_prepared_hierarchy(
            hierarchy2, selector_map,
            expected_caption=requested_caption,
            expected_privacy=expected_privacy,
        )
        media_method2 = self.media.verify_inventory(
            expected=expected_media,
            media_inventory=session.get_media_inventory(),
        )
        if media_method2 != media_method:
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        return PreparePublishOutcome(
            screen2, foreground2.package_name, expected_privacy,
            media_method, len(hierarchy2.nodes), hierarchy2.fingerprint,
        )

    def _verify_prepared_hierarchy(
        self, hierarchy, selector_map, *,
        expected_caption: str, expected_privacy: str,
    ) -> None:
        caption_selector = selector_map.get("caption_input")
        post_selector = selector_map.get("publish_action")
        drafts_selector = selector_map.get("draft_action")
        if caption_selector is None or post_selector is None or drafts_selector is None:
            raise tiktok_error("TIKTOK_UI_PROFILE_MISMATCH")
        caption = self.selectors.resolve(hierarchy, caption_selector)
        try:
            self.selectors.resolve(hierarchy, post_selector)
            self.selectors.resolve(hierarchy, drafts_selector)
        except TikTokActionError as error:
            if error.code in {"TIKTOK_ELEMENT_NOT_FOUND", "TIKTOK_ELEMENT_AMBIGUOUS"}:
                raise tiktok_error("TIKTOK_PREPARE_CONTROLS_INVALID") from error
            raise
        observed_caption = hierarchy.nodes[caption.node_index].text
        try:
            normalized_caption = normalize_caption(observed_caption)
        except TikTokActionError as error:
            raise tiktok_error("TIKTOK_PREPARE_CAPTION_MISMATCH") from error
        if normalized_caption != expected_caption or observed_caption != expected_caption:
            raise tiktok_error("TIKTOK_PREPARE_CAPTION_MISMATCH")
        observed_privacy = self._observed_privacy_summary(hierarchy, selector_map)
        if observed_privacy != expected_privacy:
            raise tiktok_error("TIKTOK_PREPARE_PRIVACY_MISMATCH")

    def _observed_privacy(self, hierarchy, selector_map) -> str | None:
        observed = []
        for value, key in (
            ("everyone", "privacy_everyone"),
            ("only_you", "privacy_only_you"),
        ):
            selector = selector_map.get(key)
            if selector is None:
                continue
            try:
                resolved = self.selectors.resolve(hierarchy, selector)
            except TikTokActionError:
                continue
            node = hierarchy.nodes[resolved.node_index]
            descendants = list(node.child_indexes)
            checked = node.checked
            while descendants:
                child = hierarchy.nodes[descendants.pop()]
                checked = checked or child.checked
                descendants.extend(child.child_indexes)
            if checked:
                observed.append(value)
        return observed[0] if len(observed) == 1 else None

    def _observed_privacy_summary(self, hierarchy, selector_map) -> str | None:
        observed = []
        for value, key in (
            ("everyone", "privacy_summary_everyone"),
            ("only_you", "privacy_summary_only_you"),
        ):
            selector = selector_map.get(key)
            if selector is None:
                continue
            try:
                self.selectors.resolve(hierarchy, selector)
            except TikTokActionError:
                continue
            observed.append(value)
        return observed[0] if len(observed) == 1 else None

    @staticmethod
    def _raise_for_overlay(overlay, *, action: str, changed: bool) -> None:
        if overlay.overlay == TikTokOverlay.ANDROID_PERMISSION_PROMPT:
            raise tiktok_error(
                "TIKTOK_PERMISSION_REQUIRED",
                safe_metadata={
                    "overlay": overlay.overlay.value,
                    "permission_kind": overlay.permission_kind,
                    "action": action,
                    "changed": changed,
                },
            )
        if overlay.overlay != TikTokOverlay.NONE:
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")

    def _observe(
        self,
        session: TikTokUiActionSession,
        profile: TikTokUiProfileDefinition,
        expected_package: str,
    ) -> tuple[AdbForegroundApp, UiHierarchy, TikTokScreen]:
        foreground = session.get_foreground_app()
        if foreground.package_name != expected_package:
            raise tiktok_error("TIKTOK_APP_NOT_FOREGROUND")
        hierarchy = session.dump_ui_hierarchy()
        screen = self.screens.classify(
            hierarchy, profile, foreground.package_name
        )
        return foreground, hierarchy, screen
