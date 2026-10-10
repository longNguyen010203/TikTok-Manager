"""Internal-only Android UI sessions with one exact Runtime lock."""

from __future__ import annotations

import re
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator

from sqlalchemy.orm import Session

from app.services.adb_executor import AdbExecutor, AdbForegroundApp, AdbMediaRecord
from app.services.android_automation import AutomationReadinessService, RuntimeTarget, RuntimeTargetResolver, ScreenSessionInspector
from app.services.android_ui_hierarchy import UiHierarchy, UiHierarchyParser
from app.services.automation_errors import AutomationError, automation_error
from app.services.runtime_operation_lock import RuntimeOperationGuard, RuntimeOperationLockBusy
from app.services.tiktok_errors import TikTokActionError, tiktok_error
from app.services.tiktok_screen_resolver import ResolvedUiElement
from app.services.tiktok_ui_profiles import ProfileCoordinate


@dataclass(frozen=True)
class DisplayState:
    width: int
    height: int
    rotation: int
    orientation: str
    category: str


class TextEntryProvider:
    def validate(self, value: str) -> None: ...
    def enter(self, adb: AdbExecutor, serial: str, value: str) -> None: ...


class AsciiTextEntryProvider(TextEntryProvider):
    _SAFE = re.compile(r"^[A-Za-z0-9 .,!?@_+\-]{1,320}$")

    def validate(self, value: str) -> None:
        if value and not self._SAFE.fullmatch(value):
            raise tiktok_error("TIKTOK_TEXT_UNSUPPORTED")

    def enter(self, adb: AdbExecutor, serial: str, value: str) -> None:
        self.validate(value)
        # Android input uses %s for spaces; this remains one argv element.
        adb.input_text(serial, value.replace(" ", "%s"))


class AndroidUiSession:
    def __init__(self, target: RuntimeTarget, adb: AdbExecutor, parser: UiHierarchyParser, text: TextEntryProvider) -> None:
        self.target = target
        self.adb = adb
        self.parser = parser
        self.text = text

    def dump_ui_hierarchy(self) -> UiHierarchy:
        try:
            return self.parser.parse(self.adb.dump_ui_hierarchy(self.target.adb_serial))
        except TikTokActionError:
            raise
        except Exception as error:
            raise tiktok_error("TIKTOK_UI_DUMP_INVALID") from error

    def get_foreground_app(self) -> AdbForegroundApp:
        return self.adb.foreground_window(self.target.adb_serial)

    def get_foreground_activity(self) -> AdbForegroundApp:
        return self.adb.foreground_activity(self.target.adb_serial)

    def get_display_state(self) -> DisplayState:
        width, height = self.adb.display_size(self.target.adb_serial)
        rotation = self.adb.display_rotation(self.target.adb_serial)
        orientation = "portrait" if height >= width else "landscape"
        longest = max(width, height)
        category = "compact" if longest < 1280 else "standard" if longest < 2200 else "large"
        return DisplayState(width, height, rotation, orientation, category)

    def get_media_inventory(self) -> tuple[AdbMediaRecord, ...]:
        """Return the fixed, typed MediaStore inventory for this exact Runtime."""
        return self.adb.list_media_records(self.target.adb_serial)

    def tap_element(self, element: ResolvedUiElement) -> None:
        if not element.actionable:
            raise tiktok_error("TIKTOK_ELEMENT_NOT_FOUND")
        current = self.dump_ui_hierarchy()
        if current.fingerprint != element.snapshot_fingerprint:
            raise tiktok_error("TIKTOK_UI_STATE_UNCERTAIN")
        self.adb.tap(self.target.adb_serial, *element.bounds.center)

    def tap_profile_coordinate(self, coordinate: ProfileCoordinate, *, required_screen: str) -> None:
        display = self.get_display_state()
        if (coordinate.screen_key != required_screen or coordinate.width != display.width
                or coordinate.height != display.height or coordinate.orientation != display.orientation):
            raise tiktok_error("TIKTOK_UI_PROFILE_MISMATCH")
        self.adb.tap(self.target.adb_serial, coordinate.x, coordinate.y)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        display = self.get_display_state()
        if any(x < 0 for x in (x1, x2)) or any(y < 0 for y in (y1, y2)) or max(x1, x2) >= display.width or max(y1, y2) >= display.height:
            raise ValueError("UI coordinates are outside the display")
        self.adb.swipe(self.target.adb_serial, x1, y1, x2, y2, duration_ms)

    def focus_element(self, element: ResolvedUiElement) -> None:
        self.tap_element(element)

    def set_text(self, value: str) -> None:
        self.text.enter(self.adb, self.target.adb_serial, value)

    def replace_focused_text(self, current_length: int, value: str) -> None:
        self.adb.clear_focused_text(self.target.adb_serial, current_length)
        if value:
            self.text.enter(self.adb, self.target.adb_serial, value)

    def validate_text_entry(self, value: str) -> None:
        self.text.validate(value)

    def is_keyboard_visible(self) -> bool:
        return self.adb.is_keyboard_visible(self.target.adb_serial)

    def back(self) -> None:
        self.adb.keyevent(self.target.adb_serial, 4)

    def wait_for(self, predicate: Callable[[UiHierarchy], bool], *, timeout: float, interval: float = 0.5) -> UiHierarchy:
        deadline = time.monotonic() + timeout
        while True:
            hierarchy = self.dump_ui_hierarchy()
            if predicate(hierarchy):
                return hierarchy
            if time.monotonic() >= deadline:
                raise tiktok_error("TIKTOK_SCREEN_TIMEOUT", retryable=True)
            time.sleep(interval)

    def capture_screenshot(self) -> bytes:
        return self.adb.capture_screenshot(self.target.adb_serial)


class AndroidUiAutomationService:
    def __init__(self, session: Session, *, adb: AdbExecutor, readiness: AutomationReadinessService,
                 guard: RuntimeOperationGuard, parser: UiHierarchyParser,
                 text_provider: TextEntryProvider | None = None, lock_timeout: float = 0) -> None:
        self.session = session
        self.adb = adb
        self.readiness = readiness
        self.guard = guard
        self.parser = parser
        self.text_provider = text_provider or AsciiTextEntryProvider()
        self.lock_timeout = lock_timeout

    @contextmanager
    def open_session(self, runtime_id: int) -> Iterator[AndroidUiSession]:
        try:
            with self.guard.acquire_runtime(runtime_id, timeout=self.lock_timeout):
                target = RuntimeTargetResolver(self.session).resolve(runtime_id)
                # Runtime identity is now pinned in an immutable value object.
                # Release SQLite's read transaction before readiness checks and
                # the potentially long UI interaction begin.
                self.session.commit()
                self.readiness.wait_until_ready(target)
                yield AndroidUiSession(target, self.adb, self.parser, self.text_provider)
        except RuntimeOperationLockBusy as error:
            raise automation_error("RUNTIME_BUSY", retryable=True) from error
