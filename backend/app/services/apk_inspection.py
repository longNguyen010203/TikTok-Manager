"""Trusted, bounded aapt2/apksigner inspection for managed APK blobs."""

from __future__ import annotations

import os
import re
import selectors
import signal
import stat
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class ApkInspectionError(RuntimeError):
    def __init__(self, code: str, safe_message: str, *, retryable: bool) -> None:
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable
        super().__init__(safe_message)


@dataclass(frozen=True)
class InspectedApk:
    package_name: str
    version_name: str | None
    version_code: int | None
    min_sdk: int | None
    target_sdk: int | None
    signer_fingerprint: str
    signer_fingerprints: tuple[str, ...]
    inspector_version: str | None


Runner = Callable[..., subprocess.CompletedProcess[bytes]]
CancellationHook = Callable[[], bool]
_PACKAGE = re.compile(r"^package:\s+name='([^']+)'(?:\s+versionCode='([^']*)')?(?:\s+versionName='([^']*)')?", re.MULTILINE)
_MIN_SDK = re.compile(r"^sdkVersion:'([^']+)'", re.MULTILINE)
_TARGET_SDK = re.compile(r"^targetSdkVersion:'([^']+)'", re.MULTILINE)
_SIGNER = re.compile(r"certificate SHA-256 digest:\s*([0-9A-Fa-f:]{64,95})", re.IGNORECASE)


class ApkToolInspector:
    def __init__(
        self,
        aapt2_path: Path,
        apksigner_path: Path,
        *,
        timeout_seconds: float,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
        runner: Runner | None = None,
        cancellation_hook: CancellationHook | None = None,
    ) -> None:
        self.aapt2_path = Path(aapt2_path)
        self.apksigner_path = Path(apksigner_path)
        self.timeout_seconds = timeout_seconds
        self.max_stdout_bytes = max_stdout_bytes
        self.max_stderr_bytes = max_stderr_bytes
        self.runner = runner
        self.cancellation_hook = cancellation_hook

    def inspect(self, path: Path) -> InspectedApk:
        source = Path(path)
        self._validate_tool(self.aapt2_path)
        self._validate_tool(self.apksigner_path)
        self._validate_source(source)
        aapt = self._execute([str(self.aapt2_path), "dump", "badging", str(source)])
        if aapt.returncode != 0:
            raise ApkInspectionError("APK_INVALID", "APK metadata is invalid", retryable=False)
        signer = self._execute([
            str(self.apksigner_path), "verify", "--verbose", "--print-certs", str(source)
        ])
        if signer.returncode != 0:
            raise ApkInspectionError("APK_SIGNATURE_INVALID", "APK signature is invalid", retryable=False)
        normalized = self._normalize(aapt.stdout or b"", signer.stdout or b"")
        inspector_version = self._inspector_version()
        return InspectedApk(
            normalized.package_name,
            normalized.version_name,
            normalized.version_code,
            normalized.min_sdk,
            normalized.target_sdk,
            normalized.signer_fingerprint,
            normalized.signer_fingerprints,
            inspector_version,
        )

    def _inspector_version(self) -> str | None:
        versions: list[str] = []
        for name, command in (
            ("aapt2", [str(self.aapt2_path), "version"]),
            ("apksigner", [str(self.apksigner_path), "version"]),
        ):
            try:
                completed = self._execute(command)
            except ApkInspectionError:
                continue
            if completed.returncode != 0:
                continue
            output = completed.stdout.decode("utf-8", errors="ignore")
            match = re.search(r"\b\d+(?:\.\d+){1,3}(?:[-+._A-Za-z0-9]*)?\b", output)
            if match:
                versions.append(f"{name}:{match.group(0)}")
        value = ";".join(versions)
        return value[:255] or None

    def _execute(self, command: list[str]) -> subprocess.CompletedProcess[bytes]:
        if self.cancellation_hook is not None and self.cancellation_hook():
            raise ApkInspectionError("APP_INSPECTION_CANCELLED", "App inspection was cancelled", retryable=True)
        try:
            if self.runner is not None:
                completed = self.runner(
                    command, shell=False, capture_output=True, text=False,
                    check=False, timeout=self.timeout_seconds,
                )
            else:
                completed = self._run_owned(command)
        except subprocess.TimeoutExpired as error:
            raise ApkInspectionError("APK_INSPECTION_TIMEOUT", "APK inspection timed out", retryable=True) from error
        except OSError as error:
            raise ApkInspectionError("APK_INSPECTOR_UNAVAILABLE", "APK inspection tooling is unavailable", retryable=True) from error
        stdout = completed.stdout.encode() if isinstance(completed.stdout, str) else (completed.stdout or b"")
        stderr = completed.stderr.encode() if isinstance(completed.stderr, str) else (completed.stderr or b"")
        if len(stdout) > self.max_stdout_bytes or len(stderr) > self.max_stderr_bytes:
            raise ApkInspectionError("APK_INSPECTION_FAILED", "APK inspector output exceeded safe limits", retryable=False)
        if self.cancellation_hook is not None and self.cancellation_hook():
            raise ApkInspectionError("APP_INSPECTION_CANCELLED", "App inspection was cancelled", retryable=True)
        return subprocess.CompletedProcess(command, completed.returncode, stdout, stderr)

    def _run_owned(self, command: list[str]) -> subprocess.CompletedProcess[bytes]:
        process = subprocess.Popen(
            command, shell=False, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        )
        deadline = time.monotonic() + self.timeout_seconds
        selector = selectors.DefaultSelector()
        assert process.stdout is not None and process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        output = {"stdout": bytearray(), "stderr": bytearray()}
        try:
            while selector.get_map():
                if self.cancellation_hook is not None and self.cancellation_hook():
                    self._terminate(process)
                    raise ApkInspectionError("APP_INSPECTION_CANCELLED", "App inspection was cancelled", retryable=True)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._terminate(process)
                    raise subprocess.TimeoutExpired(command, self.timeout_seconds)
                for key, _ in selector.select(timeout=min(0.1, remaining)):
                    chunk = os.read(key.fileobj.fileno(), 65_536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    buffer = output[key.data]
                    buffer.extend(chunk)
                    limit = self.max_stdout_bytes if key.data == "stdout" else self.max_stderr_bytes
                    if len(buffer) > limit:
                        self._terminate(process)
                        raise ApkInspectionError("APK_INSPECTION_FAILED", "APK inspector output exceeded safe limits", retryable=False)
            process.wait(timeout=max(0.1, deadline - time.monotonic()))
            return subprocess.CompletedProcess(command, process.returncode, bytes(output["stdout"]), bytes(output["stderr"]))
        finally:
            selector.close()
            if process.poll() is None:
                self._terminate(process)

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
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
    def _validate_tool(path: Path) -> None:
        if not path.is_absolute():
            raise ApkInspectionError("APK_INSPECTOR_UNAVAILABLE", "APK inspection tooling is unavailable", retryable=True)
        try:
            info = path.lstat()
        except OSError as error:
            raise ApkInspectionError("APK_INSPECTOR_UNAVAILABLE", "APK inspection tooling is unavailable", retryable=True) from error
        if (
            stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
            or info.st_uid not in {0, os.getuid()} or info.st_mode & 0o022
            or not info.st_mode & 0o111
        ):
            raise ApkInspectionError("APK_INSPECTOR_UNAVAILABLE", "APK inspection tooling is unavailable", retryable=True)

    @staticmethod
    def _validate_source(path: Path) -> None:
        if not path.is_absolute():
            raise ApkInspectionError("CONTENT_BLOB_MISSING", "Managed APK blob is unavailable", retryable=True)
        try:
            info = path.lstat()
        except OSError as error:
            raise ApkInspectionError("CONTENT_BLOB_MISSING", "Managed APK blob is unavailable", retryable=True) from error
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise ApkInspectionError("CONTENT_BLOB_MISSING", "Managed APK blob is unavailable", retryable=True)

    @staticmethod
    def _normalize(aapt_output: bytes, signer_output: bytes) -> InspectedApk:
        try:
            aapt = aapt_output.decode("utf-8")
            signer = signer_output.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ApkInspectionError("APK_INVALID", "APK metadata is invalid", retryable=False) from error
        package = _PACKAGE.search(aapt)
        if package is None:
            raise ApkInspectionError("APK_INVALID", "APK package metadata is invalid", retryable=False)
        package_name, raw_code, version_name = package.groups()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", package_name):
            raise ApkInspectionError("APK_INVALID", "APK package metadata is invalid", retryable=False)
        version_code = ApkToolInspector._integer(raw_code, maximum=2**63 - 1)
        min_match, target_match = _MIN_SDK.search(aapt), _TARGET_SDK.search(aapt)
        min_sdk = ApkToolInspector._integer(min_match.group(1) if min_match else None, maximum=1000)
        target_sdk = ApkToolInspector._integer(target_match.group(1) if target_match else None, maximum=1000)
        fingerprints = tuple(dict.fromkeys(
            match.replace(":", "").lower() for match in _SIGNER.findall(signer)
        ))
        if not fingerprints or any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in fingerprints):
            raise ApkInspectionError("APK_SIGNATURE_INVALID", "APK signature metadata is invalid", retryable=False)
        safe_name = version_name if version_name and len(version_name) <= 255 else None
        return InspectedApk(package_name, safe_name, version_code, min_sdk, target_sdk, fingerprints[0], fingerprints, None)

    @staticmethod
    def _integer(value: str | None, *, maximum: int) -> int | None:
        if value in {None, ""}:
            return None
        try:
            result = int(value)
        except (TypeError, ValueError) as error:
            raise ApkInspectionError("APK_INVALID", "APK numeric metadata is invalid", retryable=False) from error
        if result < 0 or result > maximum:
            raise ApkInspectionError("APK_INVALID", "APK numeric metadata is invalid", retryable=False)
        return result
