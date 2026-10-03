"""Per-Runtime network desired-state and reconciliation endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Runtime, RuntimeNetworkConfig, RuntimeNetworkState
from app.schemas.runtime_network import (
    NetworkChecks,
    NetworkCredentialsSummary,
    NetworkObservedSummary,
    RuntimeNetworkResponse,
    RuntimeNetworkStatusResponse,
    RuntimeNetworkUpdate,
)
from app.services.android_network import AndroidNetworkAdapter
from app.services.network_config import RuntimeNetworkSettings
from app.services.network_operation_lock import NetworkOperationLockBusy, RuntimeNetworkOperationGuard
from app.services.network_secrets import SecretResolutionError, SecretResolver
from app.services.network_validation import NetworkValidationError
from app.services.proxy_bridge import HostProxyBridgeSupervisor
from app.services.redroid_runtime import RedroidRuntimeAdapter
from app.services.runtime_network import (
    DesiredNetworkInput,
    RuntimeNetworkError,
    RuntimeNetworkNotFoundError,
    RuntimeNetworkRevisionConflict,
    RuntimeNetworkService,
)
from app.services.runtime_network_orchestration import (
    NetworkAdbFailure,
    NetworkApplyError,
    NetworkBridgeFailure,
    NetworkRevisionRace,
    NetworkRuntimeStopped,
    NetworkSecretFailure,
    RuntimeNetworkOrchestrator,
)
from app.services.systemd_proxy_bridge import SystemdHostProxyBridgeSupervisor

router = APIRouter(prefix="/runtimes", tags=["runtime-network"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def get_android_network_adapter() -> AndroidNetworkAdapter:
    return AndroidNetworkAdapter()


def get_network_runtime_adapter() -> RedroidRuntimeAdapter:
    return RedroidRuntimeAdapter()


def get_host_proxy_bridge_supervisor() -> HostProxyBridgeSupervisor:
    return SystemdHostProxyBridgeSupervisor(RuntimeNetworkSettings.from_environment())


def get_network_secret_resolver() -> SecretResolver:
    return SecretResolver()


def get_runtime_network_settings() -> RuntimeNetworkSettings:
    return RuntimeNetworkSettings.from_environment()


AndroidAdapter = Annotated[AndroidNetworkAdapter, Depends(get_android_network_adapter)]
RuntimeAdapter = Annotated[RedroidRuntimeAdapter, Depends(get_network_runtime_adapter)]
BridgeSupervisor = Annotated[HostProxyBridgeSupervisor, Depends(get_host_proxy_bridge_supervisor)]
Secrets = Annotated[SecretResolver, Depends(get_network_secret_resolver)]
NetworkSettings = Annotated[RuntimeNetworkSettings, Depends(get_runtime_network_settings)]


def get_request_network_cleaner(
    session: DatabaseSession,
    android: AndroidAdapter,
    runtime_adapter: RuntimeAdapter,
    bridge: BridgeSupervisor,
    secrets: Secrets,
    settings: NetworkSettings,
) -> RuntimeNetworkOrchestrator:
    return _orchestrator(
        session, android, runtime_adapter, bridge, secrets, settings
    )


NetworkCleaner = Annotated[
    RuntimeNetworkOrchestrator, Depends(get_request_network_cleaner)
]


@router.get("/{runtime_id}/network", response_model=RuntimeNetworkResponse)
def get_runtime_network(runtime_id: int, session: DatabaseSession) -> RuntimeNetworkResponse:
    _require_runtime(runtime_id, session)
    return _network_response(runtime_id, session)


@router.put("/{runtime_id}/network", response_model=RuntimeNetworkResponse)
def update_runtime_network(
    runtime_id: int,
    payload: RuntimeNetworkUpdate,
    session: DatabaseSession,
    settings: NetworkSettings,
) -> RuntimeNetworkResponse:
    desired = DesiredNetworkInput(
        mode=payload.mode,
        proxy_host=payload.proxy_host,
        proxy_port=payload.proxy_port,
        proxy_username_secret_ref=payload.proxy_username_secret_ref,
        proxy_password_secret_ref=payload.proxy_password_secret_ref,
    )
    try:
        RuntimeNetworkService(session, settings=settings).create_or_update_desired(
            runtime_id,
            desired,
            expected_revision=payload.expected_revision,
        )
    except RuntimeNetworkNotFoundError as error:
        raise HTTPException(status_code=404, detail="Runtime not found") from error
    except RuntimeNetworkRevisionConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (NetworkValidationError, SecretResolutionError, ValueError) as error:
        raise HTTPException(status_code=422, detail="Invalid Runtime network configuration") from error
    except RuntimeNetworkError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _network_response(runtime_id, session)


@router.post("/{runtime_id}/network/apply", response_model=RuntimeNetworkResponse)
def apply_runtime_network(
    runtime_id: int,
    session: DatabaseSession,
    android: AndroidAdapter,
    runtime_adapter: RuntimeAdapter,
    bridge: BridgeSupervisor,
    secrets: Secrets,
    settings: NetworkSettings,
) -> RuntimeNetworkResponse:
    orchestrator = _orchestrator(
        session, android, runtime_adapter, bridge, secrets, settings
    )
    _execute_apply(lambda: orchestrator.apply(runtime_id))
    return _network_response(runtime_id, session)


@router.post("/{runtime_id}/network/clear", response_model=RuntimeNetworkResponse)
def clear_runtime_network(
    runtime_id: int,
    session: DatabaseSession,
    android: AndroidAdapter,
    runtime_adapter: RuntimeAdapter,
    bridge: BridgeSupervisor,
    secrets: Secrets,
    settings: NetworkSettings,
) -> RuntimeNetworkResponse:
    runtime = _require_runtime(runtime_id, session)
    config = session.scalar(
        select(RuntimeNetworkConfig).where(RuntimeNetworkConfig.runtime_id == runtime_id)
    )
    expected = 0 if config is None else config.desired_revision
    if config is None or config.mode != "direct":
        try:
            RuntimeNetworkService(session, settings=settings).switch_to_direct(
                runtime_id,
                expected_revision=expected,
                cleanup_complete=False,
            )
        except RuntimeNetworkRevisionConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except RuntimeNetworkError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
    if runtime.status == "stopped":
        return _network_response(runtime_id, session)
    orchestrator = _orchestrator(
        session, android, runtime_adapter, bridge, secrets, settings
    )
    _execute_apply(lambda: orchestrator.apply(runtime_id))
    return _network_response(runtime_id, session)


@router.get("/{runtime_id}/network/status", response_model=RuntimeNetworkStatusResponse)
def get_runtime_network_status(
    runtime_id: int,
    session: DatabaseSession,
    android: AndroidAdapter,
    runtime_adapter: RuntimeAdapter,
    bridge: BridgeSupervisor,
    secrets: Secrets,
    settings: NetworkSettings,
) -> RuntimeNetworkStatusResponse:
    _require_runtime(runtime_id, session)
    config = session.scalar(select(RuntimeNetworkConfig).where(RuntimeNetworkConfig.runtime_id == runtime_id))
    state = session.get(RuntimeNetworkState, runtime_id)
    if config is None or state is None:
        return RuntimeNetworkStatusResponse(
            runtime_id=runtime_id,
            status="disabled",
            desired_revision=0,
            applied_revision=None,
            checks=NetworkChecks(
                runtime="unmanaged", adb="not_applicable", android_proxy="unknown",
                adb_reverse="unknown", bridge="not_applicable",
            ),
            last_applied_at=None,
            last_verified_at=None,
            error_code=None,
            error_message=None,
        )
    checks = _orchestrator(
        session, android, runtime_adapter, bridge, secrets, settings
    ).checks(runtime_id)
    return RuntimeNetworkStatusResponse(
        runtime_id=runtime_id,
        status=state.status,
        desired_revision=config.desired_revision,
        applied_revision=state.applied_revision,
        checks=NetworkChecks(**checks.__dict__),
        last_applied_at=state.last_applied_at,
        last_verified_at=state.last_verified_at,
        error_code=state.error_code,
        error_message=state.error_message,
    )


def _orchestrator(
    session: Session,
    android: AndroidNetworkAdapter,
    runtime_adapter: RedroidRuntimeAdapter,
    bridge: HostProxyBridgeSupervisor,
    secrets: SecretResolver,
    settings: RuntimeNetworkSettings,
) -> RuntimeNetworkOrchestrator:
    return RuntimeNetworkOrchestrator(
        session,
        runtime_adapter=runtime_adapter,
        android_adapter=android,
        bridge_supervisor=bridge,
        secret_resolver=secrets,
        guard=RuntimeNetworkOperationGuard(settings.lock_directory),
    )


def _execute_apply(operation) -> None:
    try:
        operation()
    except NetworkRuntimeStopped as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (NetworkOperationLockBusy, NetworkRevisionRace) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except NetworkSecretFailure as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (NetworkAdbFailure, NetworkBridgeFailure) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except NetworkApplyError as error:
        detail = str(error)
        code = 404 if detail == "Runtime not found" else 409
        raise HTTPException(status_code=code, detail=detail) from error


def _require_runtime(runtime_id: int, session: Session) -> Runtime:
    runtime = session.get(Runtime, runtime_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Runtime not found")
    return runtime


def _network_response(runtime_id: int, session: Session) -> RuntimeNetworkResponse:
    config = session.scalar(select(RuntimeNetworkConfig).where(RuntimeNetworkConfig.runtime_id == runtime_id))
    state = session.get(RuntimeNetworkState, runtime_id)
    if config is None:
        return RuntimeNetworkResponse(
            runtime_id=runtime_id,
            managed=False,
            mode="direct",
            enabled=False,
            proxy_host=None,
            proxy_port=None,
            credentials=NetworkCredentialsSummary(
                username_configured=False, password_configured=False
            ),
            desired_revision=0,
            applied_revision=None,
            status="disabled",
            observed=NetworkObservedSummary(
                mode="unknown", android_proxy_host=None, android_proxy_port=None,
                reverse_present=None, bridge_status="stopped",
                last_applied_at=None, last_verified_at=None,
            ),
            error_code=None,
            error_message=None,
        )
    assert state is not None
    return RuntimeNetworkResponse(
        runtime_id=runtime_id,
        managed=True,
        mode=config.mode,
        enabled=config.mode == "http_proxy",
        proxy_host=config.proxy_host,
        proxy_port=config.proxy_port,
        credentials=NetworkCredentialsSummary(
            username_configured=config.proxy_username_secret_ref is not None,
            password_configured=config.proxy_password_secret_ref is not None,
        ),
        desired_revision=config.desired_revision,
        applied_revision=state.applied_revision,
        status=state.status,
        observed=NetworkObservedSummary(
            mode=state.observed_mode,
            android_proxy_host=state.observed_android_proxy_host,
            android_proxy_port=state.observed_android_proxy_port,
            reverse_present=state.reverse_present,
            bridge_status=state.bridge_status,
            last_applied_at=state.last_applied_at,
            last_verified_at=state.last_verified_at,
        ),
        error_code=state.error_code,
        error_message=state.error_message,
    )
