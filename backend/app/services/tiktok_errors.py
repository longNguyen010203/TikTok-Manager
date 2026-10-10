"""Stable, sanitized failures for the TikTok UI action layer."""

from dataclasses import dataclass, field
from typing import Any


_MESSAGES = {
    "TIKTOK_APP_NOT_FOREGROUND": "The managed app is not in the foreground.",
    "TIKTOK_UNKNOWN_SCREEN": "The current app screen is not recognized.",
    "TIKTOK_ELEMENT_NOT_FOUND": "The required app element was not found.",
    "TIKTOK_ELEMENT_AMBIGUOUS": "The required app element was ambiguous.",
    "TIKTOK_UI_DUMP_INVALID": "The Android UI hierarchy was invalid.",
    "TIKTOK_UI_PROFILE_NOT_FOUND": "No UI profile is configured for this managed app.",
    "TIKTOK_UI_PROFILE_MISMATCH": "The installed app version is not supported by the pinned UI profile.",
    "TIKTOK_SCREEN_TIMEOUT": "The expected app screen did not appear in time.",
    "TIKTOK_UNEXPECTED_SCREEN": "The app reached an unexpected screen.",
    "TIKTOK_ACTION_CANCELLED": "The app action was cancelled.",
    "TIKTOK_UI_STATE_UNCERTAIN": "The app UI changed before the action could be applied.",
    "TIKTOK_PERMISSION_REQUIRED": "Android permission approval is required before the app action can continue.",
    "TIKTOK_MEDIA_NOT_FOUND": "The delivered media is not visible in the app picker.",
    "TIKTOK_MEDIA_AMBIGUOUS": "The delivered media cannot be identified uniquely in the app picker.",
    "TIKTOK_MEDIA_DELIVERY_INVALID": "The content delivery is not eligible for app selection.",
    "TIKTOK_TEXT_UNSUPPORTED": "The requested text cannot be entered safely.",
    "TIKTOK_CAPTION_INVALID": "The caption does not satisfy the supported text policy.",
    "TIKTOK_CAPTION_VERIFICATION_FAILED": "The caption field could not be verified after entry.",
    "TIKTOK_KEYBOARD_UNAVAILABLE": "The Android keyboard state could not be verified.",
    "TIKTOK_ACCOUNT_NOT_FOUND": "The bound Account was not found.",
    "TIKTOK_ACCOUNT_EMAIL_REQUIRED": "The bound Account does not have a valid email.",
    "TIKTOK_ACCOUNT_RUNTIME_MISMATCH": "The Account is not assigned to the target Runtime.",
    "TIKTOK_EMAIL_VERIFICATION_FAILED": "The registration email field could not be verified after entry.",
    "TIKTOK_REGISTRATION_EMAIL_MISMATCH": "The registration email does not match the bound Account.",
    "TIKTOK_REGISTRATION_CONTINUE_DISABLED": "The registration Continue control is not enabled.",
    "TIKTOK_OPTION_UNSUPPORTED": "The requested post option is not supported by this UI profile.",
    "TIKTOK_OPTION_VERIFICATION_FAILED": "The post option could not be verified after the change.",
    "TIKTOK_PREPARE_CAPTION_MISMATCH": "The prepared caption does not match the expected caption.",
    "TIKTOK_PREPARE_PRIVACY_MISMATCH": "The prepared privacy does not match the expected privacy.",
    "TIKTOK_PREPARE_CONTROLS_INVALID": "The final publishing controls could not be verified safely.",
}


@dataclass(eq=False)
class TikTokActionError(RuntimeError):
    code: str
    retryable: bool = False
    safe_message: str = ""
    safe_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.safe_message:
            self.safe_message = _MESSAGES.get(self.code, "The app action failed.")
        RuntimeError.__init__(self, self.safe_message)


def tiktok_error(
    code: str, *, retryable: bool = False,
    safe_metadata: dict[str, Any] | None = None,
) -> TikTokActionError:
    return TikTokActionError(code, retryable, safe_metadata=safe_metadata or {})
