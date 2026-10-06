"""Narrow public contracts that create server-owned TikTok actions."""

from pydantic import BaseModel, ConfigDict, Field


class TikTokDetectScreenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    managed_app_id: int = Field(gt=0)


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
