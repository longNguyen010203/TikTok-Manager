"""Validation shared by network desired-state and adapter boundaries."""

from __future__ import annotations

import ipaddress
import re

from app.services.network_secrets import validate_secret_reference


_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_ADB_SERIAL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")


class NetworkValidationError(ValueError):
    """Raised when desired network input is invalid."""


def validate_port(port: int, field: str) -> int:
    if isinstance(port, bool) or not 1 <= port <= 65535:
        raise NetworkValidationError(f"{field} must be between 1 and 65535")
    return port


def validate_host(host: str) -> str:
    if not host or len(host) > 253 or host != host.strip():
        raise NetworkValidationError("proxy_host must be a valid hostname or IP address")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    normalized = host[:-1] if host.endswith(".") else host
    if not normalized or any(not _HOST_LABEL.fullmatch(label) for label in normalized.split(".")):
        raise NetworkValidationError("proxy_host must be a valid hostname or IP address")
    return host


def validate_adb_serial(adb_serial: str) -> str:
    if not _ADB_SERIAL.fullmatch(adb_serial):
        raise NetworkValidationError("adb_serial contains unsupported characters")
    return adb_serial


def validate_optional_secret_reference(reference: str | None) -> str | None:
    if reference is not None:
        validate_secret_reference(reference)
    return reference

