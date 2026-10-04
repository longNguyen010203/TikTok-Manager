"""Stable, sanitized errors for Android automation services."""

from __future__ import annotations


class AutomationError(RuntimeError):
    """An API-safe automation failure with stable retry semantics."""

    def __init__(self, code: str, safe_message: str, *, retryable: bool) -> None:
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable
        super().__init__(safe_message)


def automation_error(code: str, *, retryable: bool = False) -> AutomationError:
    messages = {
        "RUNTIME_NOT_FOUND": "Runtime was not found",
        "RUNTIME_STOPPED": "Runtime is stopped",
        "RUNTIME_DEPROVISIONING": "Runtime is being deprovisioned",
        "RUNTIME_BUSY": "Runtime is busy with another operation",
        "RUNTIME_SCREEN_ACTIVE": "Runtime has an active screen session",
        "DEVICE_NOT_READY": "Android device is not ready",
        "ADB_UNAVAILABLE": "ADB is unavailable for the Runtime",
        "ADB_COMMAND_FAILED": "ADB automation command failed",
        "AUTOMATION_TIMEOUT": "Android automation operation timed out",
        "PACKAGE_NOT_FOUND": "Android package was not found",
        "INVALID_AUTOMATION_PAYLOAD": "Automation input is invalid",
        "FILE_TRANSFER_FAILED": "Android file transfer failed",
        "MEDIA_IMPORT_FAILED": "Android media import failed",
        "ARTIFACT_NOT_FOUND": "Managed artifact was not found",
        "ARTIFACT_POLICY_VIOLATION": "Managed artifact policy rejected the operation",
        "ARTIFACT_STORAGE_FULL": "Managed artifact storage quota is full",
        "AUTOMATION_CANCELLED": "Android automation operation was cancelled",
    }
    return AutomationError(code, messages[code], retryable=retryable)
