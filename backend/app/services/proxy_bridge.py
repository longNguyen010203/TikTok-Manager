"""Host proxy bridge boundary; Phase 2 includes no real process launcher."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from app.services.network_secrets import SecretValue
from app.services.network_validation import validate_host, validate_port


_ADAPTER_TYPE = re.compile(r"^[a-z][a-z0-9_-]{0,49}$")


@dataclass(frozen=True)
class BridgeSpec:
    runtime_id: int
    owner_token: str
    loopback_host: str
    host_port: int
    upstream_host: str
    upstream_port: int
    adapter_type: str

    def __post_init__(self) -> None:
        if self.runtime_id <= 0:
            raise ValueError("runtime_id must be positive")
        if not self.owner_token or len(self.owner_token) > 100:
            raise ValueError("owner_token must be a bounded non-empty value")
        if self.loopback_host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("bridge listener must use loopback")
        validate_port(self.host_port, "host_port")
        validate_host(self.upstream_host)
        validate_port(self.upstream_port, "upstream_port")
        if not _ADAPTER_TYPE.fullmatch(self.adapter_type):
            raise ValueError("adapter_type contains unsupported characters")


@dataclass(frozen=True, repr=False)
class BridgeCredentials:
    username: SecretValue | None = None
    password: SecretValue | None = None

    def __repr__(self) -> str:
        return "BridgeCredentials(username=[REDACTED], password=[REDACTED])"


@dataclass(frozen=True)
class BridgeObservation:
    runtime_id: int
    owner_token: str
    status: str
    supervisor_id: str | None = None
    pid: int | None = None
    process_start_token: str | None = None


class HostProxyBridgeSupervisor(Protocol):
    def ensure_started(self, spec: BridgeSpec, credentials: BridgeCredentials) -> BridgeObservation: ...
    def inspect(self, runtime_id: int, owner_token: str) -> BridgeObservation: ...
    def stop(self, runtime_id: int, owner_token: str) -> BridgeObservation: ...


class BridgeSupervisorUnavailable(RuntimeError):
    """Raised until a real host bridge supervisor is configured."""


class BridgeOwnershipConflict(RuntimeError):
    """Raised when persisted and live ownership evidence does not agree."""


class UnavailableHostProxyBridgeSupervisor:
    """Safe production placeholder that never pretends a bridge exists."""

    @staticmethod
    def _unavailable() -> None:
        raise BridgeSupervisorUnavailable("Host proxy bridge supervisor is unavailable")

    def ensure_started(self, spec: BridgeSpec, credentials: BridgeCredentials) -> BridgeObservation:
        del spec, credentials
        self._unavailable()

    def inspect(self, runtime_id: int, owner_token: str) -> BridgeObservation:
        del runtime_id, owner_token
        self._unavailable()

    def stop(self, runtime_id: int, owner_token: str) -> BridgeObservation:
        del runtime_id, owner_token
        self._unavailable()


class FakeHostProxyBridgeSupervisor:
    """Deterministic in-memory test double that launches no process."""

    def __init__(self) -> None:
        self._bridges: dict[int, tuple[BridgeSpec, BridgeObservation]] = {}

    def ensure_started(self, spec: BridgeSpec, credentials: BridgeCredentials) -> BridgeObservation:
        del credentials
        existing = self._bridges.get(spec.runtime_id)
        if existing is not None and existing[0].owner_token != spec.owner_token:
            raise RuntimeError("Bridge ownership conflict")
        observation = BridgeObservation(
            runtime_id=spec.runtime_id,
            owner_token=spec.owner_token,
            status="running",
            supervisor_id=f"fake-runtime-{spec.runtime_id}",
        )
        self._bridges[spec.runtime_id] = (spec, observation)
        return observation

    def inspect(self, runtime_id: int, owner_token: str) -> BridgeObservation:
        existing = self._bridges.get(runtime_id)
        if existing is None:
            return BridgeObservation(runtime_id, owner_token, "stopped")
        if existing[0].owner_token != owner_token:
            raise RuntimeError("Bridge ownership conflict")
        return existing[1]

    def stop(self, runtime_id: int, owner_token: str) -> BridgeObservation:
        existing = self._bridges.get(runtime_id)
        if existing is not None and existing[0].owner_token != owner_token:
            raise RuntimeError("Bridge ownership conflict")
        self._bridges.pop(runtime_id, None)
        return BridgeObservation(runtime_id, owner_token, "stopped")
