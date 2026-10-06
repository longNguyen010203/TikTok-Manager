"""Repository-owned, immutable TikTok selector and screen definitions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TikTokUiProfile
from app.services.tiktok_errors import tiktok_error


@dataclass(frozen=True)
class StructuralConstraint:
    ancestor_class_names: tuple[str, ...] = ()
    descendant_class_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class TikTokElementSelector:
    key: str
    resource_ids: tuple[str, ...] = ()
    content_descriptions: tuple[str, ...] = ()
    normalized_text: tuple[str, ...] = ()
    class_names: tuple[str, ...] = ()
    structure: StructuralConstraint = StructuralConstraint()
    require_enabled: bool = True
    require_clickable: bool | None = None
    require_focusable: bool | None = None
    visual_fallback_key: str | None = None
    coordinate_fallback_key: str | None = None
    actionable: bool = False


@dataclass(frozen=True)
class ScreenDefinition:
    key: str
    required_selectors: tuple[str, ...]
    reinforcing_selectors: tuple[str, ...] = ()
    forbidden_selectors: tuple[str, ...] = ()
    minimum_score: int = 2
    calibrated: bool = True


@dataclass(frozen=True)
class ProfileCoordinate:
    key: str
    screen_key: str
    width: int
    height: int
    orientation: str
    x: int
    y: int


@dataclass(frozen=True)
class TikTokUiProfileDefinition:
    resource_key: str
    package_name: str
    selectors: tuple[TikTokElementSelector, ...]
    screens: tuple[ScreenDefinition, ...]
    coordinates: tuple[ProfileCoordinate, ...] = ()

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


# Deliberately uncalibrated. Phase 3 will replace empty signal definitions with
# observations from the controlled 44.4.3 installation; no resource IDs are guessed.
TRILL_44_4_3_TESTING = TikTokUiProfileDefinition(
    resource_key="trill-44.4.3-testing-v1",
    package_name="com.ss.android.ugc.trill",
    selectors=(),
    screens=tuple(
        ScreenDefinition(key=name, required_selectors=(), calibrated=False)
        for name in ("HOME", "CREATE_ENTRY", "MEDIA_PICKER", "EDIT_MEDIA", "CAPTION", "POST_SETTINGS", "READY_TO_PUBLISH")
    ),
)


class TikTokUiProfileRegistry:
    def __init__(self, definitions: tuple[TikTokUiProfileDefinition, ...] | None = None) -> None:
        values = definitions or (TRILL_44_4_3_TESTING,)
        self._definitions = {item.resource_key: item for item in values}

    def definition_for(self, profile: TikTokUiProfile) -> TikTokUiProfileDefinition:
        definition = self._definitions.get(profile.resource_key)
        if definition is None or definition.fingerprint != profile.profile_fingerprint:
            raise tiktok_error("TIKTOK_UI_PROFILE_MISMATCH")
        return definition

    def select(
        self, session: Session, *, package_name: str, version_code: int | None
    ) -> tuple[TikTokUiProfile, TikTokUiProfileDefinition]:
        rows = session.scalars(
            select(TikTokUiProfile)
            .where(TikTokUiProfile.package_name == package_name, TikTokUiProfile.status != "retired")
            .order_by(TikTokUiProfile.version.desc(), TikTokUiProfile.id.desc())
        ).all()
        if not rows:
            raise tiktok_error("TIKTOK_UI_PROFILE_NOT_FOUND")
        for row in rows:
            if version_code is None:
                continue
            if row.min_version_code is not None and version_code < row.min_version_code:
                continue
            if row.max_version_code is not None and version_code > row.max_version_code:
                continue
            return row, self.definition_for(row)
        raise tiktok_error("TIKTOK_UI_PROFILE_MISMATCH")

    def pinned(self, session: Session, profile_id: int) -> tuple[TikTokUiProfile, TikTokUiProfileDefinition]:
        row = session.get(TikTokUiProfile, profile_id)
        if row is None or row.status == "retired":
            raise tiktok_error("TIKTOK_UI_PROFILE_MISMATCH")
        return row, self.definition_for(row)
