"""Safe application and cleanup orchestration for Runtime network state."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.models import Runtime, RuntimeNetworkConfig, RuntimeNetworkConfigRevision, RuntimeNetworkState
from app.models.timestamps import utc_now
from app.services.android_network import AdbReverseRule, AndroidNetworkAdapter, AndroidNetworkCommandError
from app.services.network_operation_lock import NetworkOperationLockBusy, RuntimeNetworkOperationGuard
from app.services.network_credentials import NetworkCredentialError, NetworkCredentialProvider
from app.services.network_secrets import SecretResolutionError, SecretResolver
from app.services.proxy_bridge import (
    BridgeCredentials,
    BridgeSpec,
    BridgeOwnershipConflict,
    HostProxyBridgeSupervisor,
)
from app.services.redroid_runtime import RedroidRuntimeAdapter, RedroidRuntimeError

logger = logging.getLogger(__name__)


class NetworkApplyError(RuntimeError):
    """Base sanitized network application error."""


class NetworkRuntimeStopped(NetworkApplyError):
    pass


class NetworkRevisionRace(NetworkApplyError):
    pass


class NetworkAdbFailure(NetworkApplyError):
    pass


class NetworkBridgeFailure(NetworkApplyError):
    pass


class NetworkSecretFailure(NetworkApplyError):
    pass


@dataclass(frozen=True)
class NetworkCheckSnapshot:
    runtime: str
    adb: str
    android_proxy: str
    adb_reverse: str
    bridge: str
    connectivity: str = "not_run"


class RuntimeNetworkOrchestrator:
    """Apply one desired revision without mutating lifecycle readiness."""

    def __init__(
        self,
        session: Session,
        *,
        runtime_adapter: RedroidRuntimeAdapter,
        android_adapter: AndroidNetworkAdapter,
        bridge_supervisor: HostProxyBridgeSupervisor,
        secret_resolver: SecretResolver,
        guard: RuntimeNetworkOperationGuard,
        credential_provider: NetworkCredentialProvider | None = None,
    ) -> None:
        self.session = session
        self.runtime_adapter = runtime_adapter
        self.android_adapter = android_adapter
        self.bridge_supervisor = bridge_supervisor
        self.secret_resolver = secret_resolver
        self.guard = guard
        self.credential_provider = credential_provider

    def apply(self, runtime_id: int) -> RuntimeNetworkState:
        try:
            with self.guard.acquire_runtime(runtime_id, blocking=False):
                return self._apply_locked(runtime_id)
        except NetworkOperationLockBusy:
            raise

    def _apply_locked(self, runtime_id: int) -> RuntimeNetworkState:
        runtime, config, state = self._load(runtime_id)
        revision = config.desired_revision
        if runtime.status == "stopped":
            self._mark_pending(state, revision, "RUNTIME_STOPPED", "Runtime is stopped")
            raise NetworkRuntimeStopped("Runtime is stopped; desired network state remains pending")
        self._require_runtime_ready(runtime, state, revision)
        state.status = "applying"
        state.desired_revision = revision
        state.last_apply_attempt_at = utc_now()
        state.error_code = None
        state.error_message = None
        self.session.commit()
        try:
            if config.mode == "direct":
                self._apply_direct(runtime, config, state)
            else:
                self._apply_http_proxy(runtime, config, state)
        except (SecretResolutionError, NetworkCredentialError) as error:
            self._record_failure(state, revision, "PROXY_SECRET_UNAVAILABLE", "Configured proxy secret is unavailable")
            raise NetworkSecretFailure("Configured proxy secret is unavailable") from error
        except AndroidNetworkCommandError as error:
            self._record_failure(state, revision, "ADB_NETWORK_FAILED", "ADB network operation failed")
            raise NetworkAdbFailure("ADB network operation failed") from error
        except BridgeOwnershipConflict as error:
            self._record_failure(
                state,
                revision,
                "BRIDGE_OWNERSHIP_CONFLICT",
                "Host proxy bridge ownership could not be verified",
            )
            raise NetworkBridgeFailure(
                "Host proxy bridge ownership could not be verified"
            ) from error
        except (NetworkBridgeFailure, NetworkRevisionRace):
            raise
        except Exception as error:
            self._record_failure(state, revision, "BRIDGE_OPERATION_FAILED", "Host proxy bridge operation failed")
            raise NetworkBridgeFailure("Host proxy bridge operation failed") from error
        return state

    def _apply_http_proxy(
        self,
        runtime: Runtime,
        config: RuntimeNetworkConfig,
        state: RuntimeNetworkState,
    ) -> None:
        assert runtime.adb_serial
        assert config.proxy_host and config.proxy_port
        assert config.bridge_host_port and config.bridge_device_port
        owner_token = state.bridge_owner_token or str(uuid4())
        state.bridge_owner_token = owner_token
        credentials = (
            self.credential_provider.resolve(self.session, config)
            if self.credential_provider is not None
            else BridgeCredentials(
                username=(
                    self.secret_resolver.resolve(config.proxy_username_secret_ref)
                    if config.proxy_username_secret_ref
                    else None
                ),
                password=(
                    self.secret_resolver.resolve(config.proxy_password_secret_ref)
                    if config.proxy_password_secret_ref
                    else None
                ),
            )
        )
        spec = BridgeSpec(
            runtime_id=runtime.id,
            owner_token=owner_token,
            loopback_host="127.0.0.1",
            host_port=config.bridge_host_port,
            upstream_host=config.proxy_host,
            upstream_port=config.proxy_port,
            adapter_type="generic_http",
        )
        try:
            observation = self.bridge_supervisor.ensure_started(spec, credentials)
            verified_bridge = self.bridge_supervisor.inspect(runtime.id, owner_token)
        except BridgeOwnershipConflict:
            raise
        except Exception as error:
            self._record_failure(state, config.desired_revision, "BRIDGE_OPERATION_FAILED", "Host proxy bridge operation failed")
            raise NetworkBridgeFailure("Host proxy bridge operation failed") from error
        if (
            observation.owner_token != owner_token
            or verified_bridge.owner_token != owner_token
            or verified_bridge.status != "running"
        ):
            self._record_failure(state, config.desired_revision, "BRIDGE_VERIFICATION_FAILED", "Host proxy bridge verification failed")
            raise NetworkBridgeFailure("Host proxy bridge verification failed")

        self.android_adapter.add_reverse_rule(
            runtime.adb_serial,
            config.bridge_device_port,
            config.bridge_host_port,
        )
        self.android_adapter.set_global_http_proxy(
            runtime.adb_serial, "127.0.0.1", config.bridge_device_port
        )
        settings = self.android_adapter.get_proxy_settings(runtime.adb_serial)
        rules = self.android_adapter.list_reverse_rules(runtime.adb_serial)
        expected_rule = AdbReverseRule(config.bridge_device_port, config.bridge_host_port)
        if settings.host != "127.0.0.1" or settings.port != config.bridge_device_port:
            raise AndroidNetworkCommandError("Android proxy verification failed")
        if expected_rule not in rules:
            raise AndroidNetworkCommandError("ADB reverse verification failed")
        self._assert_current_revision(runtime.id, config.desired_revision, state)
        now = utc_now()
        state.status = "ready"
        state.applied_revision = config.desired_revision
        state.observed_mode = "http_proxy"
        state.observed_android_proxy_host = settings.host
        state.observed_android_proxy_port = settings.port
        state.reverse_present = True
        state.bridge_status = "running"
        state.bridge_supervisor_id = verified_bridge.supervisor_id
        state.bridge_pid = verified_bridge.pid
        state.bridge_process_start_token = verified_bridge.process_start_token
        state.last_applied_at = now
        state.last_verified_at = now
        state.error_code = None
        state.error_message = None
        self.session.commit()

    def _apply_direct(
        self,
        runtime: Runtime,
        config: RuntimeNetworkConfig,
        state: RuntimeNetworkState,
    ) -> None:
        assert runtime.adb_serial
        previous = self._latest_http_revision(runtime.id)
        self.android_adapter.clear_global_http_proxy(runtime.adb_serial)
        if previous and previous.bridge_device_port and previous.bridge_host_port:
            self.android_adapter.remove_reverse_rule(
                runtime.adb_serial,
                previous.bridge_device_port,
                previous.bridge_host_port,
            )
        if state.bridge_owner_token:
            try:
                stopped = self.bridge_supervisor.stop(runtime.id, state.bridge_owner_token)
            except BridgeOwnershipConflict:
                raise
            except Exception:
                self._record_failure(state, config.desired_revision, "BRIDGE_OPERATION_FAILED", "Host proxy bridge cleanup failed")
                raise NetworkBridgeFailure("Host proxy bridge cleanup failed") from error
            if stopped.owner_token != state.bridge_owner_token or stopped.status != "stopped":
                raise NetworkBridgeFailure("Host proxy bridge cleanup could not be verified")
        settings = self.android_adapter.get_proxy_settings(runtime.adb_serial)
        rules = self.android_adapter.list_reverse_rules(runtime.adb_serial)
        if any((settings.http_proxy, settings.host, settings.port, settings.exclusion_list)):
            raise AndroidNetworkCommandError("Android proxy clear verification failed")
        if previous and previous.bridge_device_port and previous.bridge_host_port:
            if AdbReverseRule(previous.bridge_device_port, previous.bridge_host_port) in rules:
                raise AndroidNetworkCommandError("ADB reverse removal verification failed")
        self._assert_current_revision(runtime.id, config.desired_revision, state)
        now = utc_now()
        state.status = "disabled"
        state.applied_revision = config.desired_revision
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
        state.error_code = None
        state.error_message = None
        self.session.commit()

    def cleanup_before_delete(self, runtime_id: int) -> None:
        config = self.session.scalar(
            select(RuntimeNetworkConfig).where(RuntimeNetworkConfig.runtime_id == runtime_id)
        )
        if config is None:
            return
        try:
            with self.guard.acquire_runtime(runtime_id, blocking=False):
                runtime, _, state = self._load(runtime_id)
                previous = self._latest_http_revision(runtime_id)
                if runtime.status != "stopped" and runtime.adb_serial:
                    self.android_adapter.clear_global_http_proxy(runtime.adb_serial)
                    if previous and previous.bridge_device_port and previous.bridge_host_port:
                        self.android_adapter.remove_reverse_rule(
                            runtime.adb_serial,
                            previous.bridge_device_port,
                            previous.bridge_host_port,
                        )
                if state.bridge_owner_token:
                    observation = self.bridge_supervisor.stop(runtime_id, state.bridge_owner_token)
                    if observation.owner_token != state.bridge_owner_token or observation.status != "stopped":
                        raise NetworkBridgeFailure("Bridge ownership could not be verified")
                state.bridge_owner_token = None
                state.bridge_status = "stopped"
                self.session.commit()
        except NetworkOperationLockBusy as error:
            raise NetworkApplyError("Runtime network cleanup is already in progress") from error
        except AndroidNetworkCommandError as error:
            raise NetworkAdbFailure("Runtime network cleanup failed") from error
        except NetworkBridgeFailure:
            raise
        except Exception as error:
            raise NetworkBridgeFailure("Runtime network cleanup failed safely") from error

    def checks(self, runtime_id: int) -> NetworkCheckSnapshot:
        runtime, config, state = self._load(runtime_id)
        runtime_check = "ok" if runtime.status != "stopped" else "stopped"
        if state.status == "ready":
            return NetworkCheckSnapshot(runtime_check, "ok", "ok", "ok", "ok")
        if state.status == "disabled" and state.applied_revision == config.desired_revision:
            return NetworkCheckSnapshot(runtime_check, "ok", "clear", "absent", "stopped")
        return NetworkCheckSnapshot(
            runtime_check,
            "unknown",
            "unknown",
            "unknown",
            state.bridge_status,
        )

    def _require_runtime_ready(
        self, runtime: Runtime, state: RuntimeNetworkState, revision: int
    ) -> None:
        if not runtime.docker_container_name or not runtime.adb_serial:
            self._record_failure(state, revision, "RUNTIME_CONFIGURATION_INVALID", "Runtime network target is incomplete")
            raise NetworkAdbFailure("Runtime network target is incomplete")
        try:
            container = self.runtime_adapter.get_container_status(runtime.docker_container_name)
            if container != "running":
                self._mark_pending(state, revision, "RUNTIME_STOPPED", "Runtime is stopped")
                raise NetworkRuntimeStopped("Runtime is stopped; desired network state remains pending")
            if not self.runtime_adapter.check_boot(runtime.docker_container_name):
                self._record_failure(
                    state, revision, "ANDROID_NOT_READY", "Android is not boot-ready"
                )
                raise NetworkAdbFailure("Android is not boot-ready")
            if not self.runtime_adapter.check_adb(runtime.adb_serial):
                self._record_failure(
                    state, revision, "ADB_UNAVAILABLE", "ADB is unavailable"
                )
                raise NetworkAdbFailure("ADB is unavailable")
        except NetworkApplyError:
            raise
        except RedroidRuntimeError as error:
            self._record_failure(state, revision, "ADB_UNAVAILABLE", "Runtime readiness check failed")
            raise NetworkAdbFailure("Runtime readiness check failed") from error

    def _assert_current_revision(
        self, runtime_id: int, applied_revision: int, state: RuntimeNetworkState
    ) -> None:
        self.session.expire_all()
        current = self.session.scalar(
            select(RuntimeNetworkConfig).where(RuntimeNetworkConfig.runtime_id == runtime_id)
        )
        if current is None or current.desired_revision != applied_revision:
            if current is not None:
                state = self.session.get(RuntimeNetworkState, runtime_id) or state
                state.desired_revision = current.desired_revision
                state.status = "pending"
                state.error_code = "REVISION_CHANGED"
                state.error_message = "Desired network revision changed during apply"
                self.session.commit()
            raise NetworkRevisionRace("Desired network revision changed during apply; retry required")

    def _load(
        self, runtime_id: int
    ) -> tuple[Runtime, RuntimeNetworkConfig, RuntimeNetworkState]:
        runtime = self.session.get(Runtime, runtime_id)
        config = self.session.scalar(
            select(RuntimeNetworkConfig).where(RuntimeNetworkConfig.runtime_id == runtime_id)
        )
        state = self.session.get(RuntimeNetworkState, runtime_id)
        if runtime is None:
            raise NetworkApplyError("Runtime not found")
        if config is None or state is None:
            raise NetworkApplyError("Runtime network configuration is unmanaged")
        return runtime, config, state

    def _latest_http_revision(
        self, runtime_id: int
    ) -> RuntimeNetworkConfigRevision | None:
        return self.session.scalar(
            select(RuntimeNetworkConfigRevision)
            .where(
                RuntimeNetworkConfigRevision.runtime_id == runtime_id,
                RuntimeNetworkConfigRevision.mode == "http_proxy",
            )
            .order_by(RuntimeNetworkConfigRevision.revision.desc())
            .limit(1)
        )

    def _mark_pending(
        self,
        state: RuntimeNetworkState,
        revision: int,
        code: str,
        message: str,
    ) -> None:
        state.status = "pending"
        state.desired_revision = revision
        state.error_code = code
        state.error_message = message
        self.session.commit()

    def _record_failure(
        self,
        state: RuntimeNetworkState,
        revision: int,
        code: str,
        message: str,
    ) -> None:
        state.status = "failed"
        state.desired_revision = revision
        state.error_code = code
        state.error_message = message
        state.last_verified_at = utc_now()
        self.session.commit()


class RuntimeNetworkCleanupCoordinator:
    """Open an isolated session for provisioning/deletion cleanup."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        runtime_adapter: RedroidRuntimeAdapter,
        android_adapter: AndroidNetworkAdapter,
        bridge_supervisor: HostProxyBridgeSupervisor,
        secret_resolver: SecretResolver,
        guard: RuntimeNetworkOperationGuard,
        credential_provider: NetworkCredentialProvider | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.runtime_adapter = runtime_adapter
        self.android_adapter = android_adapter
        self.bridge_supervisor = bridge_supervisor
        self.secret_resolver = secret_resolver
        self.guard = guard
        self.credential_provider = credential_provider

    def cleanup_before_delete(self, runtime_id: int) -> None:
        with self.session_factory() as session:
            RuntimeNetworkOrchestrator(
                session,
                runtime_adapter=self.runtime_adapter,
                android_adapter=self.android_adapter,
                bridge_supervisor=self.bridge_supervisor,
                secret_resolver=self.secret_resolver,
                guard=self.guard,
                credential_provider=self.credential_provider,
            ).cleanup_before_delete(runtime_id)


class RuntimeNetworkRecoveryCoordinator:
    """Reconcile durable network intent after host-manager startup."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        runtime_adapter: RedroidRuntimeAdapter,
        android_adapter: AndroidNetworkAdapter,
        bridge_supervisor: HostProxyBridgeSupervisor,
        secret_resolver: SecretResolver,
        guard: RuntimeNetworkOperationGuard,
        credential_provider: NetworkCredentialProvider | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.runtime_adapter = runtime_adapter
        self.android_adapter = android_adapter
        self.bridge_supervisor = bridge_supervisor
        self.secret_resolver = secret_resolver
        self.guard = guard
        self.credential_provider = credential_provider

    def reconcile_startup(self) -> None:
        with self.session_factory() as session:
            runtime_ids = session.scalars(
                select(RuntimeNetworkConfig.runtime_id).order_by(
                    RuntimeNetworkConfig.runtime_id
                )
            ).all()
        for runtime_id in runtime_ids:
            try:
                self._reconcile_one(runtime_id)
            except Exception as error:
                # All expected errors are sanitized by the orchestrator. Avoid
                # exception tracebacks because dependency messages may contain
                # host-specific details.
                logger.error(
                    "Startup network reconciliation failed for Runtime %s",
                    runtime_id,
                )

    def _reconcile_one(self, runtime_id: int) -> None:
        with self.session_factory() as session:
            runtime = session.get(Runtime, runtime_id)
            config = session.scalar(
                select(RuntimeNetworkConfig).where(
                    RuntimeNetworkConfig.runtime_id == runtime_id
                )
            )
            state = session.get(RuntimeNetworkState, runtime_id)
            if runtime is None or config is None or state is None:
                return
            if runtime.status == "stopped":
                self._reconcile_stopped(session, config, state)
                return
            RuntimeNetworkOrchestrator(
                session,
                runtime_adapter=self.runtime_adapter,
                android_adapter=self.android_adapter,
                bridge_supervisor=self.bridge_supervisor,
                secret_resolver=self.secret_resolver,
                guard=self.guard,
                credential_provider=self.credential_provider,
            ).apply(runtime_id)

    def _reconcile_stopped(
        self,
        session: Session,
        config: RuntimeNetworkConfig,
        state: RuntimeNetworkState,
    ) -> None:
        try:
            with self.guard.acquire_runtime(config.runtime_id, blocking=False):
                if state.bridge_owner_token:
                    stopped = self.bridge_supervisor.stop(
                        config.runtime_id, state.bridge_owner_token
                    )
                    if stopped.status != "stopped":
                        raise NetworkBridgeFailure(
                            "Host proxy bridge cleanup could not be verified"
                        )
                state.bridge_status = "stopped"
                state.bridge_supervisor_id = None
                state.bridge_pid = None
                state.bridge_process_start_token = None
                state.desired_revision = config.desired_revision
                if config.mode == "http_proxy" or (
                    state.applied_revision != config.desired_revision
                ):
                    state.status = "pending"
                    state.error_code = "RUNTIME_STOPPED"
                    state.error_message = (
                        "Runtime is stopped; desired network state remains pending"
                    )
                else:
                    state.status = "disabled"
                    state.error_code = None
                    state.error_message = None
                session.commit()
        except BridgeOwnershipConflict as error:
            state.status = "failed"
            state.error_code = "BRIDGE_OWNERSHIP_CONFLICT"
            state.error_message = "Host proxy bridge ownership could not be verified"
            session.commit()
            raise NetworkBridgeFailure(state.error_message) from error
