"""Conservative ContentDelivery-to-picker identity resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.adb_executor import AdbMediaRecord
from app.services.android_ui_hierarchy import UiBounds, UiHierarchy, UiNode
from app.services.tiktok_errors import tiktok_error
from app.services.tiktok_screen_resolver import TikTokSelectorResolver
from app.services.tiktok_ui_profiles import TikTokUiProfileDefinition

_DURATION = re.compile(r"^(?:(\d+):)?(\d{2}):(\d{2})$")
_MEDIA_MIME_PREFIXES = ("image/", "video/", "audio/")


@dataclass(frozen=True)
class ResolvedMediaIdentity:
    media_id: int
    display_name: str
    node_index: int
    bounds: UiBounds
    snapshot_fingerprint: str
    resolution_method: str
    duration_seconds: int | None


class MediaIdentityResolver:
    """Resolve only independently evidenced media; grid order is never identity."""

    def __init__(self, selectors: TikTokSelectorResolver | None = None) -> None:
        self.selectors = selectors or TikTokSelectorResolver()

    def resolve(
        self,
        hierarchy: UiHierarchy,
        profile: TikTokUiProfileDefinition,
        *,
        expected: AdbMediaRecord,
        media_inventory: tuple[AdbMediaRecord, ...],
    ) -> ResolvedMediaIdentity:
        selector = next(
            (item for item in profile.selectors if item.key == "picker_grid"),
            None,
        )
        if selector is None:
            raise tiktok_error("TIKTOK_UI_PROFILE_MISMATCH")
        grid = self.selectors.resolve(hierarchy, selector)
        grid_node = hierarchy.nodes[grid.node_index]
        tiles = tuple(
            hierarchy.nodes[index]
            for index in grid_node.child_indexes
            if self._is_tile(hierarchy.nodes[index])
        )
        if not tiles:
            raise tiktok_error("TIKTOK_MEDIA_NOT_FOUND")

        # Prefer direct delivery-specific semantic evidence if TikTok exposes
        # it in a future compatible hierarchy.
        named = tuple(
            tile for tile in tiles
            if expected.display_name in self._descendant_strings(hierarchy, tile)
        )
        if len(named) == 1:
            return self._result(
                hierarchy, named[0], expected,
                method="exact_display_name",
            )
        if len(named) > 1:
            raise tiktok_error("TIKTOK_MEDIA_AMBIGUOUS")

        eligible = tuple(
            item for item in media_inventory
            if item.mime_type is not None
            and item.mime_type.startswith(_MEDIA_MIME_PREFIXES)
            and item.size_bytes is not None
            and item.size_bytes > 0
        )
        target_matches = tuple(
            item for item in eligible
            if item.media_id == expected.media_id
            and item.display_name == expected.display_name
            and item.size_bytes == expected.size_bytes
            and item.mime_type == expected.mime_type
        )
        if len(target_matches) != 1 or len(eligible) != 1 or len(tiles) != 1:
            raise tiktok_error("TIKTOK_MEDIA_AMBIGUOUS")

        tile_duration = self._duration_seconds(hierarchy, tiles[0])
        if expected.mime_type and expected.mime_type.startswith("video/"):
            expected_duration = expected.duration_ms
            if (
                expected_duration is None
                or tile_duration is None
                or tile_duration != expected_duration // 1000
            ):
                raise tiktok_error("TIKTOK_MEDIA_AMBIGUOUS")
        return self._result(
            hierarchy, tiles[0], expected,
            method="exclusive_media_inventory_duration",
            duration_seconds=tile_duration,
        )

    @staticmethod
    def verify_inventory(
        *, expected: AdbMediaRecord,
        media_inventory: tuple[AdbMediaRecord, ...],
    ) -> str:
        """Verify one backend-resolved MediaStore record without picker order."""
        matches = tuple(
            item for item in media_inventory if item.media_id == expected.media_id
        )
        if not matches:
            raise tiktok_error("TIKTOK_MEDIA_NOT_FOUND")
        if len(matches) != 1:
            raise tiktok_error("TIKTOK_MEDIA_AMBIGUOUS")
        observed = matches[0]
        if (
            observed.display_name != expected.display_name
            or observed.size_bytes != expected.size_bytes
            or observed.mime_type != expected.mime_type
            or (
                expected.duration_ms is not None
                and observed.duration_ms != expected.duration_ms
            )
        ):
            raise tiktok_error("TIKTOK_MEDIA_AMBIGUOUS")
        return "exact_mediastore_record"

    @staticmethod
    def _is_tile(node: UiNode) -> bool:
        return (
            node.class_name == "android.widget.FrameLayout"
            and node.enabled
            and node.clickable
            and node.bounds.right > node.bounds.left
            and node.bounds.bottom > node.bounds.top
        )

    @staticmethod
    def _descendants(hierarchy: UiHierarchy, node: UiNode) -> tuple[UiNode, ...]:
        output: list[UiNode] = []
        pending = list(node.child_indexes)
        while pending:
            child = hierarchy.nodes[pending.pop()]
            output.append(child)
            pending.extend(child.child_indexes)
        return tuple(output)

    def _descendant_strings(self, hierarchy: UiHierarchy, node: UiNode) -> set[str]:
        values: set[str] = set()
        for descendant in self._descendants(hierarchy, node):
            if descendant.text:
                values.add(descendant.text)
            if descendant.content_description:
                values.add(descendant.content_description)
        return values

    def _duration_seconds(self, hierarchy: UiHierarchy, node: UiNode) -> int | None:
        values: list[int] = []
        for descendant in self._descendants(hierarchy, node):
            match = _DURATION.fullmatch(descendant.text.strip())
            if match is None:
                continue
            hours = int(match.group(1) or 0)
            values.append(hours * 3600 + int(match.group(2)) * 60 + int(match.group(3)))
        return values[0] if len(values) == 1 else None

    @staticmethod
    def _result(
        hierarchy: UiHierarchy,
        tile: UiNode,
        expected: AdbMediaRecord,
        *,
        method: str,
        duration_seconds: int | None = None,
    ) -> ResolvedMediaIdentity:
        return ResolvedMediaIdentity(
            media_id=expected.media_id,
            display_name=expected.display_name,
            node_index=tile.index,
            bounds=tile.bounds,
            snapshot_fingerprint=hierarchy.fingerprint,
            resolution_method=method,
            duration_seconds=duration_seconds,
        )
