"""Deterministic selector resolution and conservative TikTok screen classification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.services.android_ui_hierarchy import UiHierarchy, UiNode
from app.services.tiktok_errors import tiktok_error
from app.services.tiktok_ui_profiles import TikTokElementSelector, TikTokUiProfileDefinition


class TikTokScreen(str, Enum):
    UNKNOWN = "UNKNOWN"
    HOME = "HOME"
    CREATE_ENTRY = "CREATE_ENTRY"
    CAMERA_CREATE = "CAMERA_CREATE"
    MEDIA_PICKER = "MEDIA_PICKER"
    EDIT_MEDIA = "EDIT_MEDIA"
    CAPTION = "CAPTION"
    POST_SETTINGS = "POST_SETTINGS"
    READY_TO_PUBLISH = "READY_TO_PUBLISH"


@dataclass(frozen=True)
class ResolvedUiElement:
    selector_key: str
    node_index: int
    bounds: object
    method: str
    snapshot_fingerprint: str
    confidence: str
    actionable: bool


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


class TikTokSelectorResolver:
    def resolve(self, hierarchy: UiHierarchy, selector: TikTokElementSelector) -> ResolvedUiElement:
        method, matches = self.matches(hierarchy, selector)
        if len(matches) > 1:
            raise tiktok_error("TIKTOK_ELEMENT_AMBIGUOUS")
        if len(matches) == 1:
            node = matches[0]
            return ResolvedUiElement(selector.key, node.index, node.bounds, method, hierarchy.fingerprint, "exact", selector.actionable)
        raise tiktok_error("TIKTOK_ELEMENT_NOT_FOUND")

    def matches(self, hierarchy: UiHierarchy, selector: TikTokElementSelector) -> tuple[str, tuple[UiNode, ...]]:
        """Return the highest-priority observed matches without requiring uniqueness.

        Screen classification uses presence, while mutation actions use ``resolve``
        and therefore still require exactly one target. Class/structure is only a
        selector by itself; it is not a broad fallback after configured semantic
        identifiers disappear from a changed UI.
        """
        candidates = [
            node for node in hierarchy.nodes
            if self._state_matches(node, selector)
            and self._structure_matches(hierarchy, node, selector)
        ]
        stages = (
            ("resource_id", bool(selector.resource_ids), lambda n: n.resource_id in selector.resource_ids),
            ("content_description", bool(selector.content_descriptions), lambda n: _normalized(n.content_description) in {_normalized(v) for v in selector.content_descriptions}),
            ("normalized_text", bool(selector.normalized_text), lambda n: _normalized(n.text) in {_normalized(v) for v in selector.normalized_text}),
        )
        has_semantic_identifier = any(configured for _, configured, _ in stages)
        for method, configured, predicate in stages:
            if not configured:
                continue
            matches = tuple(node for node in candidates if predicate(node))
            if matches:
                return method, matches
        if not has_semantic_identifier and selector.class_names:
            matches = tuple(node for node in candidates if node.class_name in selector.class_names)
            if matches:
                return "class_structure", matches
        return "none", ()

    def match_count(self, hierarchy: UiHierarchy, selector: TikTokElementSelector) -> int:
        return len(self.matches(hierarchy, selector)[1])

    def exists(self, hierarchy: UiHierarchy, selector: TikTokElementSelector) -> bool:
        return self.match_count(hierarchy, selector) > 0

    @staticmethod
    def _state_matches(node: UiNode, selector: TikTokElementSelector) -> bool:
        return (
            (not selector.class_names or node.class_name in selector.class_names)
            and
            (not selector.require_enabled or node.enabled)
            and (selector.require_clickable is None or node.clickable == selector.require_clickable)
            and (selector.require_focusable is None or node.focusable == selector.require_focusable)
        )

    @staticmethod
    def _structure_matches(hierarchy: UiHierarchy, node: UiNode, selector: TikTokElementSelector) -> bool:
        ancestor_classes: set[str] = set()
        parent = node.parent_index
        while parent is not None:
            ancestor = hierarchy.nodes[parent]
            ancestor_classes.add(ancestor.class_name)
            parent = ancestor.parent_index
        descendant_classes: set[str] = set()
        pending = list(node.child_indexes)
        while pending:
            child = hierarchy.nodes[pending.pop()]
            descendant_classes.add(child.class_name)
            pending.extend(child.child_indexes)
        return (
            set(selector.structure.ancestor_class_names).issubset(ancestor_classes)
            and set(selector.structure.descendant_class_names).issubset(descendant_classes)
        )


class TikTokScreenResolver:
    def __init__(self, selector_resolver: TikTokSelectorResolver | None = None, *, margin: int = 1) -> None:
        self.selectors = selector_resolver or TikTokSelectorResolver()
        self.margin = margin

    def classify(self, hierarchy: UiHierarchy, profile: TikTokUiProfileDefinition, foreground_package: str) -> TikTokScreen:
        if foreground_package != profile.package_name:
            raise tiktok_error("TIKTOK_APP_NOT_FOREGROUND")
        selector_map = {item.key: item for item in profile.selectors}
        scored: list[tuple[int, str]] = []
        for screen in profile.screens:
            if not screen.calibrated or len(screen.required_selectors) < 2:
                continue
            try:
                required = all(self.selectors.exists(hierarchy, selector_map[key]) for key in screen.required_selectors)
                forbidden = any(self.selectors.exists(hierarchy, selector_map[key]) for key in screen.forbidden_selectors)
                if not required or forbidden:
                    continue
                score = len(screen.required_selectors) * 2 + sum(
                    self.selectors.exists(hierarchy, selector_map[key]) for key in screen.reinforcing_selectors
                )
            except KeyError:
                continue
            if score >= screen.minimum_score:
                scored.append((score, screen.key))
        scored.sort(reverse=True)
        if not scored or (len(scored) > 1 and scored[0][0] - scored[1][0] < self.margin):
            return TikTokScreen.UNKNOWN
        try:
            return TikTokScreen(scored[0][1])
        except ValueError:
            return TikTokScreen.UNKNOWN
