"""Typed, serial-scoped ADB execution for Android automation."""

from __future__ import annotations

import re
import os
import signal
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Lock


_SERIAL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")
_SAFE_MEDIA_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
_PACKAGE_NAME = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$"
)
_COMPONENT_CLASS = re.compile(r"^(?:\.?[A-Za-z][A-Za-z0-9_.$]*)$")
_MANAGED_REMOTE_PATH = re.compile(
    r"^/sdcard/Download/TikTokManager/[A-Za-z0-9][A-Za-z0-9._-]{0,254}$"
)
_SAFE_ENCODED_TEXT = re.compile(r"^[A-Za-z0-9.,!?@_+%\-]{1,512}$")


class AdbExecutorError(RuntimeError):
    """A sanitized failure from a typed ADB operation."""

    def __init__(self, kind: str, safe_message: str) -> None:
        self.kind = kind
        self.safe_message = safe_message
        super().__init__(safe_message)


@dataclass(frozen=True)
class AdbTextResult:
    returncode: int
    stdout: str


@dataclass(frozen=True)
class AdbBinaryResult:
    returncode: int
    stdout: bytes


@dataclass(frozen=True)
class AdbInstalledPackage:
    package_name: str
    package_path: str
    version_name: str | None
    version_code: int | None
    enabled: bool
    signer_fingerprint: str | None


@dataclass(frozen=True)
class AdbForegroundApp:
    package_name: str
    activity_name: str | None


@dataclass(frozen=True)
class AdbMediaRecord:
    media_id: int
    display_name: str
    size_bytes: int | None
    mime_type: str | None
    duration_ms: int | None
    relative_path: str | None
    bucket_display_name: str | None


CommandRunner = Callable[..., subprocess.CompletedProcess[bytes]]
CancellationHook = Callable[[], bool]


class OwnedAdbProcessRegistry:
    """Track only ADB child process groups spawned by this backend process."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._processes: set[subprocess.Popen[bytes]] = set()

    def register(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            self._processes.add(process)

    def unregister(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            self._processes.discard(process)

    def terminate_all(self) -> int:
        with self._lock:
            processes = tuple(self._processes)
        terminated = 0
        for process in processes:
            if process.poll() is None:
                AdbExecutor._terminate_owned_process(process)
                terminated += 1
            self.unregister(process)
        return terminated


owned_adb_processes = OwnedAdbProcessRegistry()


def terminate_owned_adb_children() -> int:
    """Terminate exact backend-owned automation children, never the ADB server."""
    return owned_adb_processes.terminate_all()


class AdbExecutor:
    """Execute only explicitly modeled ADB operations against one exact serial."""

    def __init__(
        self,
        runner: CommandRunner | None = None,
        *,
        default_timeout: float = 15.0,
        max_stdout_bytes: int = 32 * 1024 * 1024,
        max_stderr_bytes: int = 65_536,
        cancellation_hook: CancellationHook | None = None,
    ) -> None:
        if default_timeout <= 0:
            raise ValueError("default_timeout must be greater than zero")
        if max_stdout_bytes <= 0 or max_stderr_bytes <= 0:
            raise ValueError("ADB output limits must be greater than zero")
        self._runner = runner or subprocess.run
        self._uses_default_runner = runner is None
        self.default_timeout = default_timeout
        self.max_stdout_bytes = max_stdout_bytes
        self.max_stderr_bytes = max_stderr_bytes
        self.cancellation_hook = cancellation_hook

    def get_state(self, serial: str, *, timeout: float | None = None) -> str:
        return self._text(serial, ["get-state"], timeout=timeout).stdout.strip()

    def get_boot_completed(self, serial: str, *, timeout: float | None = None) -> bool:
        result = self._text(
            serial, ["shell", "getprop", "sys.boot_completed"], timeout=timeout
        )
        return result.stdout.strip() == "1"

    def package_path(self, serial: str, package_name: str) -> str | None:
        self._validate_package_name(package_name)
        result = self._text(
            serial,
            ["shell", "pm", "path", package_name],
            raise_on_nonzero=False,
        )
        if result.returncode != 0 or not result.stdout.strip().startswith("package:"):
            return None
        return result.stdout.strip().removeprefix("package:")

    def package_pid(self, serial: str, package_name: str) -> int | None:
        self._validate_package_name(package_name)
        result = self._text(
            serial,
            ["shell", "pidof", "-s", package_name],
            raise_on_nonzero=False,
        )
        value = result.stdout.strip()
        if result.returncode != 0 or not value.isdigit():
            return None
        return int(value)

    def installed_package(
        self, serial: str, package_name: str, *, timeout: float | None = None
    ) -> AdbInstalledPackage | None:
        """Return normalized package-manager state without exposing raw output."""
        self._validate_package_name(package_name)
        package_path = self.package_path(serial, package_name)
        if package_path is None:
            return None
        if not package_path.startswith("/data/app/") or any(
            character in package_path for character in ("\x00", "\n", "\r")
        ):
            raise AdbExecutorError("failed", "Android package path is invalid")
        result = self._text(
            serial,
            ["shell", "dumpsys", "package", package_name],
            timeout=timeout,
        )
        version_code_match = re.search(r"(?:^|\s)versionCode=(\d+)(?:\s|$)", result.stdout)
        version_name_match = re.search(r"(?:^|\s)versionName=([^\s]+)", result.stdout)
        enabled_match = re.search(r"(?:^|\s)enabled=(true|false|[0-4])(?:\s|$)", result.stdout)
        digest_match = re.search(
            r"SHA-256(?: certificate)? digest:\s*([0-9A-Fa-f:]{64,95})",
            result.stdout,
        )
        signer = None
        if digest_match:
            candidate = digest_match.group(1).replace(":", "").lower()
            if re.fullmatch(r"[0-9a-f]{64}", candidate):
                signer = candidate
        enabled_value = enabled_match.group(1) if enabled_match else "true"
        return AdbInstalledPackage(
            package_name=package_name,
            package_path=package_path,
            version_name=version_name_match.group(1) if version_name_match else None,
            version_code=int(version_code_match.group(1)) if version_code_match else None,
            enabled=enabled_value in {"true", "0", "1"},
            signer_fingerprint=signer,
        )

    def install_package(
        self, serial: str, apk_path: Path, *, timeout: float = 300.0
    ) -> None:
        """Install one backend-resolved monolithic APK with the fixed update policy."""
        path = Path(apk_path)
        if not path.is_absolute():
            raise ValueError("APK path must be absolute")
        # -r permits a same-signer upgrade while deliberately omitting -d, -g,
        # uninstall, split-package flags, and every caller-controlled option.
        self._text(serial, ["install", "-r", str(path)], timeout=timeout)

    def launch_package(self, serial: str, package_name: str) -> None:
        self._validate_package_name(package_name)
        resolved = self._text(
            serial,
            [
                "shell", "cmd", "package", "resolve-activity", "--brief",
                "-c", "android.intent.category.LAUNCHER", package_name,
            ],
        ).stdout
        lines = [line.strip() for line in resolved.splitlines() if line.strip()]
        if not lines or "/" not in lines[-1]:
            raise AdbExecutorError("failed", "Android package has no safe launcher activity")
        component_package, component_class = lines[-1].split("/", 1)
        if component_package != package_name or not _COMPONENT_CLASS.fullmatch(component_class):
            raise AdbExecutorError("failed", "Android launcher activity is invalid")
        self._text(
            serial,
            ["shell", "am", "start", "-n", f"{component_package}/{component_class}"],
        )

    def force_stop_package(self, serial: str, package_name: str) -> None:
        self._validate_package_name(package_name)
        self._text(serial, ["shell", "am", "force-stop", package_name])

    def capture_screenshot(
        self, serial: str, *, timeout: float | None = 30.0
    ) -> bytes:
        return self._binary(
            serial, ["exec-out", "screencap", "-p"], timeout=timeout
        ).stdout

    def push(self, serial: str, local_path: Path, remote_path: str, *, timeout: float = 120.0) -> None:
        self._validate_managed_remote_path(remote_path)
        self._text(serial, ["push", str(local_path), remote_path], timeout=timeout)

    def ensure_managed_remote_directory(self, serial: str) -> None:
        self._text(
            serial,
            ["shell", "mkdir", "-p", "/sdcard/Download/TikTokManager"],
        )

    def pull(self, serial: str, remote_path: str, local_path: Path, *, timeout: float = 120.0) -> None:
        self._validate_managed_remote_path(remote_path)
        self._text(serial, ["pull", remote_path, str(local_path)], timeout=timeout)

    def remote_file_size(self, serial: str, remote_path: str) -> int | None:
        self._validate_managed_remote_path(remote_path)
        result = self._text(
            serial,
            ["shell", "stat", "-c", "%s", remote_path],
            raise_on_nonzero=False,
        )
        value = result.stdout.strip()
        return int(value) if result.returncode == 0 and value.isdigit() else None

    def scan_media(self, serial: str, remote_path: str) -> None:
        self._validate_managed_remote_path(remote_path)
        self._text(
            serial,
            [
                "shell",
                "am",
                "broadcast",
                "-a",
                "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                "-d",
                f"file://{remote_path}",
            ],
        )

    def find_media_id(self, serial: str, display_name: str) -> int | None:
        if not _SAFE_MEDIA_NAME.fullmatch(display_name):
            raise ValueError("media display name is invalid")
        result = self._text(
            serial,
            [
                "shell",
                "content",
                "query",
                "--uri",
                "content://media/external/file",
                "--projection",
                "_id:_display_name",
            ],
            raise_on_nonzero=False,
        )
        if result.returncode != 0:
            return None
        matches: list[int] = []
        for line in result.stdout.splitlines():
            match = re.search(r"(?:^|[ ,])_id=(\d+), _display_name=(.+)$", line)
            if match and match.group(2) == display_name:
                matches.append(int(match.group(1)))
        return matches[-1] if matches else None

    def list_media_records(self, serial: str) -> tuple[AdbMediaRecord, ...]:
        """Return a bounded normalized MediaStore inventory from a fixed URI."""
        result = self._text(
            serial,
            [
                "shell", "content", "query", "--uri",
                "content://media/external/file", "--projection",
                "_id:_display_name:_size:mime_type:duration:relative_path:bucket_display_name",
            ],
            raise_on_nonzero=False,
        )
        if result.returncode != 0:
            return ()
        records: list[AdbMediaRecord] = []
        pattern = re.compile(
            r"(?:^|[ ,])_id=(\d+), _display_name=([^,]+), _size=([^,]+), "
            r"mime_type=([^,]+), duration=([^,]+), relative_path=([^,]+), "
            r"bucket_display_name=(.*)$"
        )
        for line in result.stdout.splitlines():
            match = pattern.search(line)
            if match is None:
                continue
            media_id = int(match.group(1))
            display_name = match.group(2).strip()
            if not _SAFE_MEDIA_NAME.fullmatch(display_name):
                continue
            values = [value.strip() for value in match.groups()[2:]]
            size = int(values[0]) if values[0].isdigit() else None
            duration = int(values[2]) if values[2].isdigit() else None
            mime = None if values[1] in {"NULL", "null"} else values[1][:255]
            relative = None if values[3] in {"NULL", "null"} else values[3][:512]
            bucket = None if values[4] in {"NULL", "null"} else values[4][:255]
            records.append(AdbMediaRecord(
                media_id=media_id,
                display_name=display_name,
                size_bytes=size,
                mime_type=mime,
                duration_ms=duration,
                relative_path=relative,
                bucket_display_name=bucket,
            ))
        return tuple(records)

    def display_size(self, serial: str) -> tuple[int, int]:
        result = self._text(serial, ["shell", "wm", "size"])
        matches = re.findall(r"(?:Physical|Override) size:\s*(\d+)x(\d+)", result.stdout)
        if not matches:
            raise AdbExecutorError("failed", "ADB display-size query failed")
        width, height = matches[-1]
        return int(width), int(height)

    def dump_ui_hierarchy(self, serial: str, *, timeout: float = 15.0) -> str:
        """Return UIAutomator XML using only backend-owned fixed commands/paths."""
        direct = self._text(
            serial, ["exec-out", "uiautomator", "dump", "/dev/tty"],
            timeout=timeout, raise_on_nonzero=False,
        )
        extracted = self._extract_uiautomator_xml(direct.stdout)
        if direct.returncode == 0 and extracted is not None:
            return extracted
        fixed_path = "/sdcard/window_dump_tiktok_manager.xml"
        self._text(serial, ["shell", "uiautomator", "dump", fixed_path], timeout=timeout)
        try:
            result = self._text(serial, ["exec-out", "cat", fixed_path], timeout=timeout)
            extracted = self._extract_uiautomator_xml(result.stdout)
            if extracted is None:
                raise AdbExecutorError("failed", "Android UI hierarchy was unavailable")
            return extracted
        finally:
            self._text(
                serial, ["shell", "rm", "-f", fixed_path],
                timeout=timeout, raise_on_nonzero=False,
            )

    def foreground_window(self, serial: str) -> AdbForegroundApp:
        # Android 12's `dumpsys window windows` omits mCurrentFocus on the
        # validated Redroid build; the fixed service-level dump retains it.
        result = self._text(serial, ["shell", "dumpsys", "window"])
        return self._parse_foreground(result.stdout)

    def foreground_activity(self, serial: str) -> AdbForegroundApp:
        result = self._text(serial, ["shell", "dumpsys", "activity", "activities"])
        return self._parse_foreground(result.stdout)

    def display_rotation(self, serial: str) -> int:
        result = self._text(serial, ["shell", "settings", "get", "system", "user_rotation"])
        value = result.stdout.strip()
        if value not in {"0", "1", "2", "3"}:
            raise AdbExecutorError("failed", "ADB display-rotation query failed")
        return int(value)

    def tap(self, serial: str, x: int, y: int) -> None:
        self._validate_coordinate(x)
        self._validate_coordinate(y)
        self._text(serial, ["shell", "input", "tap", str(x), str(y)])

    def swipe(
        self,
        serial: str,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int,
    ) -> None:
        for coordinate in (x1, y1, x2, y2):
            self._validate_coordinate(coordinate)
        if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or not 50 <= duration_ms <= 5000:
            raise ValueError("swipe duration is invalid")
        self._text(
            serial,
            [
                "shell",
                "input",
                "swipe",
                str(x1),
                str(y1),
                str(x2),
                str(y2),
                str(duration_ms),
            ],
        )

    def input_text(self, serial: str, encoded_text: str) -> None:
        if not isinstance(encoded_text, str) or not _SAFE_ENCODED_TEXT.fullmatch(encoded_text):
            raise ValueError("encoded input text is invalid")
        self._text(serial, ["shell", "input", "text", encoded_text])

    def clear_focused_text(self, serial: str, character_count: int) -> None:
        """Clear one focused field with fixed backend-owned Android keycodes."""
        if (
            isinstance(character_count, bool)
            or not isinstance(character_count, int)
            or not 0 <= character_count <= 512
        ):
            raise ValueError("focused text length is invalid")
        if character_count == 0:
            return
        # KEYCODE_MOVE_END followed by exactly the bounded number of
        # KEYCODE_DEL events. No caller chooses either keycode.
        self._text(
            serial,
            ["shell", "input", "keyevent", "123"]
            + ["67"] * character_count,
        )

    def is_keyboard_visible(self, serial: str) -> bool:
        """Return normalized IME visibility without exposing dumpsys output."""
        output = self._text(
            serial, ["shell", "dumpsys", "input_method"]
        ).stdout
        # InputMethodManagerService's current request state is authoritative.
        # InputMethodService may retain mIsInputViewShown=true briefly while
        # its view exists but the system has already hidden it.
        primary = re.findall(r"(?:^|\s)mInputShown=(true|false)", output)
        if primary:
            return primary[-1] == "true"
        fallback = re.findall(
            r"(?:mIsInputViewShown|isInputViewShown)=(true|false)", output,
        )
        if not fallback:
            raise AdbExecutorError("failed", "Android keyboard state is unavailable")
        return fallback[-1] == "true"

    def keyevent(self, serial: str, keycode: int) -> None:
        if isinstance(keycode, bool) or keycode not in {3, 4, 19, 20, 21, 22, 23, 66, 82, 187}:
            raise ValueError("keyevent is not allowlisted")
        self._text(serial, ["shell", "input", "keyevent", str(keycode)])

    def _text(
        self,
        serial: str,
        arguments: Sequence[str],
        *,
        timeout: float | None = None,
        raise_on_nonzero: bool = True,
    ) -> AdbTextResult:
        completed = self._execute(
            serial,
            arguments,
            timeout=timeout,
            stdout_limit=self.max_stdout_bytes,
            raise_on_nonzero=raise_on_nonzero,
        )
        try:
            stdout = completed.stdout.decode("utf-8", errors="replace")
        except AttributeError:
            stdout = str(completed.stdout)
        return AdbTextResult(completed.returncode, stdout)

    def _binary(
        self,
        serial: str,
        arguments: Sequence[str],
        *,
        timeout: float | None = None,
    ) -> AdbBinaryResult:
        completed = self._execute(
            serial,
            arguments,
            timeout=timeout,
            stdout_limit=self.max_stdout_bytes,
            raise_on_nonzero=True,
        )
        stdout = completed.stdout
        if isinstance(stdout, str):
            stdout = stdout.encode()
        return AdbBinaryResult(completed.returncode, stdout)

    def _execute(
        self,
        serial: str,
        arguments: Sequence[str],
        *,
        timeout: float | None,
        stdout_limit: int,
        raise_on_nonzero: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        self._validate_serial(serial)
        if not arguments or any(not isinstance(argument, str) for argument in arguments):
            raise ValueError("ADB arguments must be a non-empty string sequence")
        if "kill-server" in arguments:
            raise ValueError("adb kill-server is not an automation operation")
        if self.cancellation_hook is not None and self.cancellation_hook():
            raise AdbExecutorError("cancelled", "ADB automation was cancelled")
        command = ["adb", "-s", serial, *arguments]
        command_timeout = self.default_timeout if timeout is None else timeout
        if command_timeout <= 0:
            raise ValueError("ADB timeout must be greater than zero")
        try:
            if self._uses_default_runner and self.cancellation_hook is not None:
                completed = self._run_cancellable(command, command_timeout)
            else:
                completed = self._runner(
                    command, shell=False, capture_output=True, text=False,
                    check=False, timeout=command_timeout,
                )
        except subprocess.TimeoutExpired as error:
            raise AdbExecutorError("timeout", "ADB automation command timed out") from error
        except OSError as error:
            raise AdbExecutorError("unavailable", "ADB executable is unavailable") from error
        stdout = completed.stdout or b""
        stderr = completed.stderr or b""
        if isinstance(stdout, str):
            stdout_size = len(stdout.encode())
        else:
            stdout_size = len(stdout)
        if isinstance(stderr, str):
            stderr_size = len(stderr.encode())
        else:
            stderr_size = len(stderr)
        if stdout_size > stdout_limit or stderr_size > self.max_stderr_bytes:
            raise AdbExecutorError("output_limit", "ADB command output exceeded its safe limit")
        if raise_on_nonzero and completed.returncode != 0:
            raise AdbExecutorError("failed", "ADB automation command failed")
        if self.cancellation_hook is not None and self.cancellation_hook():
            raise AdbExecutorError("cancelled", "ADB automation was cancelled")
        return completed

    def _run_cancellable(self, command: list[str], timeout: float) -> subprocess.CompletedProcess[bytes]:
        """Terminate only the exact process group created for this ADB command."""
        process = subprocess.Popen(
            command, shell=False, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )
        owned_adb_processes.register(process)
        try:
            deadline = time.monotonic() + timeout
            while True:
                if self.cancellation_hook is not None and self.cancellation_hook():
                    self._terminate_owned_process(process)
                    raise AdbExecutorError("cancelled", "ADB automation was cancelled")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._terminate_owned_process(process)
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    stdout, stderr = process.communicate(timeout=min(0.1, remaining))
                    return subprocess.CompletedProcess(
                        command, process.returncode, stdout, stderr
                    )
                except subprocess.TimeoutExpired:
                    continue
        finally:
            owned_adb_processes.unregister(process)

    @staticmethod
    def _terminate_owned_process(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
        except ProcessLookupError:
            pass

    @staticmethod
    def _validate_serial(serial: str) -> None:
        if not isinstance(serial, str) or not _SERIAL_PATTERN.fullmatch(serial):
            raise ValueError("ADB serial is invalid")

    @staticmethod
    def _validate_package_name(package_name: str) -> None:
        if (
            not isinstance(package_name, str)
            or len(package_name) > 255
            or not _PACKAGE_NAME.fullmatch(package_name)
        ):
            raise ValueError("Android package name is invalid")

    @staticmethod
    def _validate_managed_remote_path(remote_path: str) -> None:
        if not isinstance(remote_path, str) or not _MANAGED_REMOTE_PATH.fullmatch(remote_path):
            raise ValueError("Android remote path is outside the managed directory")

    @staticmethod
    def _validate_coordinate(value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("Android input coordinate is invalid")

    @staticmethod
    def _parse_foreground(output: str) -> AdbForegroundApp:
        patterns = (
            r"(?:mCurrentFocus|mFocusedApp|topResumedActivity|mResumedActivity)[^\n]*?\s([A-Za-z][A-Za-z0-9_.]*)/([A-Za-z0-9_.$]+)",
            r"\b([A-Za-z][A-Za-z0-9_.]*)/([A-Za-z0-9_.$]+)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, output)
            if match and _PACKAGE_NAME.fullmatch(match.group(1)):
                return AdbForegroundApp(match.group(1), match.group(2))
        raise AdbExecutorError("failed", "ADB foreground-app query failed")

    @staticmethod
    def _extract_uiautomator_xml(output: str) -> str | None:
        """Strip UIAutomator's device-specific pre/postamble from one document."""
        start = output.find("<?xml")
        closing = "</hierarchy>"
        end = output.find(closing, start + 5) if start >= 0 else -1
        if start < 0 or end < 0:
            return None
        return output[start:end + len(closing)]
