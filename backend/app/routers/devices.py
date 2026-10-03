"""Device CRUD endpoints."""

import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Device,
    RedroidProvisioning,
    RuntimeNetworkConfig,
    RuntimeNetworkState,
)
from app.schemas.device import (
    DeviceCreate,
    DeviceLifecycleStatus,
    DeviceList,
    DeviceRead,
    DeviceScreenStatus,
    DeviceUpdate,
)
from app.services.device_lifecycle import (
    DeviceLifecycleError,
    DeviceLifecycleService,
    get_redroid_target,
)
from app.services.device_screen import (
    DeviceScreenError,
    ScreenProcessManager,
    ScreenProcessState,
)
from app.services.redroid_runtime import (
    RedroidBootTimeoutError,
    RedroidRuntimeAdapter,
    RedroidRuntimeError,
)
from app.routers.runtime_networks import NetworkCleaner
from app.services.runtime_network_orchestration import (
    NetworkApplyError,
    RuntimeNetworkOrchestrator,
)

router = APIRouter(prefix="/devices", tags=["devices"])
DatabaseSession = Annotated[Session, Depends(get_db)]
logger = logging.getLogger(__name__)


def get_redroid_runtime_adapter() -> RedroidRuntimeAdapter:
    """Provide the local Redroid adapter for lifecycle operations."""
    return RedroidRuntimeAdapter()


RuntimeAdapter = Annotated[
    RedroidRuntimeAdapter, Depends(get_redroid_runtime_adapter)
]

screen_process_manager = ScreenProcessManager()


def get_screen_process_manager() -> ScreenProcessManager:
    """Provide the process-local scrcpy session registry."""
    return screen_process_manager


ScreenManager = Annotated[ScreenProcessManager, Depends(get_screen_process_manager)]


def _get_device_or_404(device_id: int, session: Session) -> Device:
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.get("", response_model=DeviceList)
def list_devices(
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DeviceList:
    """List devices using page-based pagination."""
    total = session.scalar(select(func.count()).select_from(Device))
    devices = session.scalars(
        select(Device)
        .order_by(Device.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return DeviceList(
        items=list(devices), total=total or 0, page=page, page_size=page_size
    )


@router.get("/{device_id}", response_model=DeviceRead)
def get_device(device_id: int, session: DatabaseSession) -> Device:
    """Return one device by ID."""
    return _get_device_or_404(device_id, session)


@router.get("/{device_id}/status", response_model=DeviceLifecycleStatus)
def get_device_status(
    device_id: int, session: DatabaseSession, adapter: RuntimeAdapter
) -> DeviceLifecycleStatus:
    """Inspect and reconcile a Device's Redroid runtime state."""
    device = _get_device_or_404(device_id, session)
    service = DeviceLifecycleService(session, adapter)
    return _execute_lifecycle(lambda: service.status(device))


@router.post("/{device_id}/start", response_model=DeviceLifecycleStatus)
def start_device(
    device_id: int,
    session: DatabaseSession,
    adapter: RuntimeAdapter,
    network_cleaner: NetworkCleaner,
) -> DeviceLifecycleStatus:
    """Start a Device's Redroid runtime and wait for readiness."""
    device = _get_device_or_404(device_id, session)
    service = DeviceLifecycleService(session, adapter)
    result = _execute_lifecycle(lambda: service.start(device))
    _reconcile_network_after_ready(device, session, network_cleaner)
    return result


@router.post("/{device_id}/stop", response_model=DeviceLifecycleStatus)
def stop_device(
    device_id: int, session: DatabaseSession, adapter: RuntimeAdapter
) -> DeviceLifecycleStatus:
    """Stop a Device's Redroid container without deleting it."""
    device = _get_device_or_404(device_id, session)
    service = DeviceLifecycleService(session, adapter)
    return _execute_lifecycle(lambda: service.stop(device))


@router.post("/{device_id}/restart", response_model=DeviceLifecycleStatus)
def restart_device(
    device_id: int,
    session: DatabaseSession,
    adapter: RuntimeAdapter,
    network_cleaner: NetworkCleaner,
) -> DeviceLifecycleStatus:
    """Restart a Device's Redroid runtime and wait for readiness."""
    device = _get_device_or_404(device_id, session)
    service = DeviceLifecycleService(session, adapter)
    result = _execute_lifecycle(lambda: service.restart(device))
    _reconcile_network_after_ready(device, session, network_cleaner)
    return result


@router.post("/{device_id}/screen/open", response_model=DeviceScreenStatus)
def open_device_screen(
    device_id: int, session: DatabaseSession, manager: ScreenManager
) -> DeviceScreenStatus:
    """Launch scrcpy for a Device without waiting for it to exit."""
    device = _get_device_or_404(device_id, session)
    return _execute_screen(
        lambda: _open_screen(device, manager)
    )


@router.post("/{device_id}/screen/close", response_model=DeviceScreenStatus)
def close_device_screen(
    device_id: int, session: DatabaseSession, manager: ScreenManager
) -> DeviceScreenStatus:
    """Terminate only the tracked scrcpy process for a Device."""
    device = _get_device_or_404(device_id, session)
    return _execute_screen(
        lambda: _close_screen(device, manager)
    )


@router.get("/{device_id}/screen/status", response_model=DeviceScreenStatus)
def get_device_screen_status(
    device_id: int, session: DatabaseSession, manager: ScreenManager
) -> DeviceScreenStatus:
    """Return the state of a Device's tracked scrcpy process."""
    device = _get_device_or_404(device_id, session)
    return _execute_screen(
        lambda: _screen_status(device, manager)
    )


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceCreate, session: DatabaseSession) -> Device:
    """Create a device."""
    device = Device(**payload.model_dump())
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


@router.patch("/{device_id}", response_model=DeviceRead)
def update_device(
    device_id: int, payload: DeviceUpdate, session: DatabaseSession
) -> Device:
    """Update fields supplied for a device."""
    device = _get_device_or_404(device_id, session)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(device, field, value)
    session.commit()
    session.refresh(device)
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: int, session: DatabaseSession, network_cleaner: NetworkCleaner
) -> Response:
    """Delete a device and its runtimes while preserving assigned accounts."""
    device = _get_device_or_404(device_id, session)
    managed = session.scalar(
        select(RedroidProvisioning).where(
            RedroidProvisioning.device_id == device.id
        )
    )
    if managed is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Provisioned managed devices must be removed through "
                f"POST /redroid-provisionings/{managed.id}/deprovision"
            ),
        )
    try:
        for runtime in device.runtimes:
            network_cleaner.cleanup_before_delete(runtime.id)
    except NetworkApplyError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    session.delete(device)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _execute_lifecycle(
    operation: Callable[[], DeviceLifecycleStatus],
) -> DeviceLifecycleStatus:
    try:
        return operation()
    except RedroidBootTimeoutError as error:
        raise HTTPException(status_code=504, detail=str(error)) from error
    except RedroidRuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except DeviceLifecycleError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def _reconcile_network_after_ready(
    device: Device,
    session: Session,
    network_orchestrator: RuntimeNetworkOrchestrator,
) -> None:
    """Reapply only network intent that has ephemeral state to restore."""
    target = get_redroid_target(device)
    config = session.scalar(
        select(RuntimeNetworkConfig).where(
            RuntimeNetworkConfig.runtime_id == target.runtime.id
        )
    )
    state = session.get(RuntimeNetworkState, target.runtime.id)
    if config is None or state is None:
        return
    if config.mode == "direct" and state.applied_revision == config.desired_revision:
        return
    try:
        network_orchestrator.apply(target.runtime.id)
    except Exception:
        # Lifecycle readiness remains independent. The network orchestrator
        # persists its own safe failure state for the status API.
        logger.error(
            "Network reconciliation after lifecycle start failed for Runtime %s",
            target.runtime.id,
        )


def _open_screen(device: Device, manager: ScreenProcessManager) -> DeviceScreenStatus:
    target = get_redroid_target(device)
    return _screen_response(
        manager.open(device.id, target.runtime.id, target.adb_serial)
    )


def _close_screen(device: Device, manager: ScreenProcessManager) -> DeviceScreenStatus:
    target = get_redroid_target(device)
    return _screen_response(
        manager.close(device.id, target.runtime.id, target.adb_serial)
    )


def _screen_status(device: Device, manager: ScreenProcessManager) -> DeviceScreenStatus:
    target = get_redroid_target(device)
    return _screen_response(
        manager.status(device.id, target.runtime.id, target.adb_serial)
    )


def _screen_response(state: ScreenProcessState) -> DeviceScreenStatus:
    return DeviceScreenStatus(
        device_id=state.device_id,
        runtime_id=state.runtime_id,
        adb_serial=state.adb_serial,
        status="open" if state.is_open else "closed",
        process_id=state.process_id,
    )


def _execute_screen(
    operation: Callable[[], DeviceScreenStatus],
) -> DeviceScreenStatus:
    try:
        return operation()
    except DeviceLifecycleError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except DeviceScreenError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
