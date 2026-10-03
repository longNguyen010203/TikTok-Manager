"""Safe request and response schemas for Runtime networking."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RuntimeNetworkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    mode: Literal["direct", "http_proxy"]
    proxy_host: str | None = None
    proxy_port: int | None = Field(default=None, ge=1, le=65535)
    proxy_username_secret_ref: str | None = None
    proxy_password_secret_ref: str | None = None
    expected_revision: int = Field(ge=0)

class NetworkCredentialsSummary(BaseModel):
    username_configured: bool
    password_configured: bool


class NetworkObservedSummary(BaseModel):
    mode: str
    android_proxy_host: str | None
    android_proxy_port: int | None
    reverse_present: bool | None
    bridge_status: str
    last_applied_at: datetime | None
    last_verified_at: datetime | None


class RuntimeNetworkResponse(BaseModel):
    runtime_id: int
    managed: bool
    mode: str
    enabled: bool
    proxy_host: str | None
    proxy_port: int | None
    credentials: NetworkCredentialsSummary
    desired_revision: int
    applied_revision: int | None
    status: str
    observed: NetworkObservedSummary
    error_code: str | None
    error_message: str | None


class NetworkChecks(BaseModel):
    runtime: str
    adb: str
    android_proxy: str
    adb_reverse: str
    bridge: str
    connectivity: str = "not_run"


class RuntimeNetworkStatusResponse(BaseModel):
    runtime_id: int
    status: str
    desired_revision: int
    applied_revision: int | None
    checks: NetworkChecks
    last_applied_at: datetime | None
    last_verified_at: datetime | None
    error_code: str | None
    error_message: str | None
