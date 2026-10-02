"""Durable allocation and orchestration for managed Redroid provisioning."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

import fcntl

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.models import Device, RedroidProvisioning, Runtime
from app.services.redroid_provisioning_adapter import (
    OccupiedResources,
    ProvisioningAllocation,
    ProvisioningVerificationError,
    RedroidProvisioningAdapter,
)
from app.services.redroid_provisioning_config import RedroidProvisioningSettings


class ProvisioningError(RuntimeError):
    pass


class ProvisioningIdempotencyConflict(ProvisioningError):
    pass


class ProvisioningAllocationError(ProvisioningError):
    pass


class ProvisioningFailedError(ProvisioningError):
    def __init__(
        self, provisioning_id: str, cause: BaseException, *, stage: str
    ) -> None:
        self.provisioning_id = provisioning_id
        self.cause = cause
        self.stage = stage
        super().__init__(f"Provisioning {provisioning_id} failed: {cause}")


@dataclass(frozen=True)
class ProvisioningRequest:
    name: str
    profile: str
    notes: str | None = None

    def fingerprint(self) -> str:
        payload = json.dumps(
            {"name": self.name, "notes": self.notes, "profile": self.profile},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()


class AllocationLock(Protocol):
    def acquire(self, session: Session) -> None: ...


class DatabaseAllocationLock:
    """Short cross-process allocation lock with SQLite/PostgreSQL strategies."""

    advisory_key = 8_417_018

    def acquire(self, session: Session) -> None:
        dialect = session.get_bind().dialect.name
        if dialect == "sqlite":
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        elif dialect == "postgresql":
            session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": self.advisory_key},
            )
        else:
            raise ProvisioningAllocationError(
                f"Provisioning allocation locking is unsupported for {dialect}"
            )


class AttemptExecutionGuard(Protocol):
    @contextmanager
    def acquire(self, attempt_id: str) -> Iterator[bool]: ...


class FileAttemptExecutionGuard:
    """Cross-process, nonblocking attempt guard for a single manager host."""

    def __init__(self, data_root: Path) -> None:
        self.lock_root = data_root.resolve() / ".tiktok-manager-locks"

    @contextmanager
    def acquire(self, attempt_id: str) -> Iterator[bool]:
        try:
            normalized = str(uuid.UUID(attempt_id))
        except ValueError as error:
            raise ProvisioningError("Invalid provisioning attempt ID") from error
        data_root = self.lock_root.parent
        if data_root.is_symlink() or not data_root.is_dir():
            raise ProvisioningError("Provisioning data root is unavailable or unsafe")
        if self.lock_root.is_symlink():
            raise ProvisioningError("Provisioning lock directory must not be a symlink")
        self.lock_root.mkdir(mode=0o700, exist_ok=True)
        lock_path = self.lock_root / f"{normalized}.lock"
        descriptor = os.open(
            lock_path,
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
            0o600,
        )
        acquired = False
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                pass
            yield acquired
        finally:
            if acquired:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


_TERMINAL_STATES = {"completed", "rolled_back", "failed", "rollback_failed", "inconsistent"}


class RedroidProvisioningService:
    """Reserve unique resources and provision a stopped managed Redroid runtime."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        adapter: RedroidProvisioningAdapter,
        settings: RedroidProvisioningSettings,
        *,
        allocation_lock: AllocationLock | None = None,
        execution_guard: AttemptExecutionGuard | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.adapter = adapter
        self.settings = settings
        self.allocation_lock = allocation_lock or DatabaseAllocationLock()
        self.execution_guard = execution_guard or FileAttemptExecutionGuard(
            settings.data_root
        )

    def get_or_create_request(
        self, idempotency_key: str, request: ProvisioningRequest
    ) -> RedroidProvisioning:
        key = idempotency_key.strip()
        if not key or len(key) > 255:
            raise ProvisioningError("idempotency_key must contain 1 to 255 characters")
        fingerprint = request.fingerprint()
        with self.session_factory() as session:
            self.allocation_lock.acquire(session)
            existing = session.scalar(
                select(RedroidProvisioning).where(
                    RedroidProvisioning.idempotency_key == key
                )
            )
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise ProvisioningIdempotencyConflict(
                        "Idempotency key was already used for a different request"
                    )
                if (
                    existing.installation_id != self.settings.installation_id
                    or existing.image_reference != self.settings.image_reference
                ):
                    raise ProvisioningIdempotencyConflict(
                        "Idempotent provisioning belongs to different trusted configuration"
                    )
                session.commit()
                return existing
            attempt = RedroidProvisioning(
                id=str(uuid.uuid4()),
                idempotency_key=key,
                request_fingerprint=fingerprint,
                ownership_token=str(uuid.uuid4()),
                installation_id=self.settings.installation_id,
                state="requested",
                image_reference=self.settings.image_reference,
            )
            session.add(attempt)
            session.commit()
            session.refresh(attempt)
            return attempt

    def reserve(self, attempt_id: str) -> RedroidProvisioning:
        occupied = self.adapter.occupied_resources()
        with self.session_factory() as session:
            self.allocation_lock.acquire(session)
            attempt = self._require_attempt(session, attempt_id)
            if attempt.device_number is not None:
                session.commit()
                return attempt
            reserved_numbers = set(
                session.scalars(
                    select(RedroidProvisioning.device_number).where(
                        RedroidProvisioning.device_number.is_not(None)
                    )
                )
            )
            runtimes = session.scalars(select(Runtime)).all()
            runtime_containers = {value for item in runtimes if (value := item.docker_container_name)}
            runtime_adb = {value for item in runtimes if (value := item.adb_serial)}
            number = self._select_number(
                reserved_numbers, runtime_containers, runtime_adb, occupied
            )
            suffix = f"{number:02d}"
            port = self.settings.base_adb_port + number
            attempt.device_number = number
            attempt.container_name = f"redroid-device-{suffix}"
            attempt.adb_host_port = port
            attempt.adb_serial = f"localhost:{port}"
            attempt.data_path = str(
                self.settings.data_root.resolve() / f"device-{suffix}-data"
            )
            attempt.network_name = f"{self.settings.network_prefix}-{suffix}-net"
            attempt.state = "reserved"
            session.commit()
            session.refresh(attempt)
            return attempt

    def provision(
        self, idempotency_key: str, request: ProvisioningRequest
    ) -> RedroidProvisioning:
        if request.profile != self.settings.supported_profile:
            raise ProvisioningError(f"Unsupported provisioning profile: {request.profile}")
        attempt = self.get_or_create_request(idempotency_key, request)
        with self.execution_guard.acquire(attempt.id) as acquired:
            if not acquired:
                return self.get(attempt.id)
            attempt = self.get(attempt.id)
            if attempt.state in _TERMINAL_STATES:
                return attempt
            return self._advance(attempt, request)

    def _advance(
        self, attempt: RedroidProvisioning, request: ProvisioningRequest
    ) -> RedroidProvisioning:
        initial_state = attempt.state
        stage = "preflight"
        try:
            if attempt.state == "requested":
                self._set_state(attempt.id, "preflighting")
            self.adapter.preflight()
            attempt = self.get(attempt.id)
            if attempt.device_number is None:
                stage = "allocation"
                attempt = self.reserve(attempt.id)
            allocation = self._allocation(attempt)
            if attempt.state == "reserved":
                stage = "data"
                created = self.adapter.create_owned_data_directory(allocation)
                self._record_stage(attempt.id, "data_created", data_directory_created=created or attempt.data_directory_created)
            attempt = self.get(attempt.id)
            if attempt.state == "data_created":
                stage = "network"
                network_id = self.adapter.create_network(allocation)
                self._record_stage(attempt.id, "network_created", network_created=True, docker_network_id=network_id)
            attempt = self.get(attempt.id)
            if attempt.state == "network_created":
                stage = "network_inspection"
                if not attempt.docker_network_id:
                    raise ProvisioningError("Network ID was not persisted")
                self.adapter.verify_network(allocation, attempt.docker_network_id)
                stage = "container"
                container_id = self.adapter.create_container(allocation)
                self._record_stage(attempt.id, "container_created", container_created=True, docker_container_id=container_id)
            attempt = self.get(attempt.id)
            if attempt.state == "container_created":
                stage = "container_inspection"
                if not attempt.docker_container_id:
                    raise ProvisioningError("Container ID was not persisted")
                self.adapter.verify_container(allocation, attempt.docker_container_id)
                self._set_state(attempt.id, "inspected")
            stage = "database"
            return self._complete(attempt.id, request)
        except Exception as error:
            self._record_error(attempt.id, error)
            current = self.get(attempt.id)
            resumed_verification = (
                isinstance(error, ProvisioningVerificationError)
                and initial_state in {"network_created", "container_created", "inspected"}
            )
            if resumed_verification:
                self._record_error(attempt.id, error, state="inconsistent")
            elif current.device_number is None:
                self._record_error(attempt.id, error, state="failed")
            else:
                self.rollback(attempt.id)
            raise ProvisioningFailedError(attempt.id, error, stage=stage) from error

    def rollback(self, attempt_id: str) -> RedroidProvisioning:
        attempt = self.get(attempt_id)
        if attempt.state == "completed":
            raise ProvisioningError("Completed provisioning cannot be rolled back")
        self._set_state(attempt_id, "rolling_back")
        allocation = self._allocation(attempt)
        try:
            container_id = attempt.docker_container_id or self.adapter.owned_container_id(allocation)
            if container_id:
                self.adapter.remove_owned_container(allocation, container_id)
            network_id = attempt.docker_network_id or self.adapter.owned_network_id(allocation)
            if network_id:
                self.adapter.remove_owned_network(allocation, network_id)
            if attempt.data_directory_created:
                self.adapter.remove_owned_data_directory(allocation)
        except Exception as error:
            self._record_error(attempt_id, error, state="rollback_failed")
            return self.get(attempt_id)
        self._set_state(attempt_id, "rolled_back")
        return self.get(attempt_id)

    def get(self, attempt_id: str) -> RedroidProvisioning:
        with self.session_factory() as session:
            return self._require_attempt(session, attempt_id)

    def _select_number(
        self,
        reserved_numbers: set[int | None],
        runtime_containers: set[str],
        runtime_adb: set[str],
        occupied: OccupiedResources,
    ) -> int:
        for number in range(1, 65535 - self.settings.base_adb_port + 1):
            if number in reserved_numbers:
                continue
            suffix = f"{number:02d}"
            container = f"redroid-device-{suffix}"
            port = self.settings.base_adb_port + number
            adb = f"localhost:{port}"
            data_path = self.settings.data_root.resolve() / f"device-{suffix}-data"
            network = f"{self.settings.network_prefix}-{suffix}-net"
            if container in runtime_containers or adb in runtime_adb:
                continue
            if container in occupied.container_names or network in occupied.network_names:
                continue
            if data_path in occupied.data_paths or port in occupied.host_ports:
                continue
            if not self.adapter.port_is_available(port):
                continue
            return number
        raise ProvisioningAllocationError("No Redroid device allocation is available")

    def _complete(self, attempt_id: str, request: ProvisioningRequest) -> RedroidProvisioning:
        with self.session_factory() as session:
            attempt = self._require_attempt(session, attempt_id)
            if attempt.state == "completed":
                return attempt
            if attempt.state != "inspected" or attempt.device_number is None:
                raise ProvisioningError("Provisioning must be inspected before DB completion")
            suffix = f"{attempt.device_number:02d}"
            device = Device(name=request.name, device_type="emulator", platform="android", os_version="12", status="offline", notes=request.notes)
            session.add(device)
            session.flush()
            runtime = Runtime(
                device_id=device.id,
                name=f"redroid-runtime-{suffix}",
                runtime_type="redroid",
                docker_container_name=attempt.container_name,
                adb_serial=attempt.adb_serial,
                status="stopped",
                last_seen_at=None,
            )
            session.add(runtime)
            session.flush()
            attempt.device_id = device.id
            attempt.runtime_id = runtime.id
            attempt.state = "completed"
            attempt.error_code = None
            attempt.error_message = None
            session.commit()
            session.refresh(attempt)
            return attempt

    def _record_stage(self, attempt_id: str, state: str, **values: object) -> None:
        with self.session_factory() as session:
            attempt = self._require_attempt(session, attempt_id)
            for key, value in values.items():
                setattr(attempt, key, value)
            attempt.state = state
            session.commit()

    def _set_state(self, attempt_id: str, state: str) -> None:
        self._record_stage(attempt_id, state)

    def _record_error(self, attempt_id: str, error: BaseException, *, state: str | None = None) -> None:
        with self.session_factory() as session:
            attempt = self._require_attempt(session, attempt_id)
            attempt.error_code = type(error).__name__
            attempt.error_message = str(error)
            if state:
                attempt.state = state
            session.commit()

    @staticmethod
    def _require_attempt(session: Session, attempt_id: str) -> RedroidProvisioning:
        attempt = session.get(RedroidProvisioning, attempt_id)
        if attempt is None:
            raise ProvisioningError("Provisioning attempt not found")
        return attempt

    @staticmethod
    def _allocation(attempt: RedroidProvisioning) -> ProvisioningAllocation:
        required = (
            attempt.device_number,
            attempt.container_name,
            attempt.adb_host_port,
            attempt.adb_serial,
            attempt.data_path,
            attempt.network_name,
        )
        if any(value is None for value in required):
            raise ProvisioningError("Provisioning attempt has no complete allocation")
        return ProvisioningAllocation(
            provisioning_id=attempt.id,
            ownership_token=attempt.ownership_token,
            device_number=int(attempt.device_number),
            container_name=str(attempt.container_name),
            adb_host_port=int(attempt.adb_host_port),
            adb_serial=str(attempt.adb_serial),
            data_path=Path(str(attempt.data_path)),
            network_name=str(attempt.network_name),
            image_reference=attempt.image_reference,
            installation_id=attempt.installation_id,
        )
