"""Device CRUD endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Device
from app.schemas.device import DeviceCreate, DeviceList, DeviceRead, DeviceUpdate

router = APIRouter(prefix="/devices", tags=["devices"])
DatabaseSession = Annotated[Session, Depends(get_db)]


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
def delete_device(device_id: int, session: DatabaseSession) -> Response:
    """Delete a device and its runtimes while preserving assigned accounts."""
    device = _get_device_or_404(device_id, session)
    session.delete(device)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
