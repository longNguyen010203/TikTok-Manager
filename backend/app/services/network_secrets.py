"""Secret reference validation and resolution without value disclosure."""

from __future__ import annotations

import os
import re


_ENV_REFERENCE = re.compile(r"^env:TIKTOK_PROXY_[A-Z0-9_]{1,220}$")


class SecretResolutionError(ValueError):
    """Raised without including a reference or resolved value."""


class SecretValue:
    """A resolved secret whose ordinary string representations are redacted."""

    __slots__ = ("__value",)

    def __init__(self, value: str) -> None:
        self.__value = value

    def reveal(self) -> str:
        """Return the value only at the explicit bridge-adapter boundary."""
        return self.__value

    def __repr__(self) -> str:
        return "<SecretValue redacted>"

    def __str__(self) -> str:
        return "[REDACTED]"


def validate_secret_reference(reference: str) -> str:
    if not _ENV_REFERENCE.fullmatch(reference):
        raise SecretResolutionError("Secret reference is not an allowed proxy environment reference")
    return reference


class SecretResolver:
    """Resolve allowlisted environment references into redacted wrappers."""

    def resolve(self, reference: str) -> SecretValue:
        validate_secret_reference(reference)
        variable_name = reference.removeprefix("env:")
        value = os.getenv(variable_name)
        if value is None or value == "":
            raise SecretResolutionError("Configured proxy secret is unavailable")
        return SecretValue(value)

