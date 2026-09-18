"""Runtime CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Device, Runtime
from app.schemas.runtime import RuntimeCreate, RuntimeList, RuntimeRead, RuntimeUpdate

router = APIRouter(prefix="/runtimes", tags=["runtimes"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _get_runtime_or_404(runtime_id: int, session: Session) -> Runtime:
    runtime = session.get(Runtime, runtime_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Runtime not found")
    return runtime


def _validate_device_id(device_id: int, session: Session) -> None:
    if session.get(Device, device_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")


@router.get("", response_model=RuntimeList)
def list_runtimes(
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RuntimeList:
    """List runtimes using page-based pagination."""
    total = session.scalar(select(func.count()).select_from(Runtime))
    runtimes = session.scalars(
        select(Runtime)
        .order_by(Runtime.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return RuntimeList(
        items=list(runtimes), total=total or 0, page=page, page_size=page_size
    )


@router.get("/{runtime_id}", response_model=RuntimeRead)
def get_runtime(runtime_id: int, session: DatabaseSession) -> Runtime:
    """Return one runtime by ID."""
    return _get_runtime_or_404(runtime_id, session)


@router.post("", response_model=RuntimeRead, status_code=status.HTTP_201_CREATED)
def create_runtime(payload: RuntimeCreate, session: DatabaseSession) -> Runtime:
    """Create a runtime for an existing device."""
    _validate_device_id(payload.device_id, session)
    runtime = Runtime(**payload.model_dump())
    session.add(runtime)
    session.commit()
    session.refresh(runtime)
    return runtime


@router.patch("/{runtime_id}", response_model=RuntimeRead)
def update_runtime(
    runtime_id: int, payload: RuntimeUpdate, session: DatabaseSession
) -> Runtime:
    """Update fields supplied for a runtime."""
    runtime = _get_runtime_or_404(runtime_id, session)
    update_data = payload.model_dump(exclude_unset=True)
    if "device_id" in update_data:
        _validate_device_id(update_data["device_id"], session)
    for field, value in update_data.items():
        setattr(runtime, field, value)
    session.commit()
    session.refresh(runtime)
    return runtime


@router.delete("/{runtime_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_runtime(runtime_id: int, session: DatabaseSession) -> Response:
    """Delete a runtime while preserving and unassigning its accounts."""
    runtime = _get_runtime_or_404(runtime_id, session)
    session.delete(runtime)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
