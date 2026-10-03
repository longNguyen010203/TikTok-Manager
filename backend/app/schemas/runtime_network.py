"""Safe request and response schemas for Runtime networking."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class RuntimeNetworkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    mode: Literal["direct", "http_proxy"]
    proxy_host: str | None = None
    proxy_port: int | None = Field(default=None, ge=1, le=65535)
    proxy_username_secret_ref: str | None = None
    proxy_password_secret_ref: str | None = None
    credential_action: Literal["retain", "replace", "clear"] | None = None
    username: SecretStr | None = Field(default=None, min_length=1, max_length=1024)
    password: SecretStr | None = Field(default=None, min_length=1, max_length=4096)
    expected_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_credential_update(self) -> "RuntimeNetworkUpdate":
        plaintext_supplied = self.username is not None or self.password is not None
        references_supplied = (
            self.proxy_username_secret_ref is not None
            or self.proxy_password_secret_ref is not None
        )
        if plaintext_supplied and (
            self.username is None or self.password is None
        ):
            raise ValueError("username and password must be supplied together")
        if references_supplied and (plaintext_supplied or self.credential_action is not None):
            raise ValueError("legacy references cannot be combined with credential updates")
        if self.credential_action == "replace" and not plaintext_supplied:
            raise ValueError("replace requires username and password")
        if self.credential_action in {"retain", "clear"} and plaintext_supplied:
            raise ValueError("credential action does not accept username or password")
        if self.mode == "direct" and (
            plaintext_supplied or references_supplied or self.credential_action is not None
        ):
            raise ValueError("direct mode does not accept credentials")
        return self

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
