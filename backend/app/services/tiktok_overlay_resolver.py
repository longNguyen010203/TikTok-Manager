"""Recognize system/app overlays independently from TikTok screen state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.adb_executor import AdbForegroundApp
from app.services.android_ui_hierarchy import UiHierarchy


class TikTokOverlay(str, Enum):
    NONE = "NONE"
    ANDROID_PERMISSION_PROMPT = "ANDROID_PERMISSION_PROMPT"
    KEYBOARD = "KEYBOARD"
    DISCARD_CONFIRMATION = "DISCARD_CONFIRMATION"
    BLOCKING_MODAL = "BLOCKING_MODAL"
    UNKNOWN_OVERLAY = "UNKNOWN_OVERLAY"


@dataclass(frozen=True)
class OverlayObservation:
    overlay: TikTokOverlay
    permission_kind: str | None = None


class TikTokOverlayResolver:
    """Resolve only strongly evidenced overlays; never act on their controls."""

    _PERMISSION_PACKAGES = frozenset({
        "com.android.permissioncontroller",
        "com.google.android.permissioncontroller",
    })
    _DIALOG_IDS = frozenset({
        "com.android.permissioncontroller:id/grant_singleton",
        "com.android.permissioncontroller:id/grant_dialog",
        "com.google.android.permissioncontroller:id/grant_singleton",
        "com.google.android.permissioncontroller:id/grant_dialog",
    })
    _BUTTON_IDS = frozenset({
        # Android 11 permission controller, observed on Runtime 17 when the
        # TikTok media picker first requested photos/media access.
        "com.android.permissioncontroller:id/permission_allow_button",
        "com.android.permissioncontroller:id/permission_deny_button",
        "com.android.permissioncontroller:id/permission_allow_foreground_only_button",
        "com.android.permissioncontroller:id/permission_allow_one_time_button",
        "com.android.permissioncontroller:id/permission_deny_and_dont_ask_again_button",
        "com.google.android.permissioncontroller:id/permission_allow_button",
        "com.google.android.permissioncontroller:id/permission_deny_button",
        "com.google.android.permissioncontroller:id/permission_allow_foreground_only_button",
        "com.google.android.permissioncontroller:id/permission_allow_one_time_button",
        "com.google.android.permissioncontroller:id/permission_deny_and_dont_ask_again_button",
    })
    _MESSAGE_IDS = frozenset({
        "com.android.permissioncontroller:id/permission_message",
        "com.google.android.permissioncontroller:id/permission_message",
    })
    # Android's one-time immersive-mode education overlay was observed on the
    # fresh TIK-026 Runtime before TikTok's own hierarchy became visible.  It
    # is recognized only so state-driven actions stop safely; this service
    # deliberately has no policy for activating its acknowledgement button.
    _IMMERSIVE_CLING_REQUIRED_IDS = frozenset({
        "android:id/immersive_cling_chevron",
        "android:id/immersive_cling_title",
        "android:id/immersive_cling_description",
        "android:id/ok",
    })

    def detect(
        self, foreground: AdbForegroundApp, hierarchy: UiHierarchy
    ) -> OverlayObservation:
        package = foreground.package_name
        node_packages = {node.package for node in hierarchy.nodes if node.package}
        resource_ids = {node.resource_id for node in hierarchy.nodes if node.resource_id}
        if (
            package in self._PERMISSION_PACKAGES
            and package in node_packages
            and bool(resource_ids & self._DIALOG_IDS)
            and bool(resource_ids & self._BUTTON_IDS)
        ):
            return OverlayObservation(
                TikTokOverlay.ANDROID_PERMISSION_PROMPT,
                self._permission_kind(hierarchy),
            )
        if package in self._PERMISSION_PACKAGES:
            return OverlayObservation(TikTokOverlay.UNKNOWN_OVERLAY)
        node_packages = {node.package for node in hierarchy.nodes if node.package}
        if (
            "android" in node_packages
            and self._IMMERSIVE_CLING_REQUIRED_IDS.issubset(resource_ids)
            and any(
                node.resource_id == "android:id/ok"
                and node.class_name == "android.widget.Button"
                and node.enabled
                and node.clickable
                for node in hierarchy.nodes
            )
        ):
            return OverlayObservation(TikTokOverlay.BLOCKING_MODAL)
        return OverlayObservation(TikTokOverlay.NONE)

    def _permission_kind(self, hierarchy: UiHierarchy) -> str | None:
        messages = " ".join(
            node.text.casefold()
            for node in hierarchy.nodes
            if node.resource_id in self._MESSAGE_IDS
        )
        if "pictures" in messages and "record video" in messages:
            return "camera"
        if "microphone" in messages or "record audio" in messages:
            return "microphone"
        if "photos" in messages or "videos" in messages:
            return "media"
        return None
