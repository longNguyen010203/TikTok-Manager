"""Desired-state foundation for per-Runtime networking."""

from __future__ import annotations

import re
import socket
import uuid
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Runtime, RuntimeNetworkConfig, RuntimeNetworkConfigRevision, RuntimeNetworkState
from app.models.runtime_network import BRIDGE_STATUSES, NETWORK_STATUSES, OBSERVED_NETWORK_MODES
from app.models.timestamps import utc_now
from app.services.network_config import RuntimeNetworkSettings
from app.services.network_operation_lock import RuntimeNetworkOperationGuard
from app.services.network_validation import (
    NetworkValidationError,
    validate_host,
    validate_optional_secret_reference,
    validate_port,
)


class RuntimeNetworkError(RuntimeError):
    """Base desired-state service error."""


class RuntimeNetworkNotFoundError(RuntimeNetworkError):
    """Raised when the target Runtime does not exist."""


class RuntimeNetworkRevisionConflict(RuntimeNetworkError):
    """Raised when optimistic revision matching fails."""


class RuntimeNetworkCleanupRequired(RuntimeNetworkError):
    """Raised when direct mode would release resources before cleanup."""


class BridgePortUnavailable(RuntimeNetworkError):
    """Raised when no configured loopback bridge port can be reserved."""


@dataclass(frozen=True)
class DesiredNetworkInput:
    mode: str
    proxy_host: str | None = None
    proxy_port: int | None = None
    proxy_username_secret_ref: str | None = None
    proxy_password_secret_ref: str | None = None
    bridge_device_port: int | None = None

    def validated(self, default_device_port: int) -> "DesiredNetworkInput":
        if self.mode == "direct":
            if any(
                value is not None
                for value in (
                    self.proxy_host,
                    self.proxy_port,
                    self.proxy_username_secret_ref,
                    self.proxy_password_secret_ref,
                    self.bridge_device_port,
                )
            ):
                raise NetworkValidationError("direct mode does not accept proxy or bridge fields")
            return self
        if self.mode != "http_proxy":
            raise NetworkValidationError("mode must be direct or http_proxy")
        if self.proxy_host is None or self.proxy_port is None:
            raise NetworkValidationError("http_proxy mode requires proxy_host and proxy_port")
        return DesiredNetworkInput(
            mode=self.mode,
            proxy_host=validate_host(self.proxy_host),
            proxy_port=validate_port(self.proxy_port, "proxy_port"),
            proxy_username_secret_ref=validate_optional_secret_reference(self.proxy_username_secret_ref),
            proxy_password_secret_ref=validate_optional_secret_reference(self.proxy_password_secret_ref),
            bridge_device_port=validate_port(self.bridge_device_port or default_device_port, "bridge_device_port"),
        )


@dataclass(frozen=True)
class DesiredNetworkView:
    """API-safe desired view containing no secret references."""

    runtime_id: int
    managed: bool
    mode: str
    proxy_host: str | None
    proxy_port: int | None
    bridge_host_port: int | None
    bridge_device_port: int | None
    desired_revision: int
    username_configured: bool
    password_configured: bool

    @classmethod
    def unmanaged(cls, runtime_id: int) -> "DesiredNetworkView":
        return cls(runtime_id, False, "direct", None, None, None, None, 0, False, False)

    @classmethod
    def from_model(cls, config: RuntimeNetworkConfig) -> "DesiredNetworkView":
        return cls(
            runtime_id=config.runtime_id,
            managed=True,
            mode=config.mode,
            proxy_host=config.proxy_host,
            proxy_port=config.proxy_port,
            bridge_host_port=config.bridge_host_port,
            bridge_device_port=config.bridge_device_port,
            desired_revision=config.desired_revision,
            username_configured=config.proxy_username_secret_ref is not None,
            password_configured=config.proxy_password_secret_ref is not None,
        )


PortProbe = Callable[[str, int], bool]


class BridgePortAllocator:
    """Allocate a durable unique port while holding a host-wide flock."""

    def __init__(
        self,
        settings: RuntimeNetworkSettings,
        guard: RuntimeNetworkOperationGuard,
        port_probe: PortProbe | None = None,
    ) -> None:
        self.settings = settings
        self.guard = guard
        self.port_probe = port_probe or self._port_is_available

    def allocate(self, session: Session, runtime_id: int) -> int:
        with self.guard.acquire_allocation():
            allocated = set(
                session.scalars(
                    select(RuntimeNetworkConfig.bridge_host_port).where(
                        RuntimeNetworkConfig.bridge_host_port.is_not(None),
                        RuntimeNetworkConfig.runtime_id != runtime_id,
                    )
                ).all()
            )
            reserved_history = session.scalars(
                select(RuntimeNetworkConfigRevision.bridge_host_port)
                .join(
                    RuntimeNetworkState,
                    RuntimeNetworkState.runtime_id
                    == RuntimeNetworkConfigRevision.runtime_id,
                )
                .where(
                    RuntimeNetworkState.bridge_owner_token.is_not(None),
                    RuntimeNetworkConfigRevision.bridge_host_port.is_not(None),
                    RuntimeNetworkConfigRevision.runtime_id != runtime_id,
                )
            ).all()
            allocated.update(reserved_history)
            for port in range(self.settings.bridge_port_start, self.settings.bridge_port_end + 1):
                if port in allocated:
                    continue
                if self.port_probe("127.0.0.1", port):
                    return port
        raise BridgePortUnavailable("No host bridge port is available in the configured range")

    @staticmethod
    def _port_is_available(host: str, port: int) -> bool:
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        try:
            with socket.socket(family, socket.SOCK_STREAM) as candidate:
                candidate.bind((host, port))
        except OSError:
            return False
        return True


class RuntimeNetworkService:
    """Persist versioned desired state without applying it to Android or bridges."""

    def __init__(
        self,
        session: Session,
        *,
        settings: RuntimeNetworkSettings,
        guard: RuntimeNetworkOperationGuard | None = None,
        port_allocator: BridgePortAllocator | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.guard = guard or RuntimeNetworkOperationGuard(settings.lock_directory)
        self.port_allocator = port_allocator or BridgePortAllocator(settings, self.guard)

    def read_desired(self, runtime_id: int) -> DesiredNetworkView:
        self._require_runtime(runtime_id)
        config = self.session.scalar(
            select(RuntimeNetworkConfig).where(RuntimeNetworkConfig.runtime_id == runtime_id)
        )
        return DesiredNetworkView.unmanaged(runtime_id) if config is None else DesiredNetworkView.from_model(config)

    def create_or_update_desired(
        self,
        runtime_id: int,
        desired: DesiredNetworkInput,
        *,
        expected_revision: int,
    ) -> DesiredNetworkView:
        return self._write_desired(
            runtime_id,
            desired,
            expected_revision=expected_revision,
            cleanup_complete=False,
        )

    def switch_to_direct(
        self,
        runtime_id: int,
        *,
        expected_revision: int,
        cleanup_complete: bool,
    ) -> DesiredNetworkView:
        return self._write_desired(
            runtime_id,
            DesiredNetworkInput(mode="direct"),
            expected_revision=expected_revision,
            cleanup_complete=cleanup_complete,
        )

    def has_revision_mismatch(self, runtime_id: int) -> bool:
        config = self.session.scalar(select(RuntimeNetworkConfig).where(RuntimeNetworkConfig.runtime_id == runtime_id))
        if config is None:
            return False
        state = self.session.get(RuntimeNetworkState, runtime_id)
        return state is None or state.applied_revision != config.desired_revision

    def update_observed_state(
        self,
        runtime_id: int,
        *,
        desired_revision: int,
        status: str,
        applied_revision: int | None = None,
        observed_mode: str = "unknown",
        observed_android_proxy_host: str | None = None,
        observed_android_proxy_port: int | None = None,
        reverse_present: bool | None = None,
        bridge_status: str = "unknown",
        error_code: str | None = None,
        error_message: str | None = None,
        verified: bool = False,
    ) -> RuntimeNetworkState:
        """Persist a controlled observed snapshot for the current revision."""
        if status not in NETWORK_STATUSES:
            raise NetworkValidationError("Unsupported network status")
        if observed_mode not in OBSERVED_NETWORK_MODES:
            raise NetworkValidationError("Unsupported observed network mode")
        if bridge_status not in BRIDGE_STATUSES:
            raise NetworkValidationError("Unsupported bridge status")
        if observed_android_proxy_host is not None:
            validate_host(observed_android_proxy_host)
        if observed_android_proxy_port is not None:
            validate_port(observed_android_proxy_port, "observed_android_proxy_port")
        if applied_revision is not None and applied_revision <= 0:
            raise NetworkValidationError("applied_revision must be positive")
        if error_code is not None and (
            len(error_code) > 100
            or re.fullmatch(r"[A-Z][A-Z0-9_]*", error_code) is None
        ):
            raise NetworkValidationError(
                "error_code must be a stable uppercase identifier"
            )

        with self.guard.acquire_runtime(runtime_id):
            config = self.session.scalar(
                select(RuntimeNetworkConfig).where(
                    RuntimeNetworkConfig.runtime_id == runtime_id
                )
            )
            if config is None:
                raise RuntimeNetworkNotFoundError(
                    "Runtime network configuration not found"
                )
            if config.desired_revision != desired_revision:
                raise RuntimeNetworkRevisionConflict(
                    "Desired network revision has changed"
                )
            state = self.session.get(RuntimeNetworkState, runtime_id)
            if state is None:
                state = RuntimeNetworkState(
                    runtime_id=runtime_id,
                    status=status,
                    desired_revision=desired_revision,
                    observed_mode=observed_mode,
                    bridge_status=bridge_status,
                )
                self.session.add(state)
            state.status = status
            state.desired_revision = desired_revision
            state.applied_revision = applied_revision
            state.observed_mode = observed_mode
            state.observed_android_proxy_host = observed_android_proxy_host
            state.observed_android_proxy_port = observed_android_proxy_port
            state.reverse_present = reverse_present
            state.bridge_status = bridge_status
            state.error_code = error_code
            state.error_message = _sanitize_error_message(error_message)
            if verified:
                state.last_verified_at = utc_now()
            self.session.commit()
            self.session.refresh(state)
            return state

    def _write_desired(
        self,
        runtime_id: int,
        desired: DesiredNetworkInput,
        *,
        expected_revision: int,
        cleanup_complete: bool,
    ) -> DesiredNetworkView:
        validated = desired.validated(self.settings.bridge_device_port)
        with self.guard.acquire_runtime(runtime_id):
            try:
                runtime = self._require_runtime(runtime_id)
                config = self.session.scalar(
                    select(RuntimeNetworkConfig).where(RuntimeNetworkConfig.runtime_id == runtime_id)
                )
                current_revision = 0 if config is None else config.desired_revision
                if expected_revision != current_revision:
                    raise RuntimeNetworkRevisionConflict("Desired network revision has changed")
                if validated.mode == "http_proxy":
                    self._require_network_capable_runtime(runtime)
                    bridge_host_port = (
                        config.bridge_host_port
                        if config is not None and config.mode == "http_proxy"
                        else self.port_allocator.allocate(self.session, runtime_id)
                    )
                else:
                    bridge_host_port = None

                revision = current_revision + 1
                cleanup_required = (
                    config is not None
                    and config.mode == "http_proxy"
                    and not cleanup_complete
                )
                values = self._desired_values(validated, bridge_host_port)
                if config is None:
                    config = RuntimeNetworkConfig(runtime_id=runtime_id, desired_revision=revision, **values)
                    self.session.add(config)
                else:
                    for field, value in values.items():
                        setattr(config, field, value)
                    config.desired_revision = revision

                self.session.add(
                    RuntimeNetworkConfigRevision(
                        runtime_id=runtime_id,
                        revision=revision,
                        **values,
                    )
                )
                self._update_state_for_desired(
                    runtime,
                    validated.mode,
                    revision,
                    cleanup_complete,
                    cleanup_required,
                )
                self.session.commit()
                self.session.refresh(config)
                return DesiredNetworkView.from_model(config)
            except (RuntimeNetworkError, NetworkValidationError):
                self.session.rollback()
                raise
            except IntegrityError as error:
                self.session.rollback()
                raise RuntimeNetworkError("Network configuration conflicts with an existing allocation") from error

    def _update_state_for_desired(
        self,
        runtime: Runtime,
        mode: str,
        revision: int,
        cleanup_complete: bool,
        cleanup_required: bool,
    ) -> None:
        state = self.session.get(RuntimeNetworkState, runtime.id)
        if state is None:
            state = RuntimeNetworkState(
                runtime_id=runtime.id,
                status=(
                    "pending"
                    if mode == "http_proxy" or cleanup_required
                    else "disabled"
                ),
                desired_revision=revision,
                applied_revision=None,
                observed_mode="unknown",
                bridge_status="stopped",
                bridge_owner_token=str(uuid.uuid4()) if mode == "http_proxy" else None,
            )
            self.session.add(state)
        else:
            state.desired_revision = revision
            state.status = (
                "pending"
                if mode == "http_proxy" or cleanup_required
                else "disabled"
            )
            state.error_code = None
            state.error_message = None
            if mode == "http_proxy" and state.bridge_owner_token is None:
                state.bridge_owner_token = str(uuid.uuid4())
        if mode == "direct" and cleanup_complete:
            now = utc_now()
            state.applied_revision = revision
            state.observed_mode = "direct"
            state.observed_android_proxy_host = None
            state.observed_android_proxy_port = None
            state.reverse_present = False
            state.bridge_status = "stopped"
            state.bridge_owner_token = None
            state.bridge_supervisor_id = None
            state.bridge_pid = None
            state.bridge_process_start_token = None
            state.last_applied_at = now
            state.last_verified_at = now

    @staticmethod
    def _desired_values(desired: DesiredNetworkInput, bridge_host_port: int | None) -> dict[str, object]:
        return {
            "mode": desired.mode,
            "proxy_host": desired.proxy_host,
            "proxy_port": desired.proxy_port,
            "proxy_username_secret_ref": desired.proxy_username_secret_ref,
            "proxy_password_secret_ref": desired.proxy_password_secret_ref,
            "bridge_host_port": bridge_host_port,
            "bridge_device_port": desired.bridge_device_port,
        }

    def _require_runtime(self, runtime_id: int) -> Runtime:
        runtime = self.session.get(Runtime, runtime_id)
        if runtime is None:
            raise RuntimeNetworkNotFoundError("Runtime not found")
        return runtime

    @staticmethod
    def _require_network_capable_runtime(runtime: Runtime) -> None:
        if runtime.runtime_type != "redroid":
            raise NetworkValidationError("HTTP proxy configuration requires a Redroid Runtime")
        if not runtime.adb_serial:
            raise NetworkValidationError("HTTP proxy configuration requires an ADB serial")


def add_default_direct_network_config(
    session: Session,
    runtime: Runtime,
    *,
    applied: bool = False,
) -> RuntimeNetworkConfig:
    """Add an uncommitted direct/disabled foundation to a provisioning transaction."""
    if runtime.id is None:
        session.flush()
    config = RuntimeNetworkConfig(runtime_id=runtime.id, mode="direct", desired_revision=1)
    session.add_all(
        [
            config,
            RuntimeNetworkConfigRevision(runtime_id=runtime.id, revision=1, mode="direct"),
            RuntimeNetworkState(
                runtime_id=runtime.id,
                status="disabled",
                desired_revision=1,
                applied_revision=1 if applied else None,
                observed_mode="direct" if applied else "unknown",
                bridge_status="stopped",
            ),
        ]
    )
    return config


_SECRET_REFERENCE_IN_TEXT = re.compile(r"env:TIKTOK_PROXY_[A-Z0-9_]+")
_URL_USERINFO = re.compile(r"(://)[^/@\s]+@")


def _sanitize_error_message(message: str | None) -> str | None:
    if message is None:
        return None
    safe = "".join(
        character if character.isprintable() else " " for character in message
    )
    safe = _SECRET_REFERENCE_IN_TEXT.sub("[REDACTED_SECRET_REFERENCE]", safe)
    safe = _URL_USERINFO.sub(r"\1[REDACTED]@", safe)
    return safe[:1000]
