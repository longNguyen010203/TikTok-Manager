"""Stable, sanitized failures for the TikTok UI action layer."""

from dataclasses import dataclass


_MESSAGES = {
    "TIKTOK_APP_NOT_FOREGROUND": "The managed app is not in the foreground.",
    "TIKTOK_UNKNOWN_SCREEN": "The current app screen is not recognized.",
    "TIKTOK_ELEMENT_NOT_FOUND": "The required app element was not found.",
    "TIKTOK_ELEMENT_AMBIGUOUS": "The required app element was ambiguous.",
    "TIKTOK_UI_DUMP_INVALID": "The Android UI hierarchy was invalid.",
    "TIKTOK_UI_PROFILE_NOT_FOUND": "No UI profile is configured for this managed app.",
    "TIKTOK_UI_PROFILE_MISMATCH": "The installed app version is not supported by the pinned UI profile.",
    "TIKTOK_SCREEN_TIMEOUT": "The expected app screen did not appear in time.",
    "TIKTOK_ACTION_CANCELLED": "The app action was cancelled.",
    "TIKTOK_UI_STATE_UNCERTAIN": "The app UI changed before the action could be applied.",
    "TIKTOK_TEXT_UNSUPPORTED": "The requested text cannot be entered safely.",
}


@dataclass(eq=False)
class TikTokActionError(RuntimeError):
    code: str
    retryable: bool = False
    safe_message: str = ""

    def __post_init__(self) -> None:
        if not self.safe_message:
            self.safe_message = _MESSAGES.get(self.code, "The app action failed.")
        RuntimeError.__init__(self, self.safe_message)


def tiktok_error(code: str, *, retryable: bool = False) -> TikTokActionError:
    return TikTokActionError(code, retryable)
