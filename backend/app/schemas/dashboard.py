"""Read-only Dashboard topology response schemas."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class TopologySummary(BaseModel):
    devices: int
    runtimes: int
    accounts: int
    ready_accounts: int
    not_ready_accounts: int
    attention_accounts: int


class DeviceNodeMetadata(BaseModel):
    name: str
    status: str
    platform: str
    device_type: str
    os_version: str
    runtime_count: int


class RuntimeNodeMetadata(BaseModel):
    name: str
    status: str
    runtime_type: str
    device_id: int
    assigned_account_count: int
    last_seen_at: datetime | None


class AccountNodeMetadata(BaseModel):
    display_name: str
    status: str
    registration_state: str
    registration_ready: bool
    registration_completed_at: datetime | None
    health_status: str
    username: str | None
    runtime_id: int | None
    device_id: int | None
    secret_present: bool


class DeviceTopologyNode(BaseModel):
    id: str
    type: Literal["device"]
    entity_id: int
    label: str
    status: str
    metadata: DeviceNodeMetadata


class RuntimeTopologyNode(BaseModel):
    id: str
    type: Literal["runtime"]
    entity_id: int
    label: str
    status: str
    metadata: RuntimeNodeMetadata


class AccountTopologyNode(BaseModel):
    id: str
    type: Literal["account"]
    entity_id: int
    label: str
    status: str
    metadata: AccountNodeMetadata


TopologyNode = Annotated[
    DeviceTopologyNode | RuntimeTopologyNode | AccountTopologyNode,
    Field(discriminator="type"),
]


class TopologyEdge(BaseModel):
    id: str
    source: str
    target: str
    type: Literal["hosts", "assigned"]


class DashboardTopology(BaseModel):
    generated_at: datetime
    summary: TopologySummary
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]
