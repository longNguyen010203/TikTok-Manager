"""Read-only Dashboard projections."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.dashboard import DashboardTopology
from app.services.system_topology import build_system_topology

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/topology", response_model=DashboardTopology)
def get_dashboard_topology(session: DatabaseSession) -> DashboardTopology:
    """Return a fresh normalized graph of all visible topology entities."""
    return build_system_topology(session)
