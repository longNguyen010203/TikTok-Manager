"""Narrow public contracts that create server-owned TikTok actions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TikTokDetectScreenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    managed_app_id: int = Field(gt=0)


class TikTokOpenCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    managed_app_id: int = Field(gt=0)


class TikTokOpenMediaPickerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    managed_app_id: int = Field(gt=0)


class TikTokOpenCaptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    managed_app_id: int = Field(gt=0)


class TikTokSetCaptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    managed_app_id: int = Field(gt=0)
    caption: str = Field(max_length=512)


class TikTokSetPostOptionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    managed_app_id: int = Field(gt=0)
    privacy: Literal["everyone", "only_you"] | None


class TikTokPreparePublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    managed_app_id: int = Field(gt=0)
    content_delivery_id: int = Field(gt=0)
    expected_caption: str = Field(max_length=512)
    expected_privacy: Literal["everyone", "only_you"]


class TikTokSelectMediaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    managed_app_id: int = Field(gt=0)
    content_delivery_id: int = Field(gt=0)


class TikTokDetectScreenResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    screen: str
    foreground_package: str
    profile_id: int = Field(gt=0)
    profile_version: int = Field(gt=0)
    profile_fingerprint: str = Field(min_length=64, max_length=64)
    node_count: int = Field(ge=0)
    display_category: str
    changed: bool = False


class TikTokOpenCreateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    screen_before: str
    screen_after: str
    foreground_package: str
    profile_id: int = Field(gt=0)
    profile_version: int = Field(gt=0)
    profile_fingerprint: str = Field(min_length=64, max_length=64)
    selector_key: str | None = None
    resolution_method: str | None = None
    changed: bool


class TikTokOpenMediaPickerResult(TikTokOpenCreateResult):
    pass


class TikTokSelectMediaResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_delivery_id: int = Field(gt=0)
    screen_before: str
    screen_after: str
    foreground_package: str
    foreground_activity: str | None = None
    profile_id: int = Field(gt=0)
    profile_version: int = Field(gt=0)
    profile_fingerprint: str = Field(min_length=64, max_length=64)
    resolution_method: str
    changed: bool
    tap_dispatched: bool
    calibration_required: bool
    node_count: int = Field(ge=0)
    hierarchy_fingerprint: str = Field(min_length=64, max_length=64)


class TikTokOpenCaptionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    screen_before: str
    screen_after: str
    foreground_package: str
    foreground_activity: str | None = None
    profile_id: int = Field(gt=0)
    profile_version: int = Field(gt=0)
    profile_fingerprint: str = Field(min_length=64, max_length=64)
    selector_key: str | None = None
    resolution_method: str
    changed: bool
    tap_dispatched: bool
    calibration_required: bool
    node_count: int = Field(ge=0)
    hierarchy_fingerprint: str = Field(min_length=64, max_length=64)


class TikTokSetCaptionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    screen_before: str
    screen_after: str
    foreground_package: str
    profile_id: int = Field(gt=0)
    profile_version: int = Field(gt=0)
    profile_fingerprint: str = Field(min_length=64, max_length=64)
    changed: bool
    caption_length: int = Field(ge=0, le=150)
    verification: bool
    keyboard_appeared: bool
    hierarchy_fingerprint: str = Field(min_length=64, max_length=64)


class TikTokSetPostOptionsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    screen_before: str
    screen_after: str
    foreground_package: str
    profile_id: int = Field(gt=0)
    profile_version: int = Field(gt=0)
    profile_fingerprint: str = Field(min_length=64, max_length=64)
    changed: bool
    tap_dispatched: bool
    calibration_required: bool
    privacy: str | None
    verification: bool
    node_count: int = Field(ge=0)
    hierarchy_fingerprint: str = Field(min_length=64, max_length=64)


class TikTokPreparePublishResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prepared: bool
    screen: str
    content_delivery_id: int = Field(gt=0)
    caption_verified: bool
    privacy_verified: bool
    privacy: Literal["everyone", "only_you"]
    media_verified: bool
    media_resolution_method: str
    post_control_present: bool
    drafts_control_present: bool
    changed: bool = False
    foreground_package: str
    profile_id: int = Field(gt=0)
    profile_version: int = Field(gt=0)
    profile_fingerprint: str = Field(min_length=64, max_length=64)
    node_count: int = Field(ge=0)
    hierarchy_fingerprint: str = Field(min_length=64, max_length=64)
