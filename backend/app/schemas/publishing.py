from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PublishingSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    workflow_id: int
    account_id: int | None
    account_id_snapshot: int
    runtime_id: int | None
    runtime_id_snapshot: int
    content_asset_version_id: int
    managed_app_id: int
    managed_app_version_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    prepared_at: datetime | None
    approved_at: datetime | None
    error_code: str | None
    error_message: str | None


class PublishingSessionList(BaseModel):
    items: list[PublishingSessionRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
