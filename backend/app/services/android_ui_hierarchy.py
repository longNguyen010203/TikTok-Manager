"""Bounded parsing and non-sensitive normalization of UIAutomator XML."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from app.services.tiktok_errors import tiktok_error

_BOUNDS = re.compile(r"^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$")


@dataclass(frozen=True)
class UiParserLimits:
    max_xml_bytes: int = 2 * 1024 * 1024
    max_nodes: int = 10_000
    max_depth: int = 64
    max_text_length: int = 2_048
    max_attribute_length: int = 4_096


@dataclass(frozen=True)
class UiBounds:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def center(self) -> tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)


@dataclass(frozen=True)
class UiNode:
    index: int
    parent_index: int | None
    child_indexes: tuple[int, ...]
    resource_id: str
    text: str
    content_description: str
    class_name: str
    package: str
    bounds: UiBounds
    enabled: bool
    clickable: bool
    focusable: bool
    focused: bool
    selected: bool
    checked: bool
    password: bool


@dataclass(frozen=True)
class UiHierarchy:
    nodes: tuple[UiNode, ...]
    fingerprint: str


class UiHierarchyParser:
    def __init__(self, limits: UiParserLimits | None = None) -> None:
        self.limits = limits or UiParserLimits()

    def parse(self, raw: bytes | str) -> UiHierarchy:
        data = raw.encode("utf-8") if isinstance(raw, str) else raw
        if not data or len(data) > self.limits.max_xml_bytes:
            raise tiktok_error("TIKTOK_UI_DUMP_INVALID")
        lowered = data.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise tiktok_error("TIKTOK_UI_DUMP_INVALID")
        try:
            root = ET.fromstring(data)
        except (ET.ParseError, ValueError) as error:
            raise tiktok_error("TIKTOK_UI_DUMP_INVALID") from error
        mutable: list[dict[str, object]] = []

        def walk(element: ET.Element, parent: int | None, depth: int) -> int:
            if depth > self.limits.max_depth or len(mutable) >= self.limits.max_nodes:
                raise tiktok_error("TIKTOK_UI_DUMP_INVALID")
            for value in element.attrib.values():
                if len(value) > self.limits.max_attribute_length:
                    raise tiktok_error("TIKTOK_UI_DUMP_INVALID")
            bounds_match = _BOUNDS.fullmatch(element.attrib.get("bounds", ""))
            if not bounds_match:
                raise tiktok_error("TIKTOK_UI_DUMP_INVALID")
            left, top, right, bottom = map(int, bounds_match.groups())
            if right <= left or bottom <= top:
                raise tiktok_error("TIKTOK_UI_DUMP_INVALID")
            password = self._boolean(element, "password")
            text = "" if password else element.attrib.get("text", "")
            description = "" if password else element.attrib.get("content-desc", "")
            if len(text) > self.limits.max_text_length or len(description) > self.limits.max_text_length:
                raise tiktok_error("TIKTOK_UI_DUMP_INVALID")
            index = len(mutable)
            mutable.append({
                "index": index, "parent_index": parent, "child_indexes": [],
                "resource_id": element.attrib.get("resource-id", ""), "text": text,
                "content_description": description, "class_name": element.attrib.get("class", ""),
                "package": element.attrib.get("package", ""),
                "bounds": UiBounds(left, top, right, bottom),
                "enabled": self._boolean(element, "enabled"), "clickable": self._boolean(element, "clickable"),
                "focusable": self._boolean(element, "focusable"), "focused": self._boolean(element, "focused"),
                "selected": self._boolean(element, "selected"), "checked": self._boolean(element, "checked"),
                "password": password,
            })
            children = [walk(child, index, depth + 1) for child in element if child.tag == "node"]
            mutable[index]["child_indexes"] = tuple(children)
            return index

        roots = [root] if root.tag == "node" else [child for child in root if child.tag == "node"]
        if not roots:
            raise tiktok_error("TIKTOK_UI_DUMP_INVALID")
        for item in roots:
            walk(item, None, 1)
        nodes = tuple(UiNode(**item) for item in mutable)
        safe = [
            [n.resource_id, n.class_name, n.package, n.bounds.left, n.bounds.top,
             n.bounds.right, n.bounds.bottom, n.enabled, n.clickable, bool(n.text),
             bool(n.content_description), n.password, n.parent_index, n.child_indexes]
            for n in nodes
        ]
        fingerprint = hashlib.sha256(json.dumps(safe, separators=(",", ":")).encode()).hexdigest()
        return UiHierarchy(nodes, fingerprint)

    @staticmethod
    def _boolean(element: ET.Element, name: str) -> bool:
        value = element.attrib.get(name, "false")
        if value not in {"true", "false"}:
            raise tiktok_error("TIKTOK_UI_DUMP_INVALID")
        return value == "true"
