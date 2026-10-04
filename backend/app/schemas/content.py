"""Safe request and response schemas for the reusable content library."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ContentAssetType = Literal["video", "image", "audio", "other"]
ContentAssetStatus = Literal["processing", "ready", "invalid", "archived", "deleted"]
ContentAssetSource = Literal["upload", "promoted_artifact", "generated", "imported"]


class ContentVersionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    version_number: int = Field(gt=0)
    original_filename: str
    detected_mime_type: str
    canonical_extension: str
    processing_status: Literal["processing", "ready", "invalid"]
    size_bytes: int = Field(gt=0)
    sha256: str
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None
    codec: str | None = None
    container: str | None = None
    frame_rate_numerator: int | None = None
    frame_rate_denominator: int | None = None
    audio_present: bool | None = None
    bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    orientation: int | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    processed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class ContentAssetRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    asset_type: ContentAssetType
    display_name: str
    notes: str | None
    source: ContentAssetSource
    status: ContentAssetStatus
    tags: list[str]
    current_version: ContentVersionRead | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    deleted_at: datetime | None
    total_deliveries: int = Field(ge=0)
    latest_delivery_status: str | None = None
    last_successful_delivery_at: datetime | None = None


class ContentAssetDetail(ContentAssetRead):
    versions: list[ContentVersionRead]


class ContentAssetList(BaseModel):
    items: list[ContentAssetRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class ContentAssetPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)
    tags: list[str] | None = Field(default=None, max_length=20)
    archived: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ContentAssetPatch":
        if not self.model_fields_set:
            raise ValueError("At least one content metadata field is required")
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("display_name cannot be null")
        return self


class ContentDeliveryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    runtime_id: int = Field(gt=0)
    version_id: int | None = Field(default=None, gt=0)
    filename: str | None = Field(default=None, min_length=1, max_length=255)
    import_media: bool = True
    allow_repeat: bool = False
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class ContentDeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(gt=0)
    content_asset_id: int = Field(gt=0)
    content_asset_version_id: int = Field(gt=0)
    content_variant_id: int | None = None
    runtime_id: int | None = None
    runtime_id_snapshot: int = Field(gt=0)
    job_id: int = Field(gt=0)
    status: Literal["pending", "delivering", "succeeded", "failed", "cancelled"]
    import_media: bool
    remote_filename: str
    remote_path: str
    media_uri: str | None = None
    delivered_sha256: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class ContentDeliveryCreateRead(BaseModel):
    delivery: ContentDeliveryRead
    job_status: str
    created: bool


class ContentDeliveryList(BaseModel):
    items: list[ContentDeliveryRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
