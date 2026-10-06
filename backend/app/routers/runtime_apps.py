"""Runtime-scoped managed app installation and publishing-readiness APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Runtime, RuntimeAppInstallation
from app.schemas.runtime_app import (
    PublishingReadinessRead,
    RuntimeAppInstallRequest,
    RuntimeAppInstallationRead,
    RuntimeAppOperationRead,
    RuntimeAppsRead,
)
from app.services.redroid_runtime import RedroidRuntimeAdapter, RedroidRuntimeError
from app.services.runtime_apps import RuntimeAppError, RuntimeAppService


router = APIRouter(prefix="/runtimes", tags=["runtime-apps"])
DatabaseSession = Annotated[Session, Depends(get_db)]
RuntimeId = Annotated[int, Path(gt=0)]
AppId = Annotated[int, Path(gt=0)]


def _runtime(session: Session, runtime_id: int) -> Runtime:
    runtime = session.get(Runtime, runtime_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Runtime not found")
    return runtime


def _raise(error: RuntimeAppError) -> None:
    status_code = 404 if error.code in {"MANAGED_APP_NOT_FOUND", "APP_RUNTIME_UNAVAILABLE"} else 409
    raise HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": error.safe_message},
    ) from error


@router.get("/{runtime_id}/apps", response_model=RuntimeAppsRead)
def list_runtime_apps(runtime_id: RuntimeId, session: DatabaseSession) -> RuntimeAppsRead:
    _runtime(session, runtime_id)
    rows = list(session.scalars(
        select(RuntimeAppInstallation)
        .where(RuntimeAppInstallation.runtime_id == runtime_id)
        .order_by(RuntimeAppInstallation.created_at.desc(), RuntimeAppInstallation.id.desc())
    ).all())
    return RuntimeAppsRead(runtime_id=runtime_id, items=rows)


@router.get("/{runtime_id}/publishing-readiness", response_model=PublishingReadinessRead)
def get_publishing_readiness(
    runtime_id: RuntimeId, session: DatabaseSession
) -> PublishingReadinessRead:
    runtime = _runtime(session, runtime_id)
    runtime_ready = False
    if runtime.docker_container_name and runtime.adb_serial and runtime.runtime_type == "redroid":
        try:
            adapter = RedroidRuntimeAdapter()
            runtime_ready = (
                adapter.get_container_status(runtime.docker_container_name) == "running"
                and adapter.check_boot(runtime.docker_container_name)
                and adapter.check_adb(runtime.adb_serial)
            )
        except RedroidRuntimeError:
            runtime_ready = False
    result = RuntimeAppService.readiness(
        session, runtime, runtime_ready=runtime_ready
    )
    return PublishingReadinessRead(**result.__dict__)


@router.post(
    "/{runtime_id}/apps/{app_id}/install",
    response_model=RuntimeAppOperationRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def install_runtime_app(
    runtime_id: RuntimeId,
    app_id: AppId,
    payload: RuntimeAppInstallRequest,
    session: DatabaseSession,
) -> RuntimeAppOperationRead:
    try:
        installation = RuntimeAppService.ensure_desired(
            session,
            runtime_id=runtime_id,
            app_id=app_id,
            version_id=payload.managed_app_version_id,
        )
        runtime = _runtime(session, runtime_id)
        job = (
            RuntimeAppService.enqueue(session, installation, operation="install")
            if runtime.status == "running"
            else None
        )
        session.commit()
        session.refresh(installation)
        return RuntimeAppOperationRead(installation=installation, job_id=job.id if job else None)
    except RuntimeAppError as error:
        session.rollback()
        _raise(error)


@router.post(
    "/{runtime_id}/apps/{app_id}/verify",
    response_model=RuntimeAppOperationRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def verify_runtime_app(
    runtime_id: RuntimeId, app_id: AppId, session: DatabaseSession
) -> RuntimeAppOperationRead:
    try:
        installation = RuntimeAppService.ensure_desired(
            session, runtime_id=runtime_id, app_id=app_id
        )
        runtime = _runtime(session, runtime_id)
        if runtime.status != "running":
            raise RuntimeAppError("RUNTIME_STOPPED", "Runtime is stopped")
        job = RuntimeAppService.enqueue(session, installation, operation="verify")
        session.commit()
        session.refresh(installation)
        return RuntimeAppOperationRead(installation=installation, job_id=job.id)
    except RuntimeAppError as error:
        session.rollback()
        _raise(error)
