"""Bounded, local-only ffprobe execution and normalized media parsing."""

from __future__ import annotations

import json
import os
import selectors
import signal
import stat
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any


class MediaProbeError(RuntimeError):
    def __init__(self, code: str, safe_message: str, *, retryable: bool) -> None:
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable
        super().__init__(safe_message)


@dataclass(frozen=True)
class ProbedMedia:
    width: int | None
    height: int | None
    duration_ms: int
    codec: str
    container: str
    frame_rate_numerator: int | None
    frame_rate_denominator: int | None
    audio_present: bool
    bitrate: int | None
    sample_rate: int | None
    channels: int | None
    orientation: int | None
    metadata: dict[str, Any]


Runner = Callable[..., subprocess.CompletedProcess[bytes]]
CancellationHook = Callable[[], bool]

_VIDEO_CODECS = {"h264", "hevc", "vp8", "vp9", "av1", "mpeg4"}
_AUDIO_CODECS = {
    "aac", "mp3", "opus", "vorbis", "flac",
    "pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le",
}
_CONTAINERS = {
    "video/mp4": ({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}, "mp4"),
    "video/quicktime": ({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}, "mov"),
    "video/webm": ({"matroska", "webm"}, "webm"),
    "audio/mpeg": ({"mp3"}, "mp3"),
    "audio/mp4": ({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}, "m4a"),
    "audio/aac": ({"aac"}, "aac"),
    "audio/wav": ({"wav"}, "wav"),
    "audio/ogg": ({"ogg"}, "ogg"),
}


class FfprobeInspector:
    def __init__(
        self,
        executable: Path,
        *,
        timeout_seconds: float = 30,
        max_output_bytes: int = 1024 * 1024,
        runner: Runner | None = None,
        cancellation_hook: CancellationHook | None = None,
    ) -> None:
        self.executable = Path(executable)
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.runner = runner
        self.cancellation_hook = cancellation_hook

    def probe(self, path: Path, expected_mime: str) -> ProbedMedia:
        self._validate_executable()
        source = Path(path)
        if not source.is_absolute():
            raise MediaProbeError("CONTENT_PROCESSING_FAILED", "Media source is unsafe", retryable=False)
        try:
            info = source.lstat()
        except OSError as error:
            raise MediaProbeError("CONTENT_BLOB_MISSING", "Content blob is unavailable", retryable=True) from error
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise MediaProbeError("CONTENT_BLOB_MISSING", "Content blob is unavailable", retryable=True)
        command = [
            str(self.executable), "-v", "error",
            "-protocol_whitelist", "file",
            "-show_entries",
            "format=format_name,duration,bit_rate:"
            "stream=index,codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,"
            "sample_rate,channels:stream_tags=rotate:stream_side_data_list=rotation",
            "-of", "json", str(source),
        ]
        completed = self._execute(command)
        if completed.returncode != 0:
            raise MediaProbeError(
                "CONTENT_MEDIA_CORRUPT", "Media could not be decoded", retryable=False
            )
        stdout = completed.stdout or b""
        stderr = completed.stderr or b""
        if isinstance(stdout, str):
            stdout = stdout.encode()
        if isinstance(stderr, str):
            stderr = stderr.encode()
        if len(stdout) > self.max_output_bytes or len(stderr) > self.max_output_bytes:
            raise MediaProbeError(
                "CONTENT_METADATA_INVALID", "Media metadata exceeded safe limits", retryable=False
            )
        try:
            payload = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MediaProbeError(
                "CONTENT_METADATA_INVALID", "Media metadata is invalid", retryable=False
            ) from error
        return self._normalize(payload, expected_mime)

    def _execute(self, command: list[str]) -> subprocess.CompletedProcess[bytes]:
        if self.cancellation_hook is not None and self.cancellation_hook():
            raise MediaProbeError(
                "CONTENT_PROCESSING_CANCELLED", "Content inspection was cancelled", retryable=True
            )
        try:
            if self.runner is not None:
                completed = self.runner(
                    command, shell=False, capture_output=True, text=False,
                    check=False, timeout=self.timeout_seconds,
                )
            else:
                completed = self._run_owned(command)
        except subprocess.TimeoutExpired as error:
            raise MediaProbeError(
                "CONTENT_FFPROBE_TIMEOUT", "Media inspection timed out", retryable=True
            ) from error
        except OSError as error:
            raise MediaProbeError(
                "CONTENT_FFPROBE_UNAVAILABLE", "Media inspection tool is unavailable", retryable=True
            ) from error
        if self.cancellation_hook is not None and self.cancellation_hook():
            raise MediaProbeError(
                "CONTENT_PROCESSING_CANCELLED", "Content inspection was cancelled", retryable=True
            )
        return completed

    def _run_owned(self, command: list[str]) -> subprocess.CompletedProcess[bytes]:
        process = subprocess.Popen(
            command,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
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
                    raise MediaProbeError(
                        "CONTENT_PROCESSING_CANCELLED",
                        "Content inspection was cancelled",
                        retryable=True,
                    )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._terminate(process)
                    raise subprocess.TimeoutExpired(command, self.timeout_seconds)
                for key, _mask in selector.select(timeout=min(0.1, remaining)):
                    chunk = os.read(key.fileobj.fileno(), 65_536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    buffer = output[key.data]
                    buffer.extend(chunk)
                    if len(buffer) > self.max_output_bytes:
                        self._terminate(process)
                        raise MediaProbeError(
                            "CONTENT_METADATA_INVALID",
                            "Media metadata exceeded safe limits",
                            retryable=False,
                        )
            process.wait(timeout=max(0.1, deadline - time.monotonic()))
            return subprocess.CompletedProcess(
                command,
                process.returncode,
                bytes(output["stdout"]),
                bytes(output["stderr"]),
            )
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

    def _validate_executable(self) -> None:
        if not self.executable.is_absolute():
            raise MediaProbeError(
                "CONTENT_FFPROBE_UNAVAILABLE", "Media inspection tool is unavailable", retryable=True
            )
        try:
            info = self.executable.lstat()
        except OSError as error:
            raise MediaProbeError(
                "CONTENT_FFPROBE_UNAVAILABLE", "Media inspection tool is unavailable", retryable=True
            ) from error
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISREG(info.st_mode)
            or info.st_uid not in {0, os.getuid()}
            or info.st_mode & 0o022
            or not info.st_mode & 0o111
        ):
            raise MediaProbeError(
                "CONTENT_FFPROBE_UNAVAILABLE", "Media inspection tool is unavailable", retryable=True
            )

    @staticmethod
    def _normalize(payload: Any, expected_mime: str) -> ProbedMedia:
        if not isinstance(payload, dict) or not isinstance(payload.get("streams"), list):
            raise MediaProbeError("CONTENT_METADATA_INVALID", "Media metadata is invalid", retryable=False)
        streams = payload["streams"]
        if not 1 <= len(streams) <= 32 or any(not isinstance(item, dict) for item in streams):
            raise MediaProbeError("CONTENT_METADATA_INVALID", "Media stream count is invalid", retryable=False)
        expected = _CONTAINERS.get(expected_mime)
        format_data = payload.get("format")
        if expected is None or not isinstance(format_data, dict):
            raise MediaProbeError("CONTENT_MEDIA_UNSUPPORTED", "Media format is unsupported", retryable=False)
        format_names = set(str(format_data.get("format_name", "")).lower().split(","))
        allowed_formats, container = expected
        if not format_names.intersection(allowed_formats):
            raise MediaProbeError("CONTENT_MEDIA_UNSUPPORTED", "Media container is unsupported", retryable=False)
        duration = FfprobeInspector._positive_float(format_data.get("duration"))
        if duration is None or duration > 24 * 60 * 60:
            raise MediaProbeError("CONTENT_METADATA_INVALID", "Media duration is invalid", retryable=False)
        duration_ms = max(1, round(duration * 1000))
        bitrate = FfprobeInspector._positive_int(format_data.get("bit_rate"))
        video_streams = [item for item in streams if item.get("codec_type") == "video"]
        audio_streams = [item for item in streams if item.get("codec_type") == "audio"]
        if expected_mime.startswith("video/"):
            if not video_streams:
                raise MediaProbeError("CONTENT_MEDIA_CORRUPT", "Media has no video stream", retryable=False)
            video = video_streams[0]
            codec = str(video.get("codec_name", "")).lower()
            if codec not in _VIDEO_CODECS:
                raise MediaProbeError("CONTENT_MEDIA_UNSUPPORTED", "Video codec is unsupported", retryable=False)
            width = FfprobeInspector._positive_int(video.get("width"))
            height = FfprobeInspector._positive_int(video.get("height"))
            if width is None or height is None or width > 32768 or height > 32768:
                raise MediaProbeError("CONTENT_METADATA_INVALID", "Video dimensions are invalid", retryable=False)
            rate = FfprobeInspector._frame_rate(video)
            audio_codec = None
            if audio_streams:
                audio_codec = str(audio_streams[0].get("codec_name", "")).lower()
                if audio_codec not in _AUDIO_CODECS:
                    raise MediaProbeError("CONTENT_MEDIA_UNSUPPORTED", "Audio codec is unsupported", retryable=False)
            rotation = FfprobeInspector._rotation(video)
            return ProbedMedia(
                width, height, duration_ms, codec, container,
                rate.numerator, rate.denominator, bool(audio_streams), bitrate,
                None, None, rotation,
                {"audio_codec": audio_codec, "rotation": rotation, "stream_count": len(streams)},
            )
        if video_streams or not audio_streams:
            raise MediaProbeError("CONTENT_MEDIA_CORRUPT", "Media audio streams are invalid", retryable=False)
        audio = audio_streams[0]
        codec = str(audio.get("codec_name", "")).lower()
        if codec not in _AUDIO_CODECS:
            raise MediaProbeError("CONTENT_MEDIA_UNSUPPORTED", "Audio codec is unsupported", retryable=False)
        sample_rate = FfprobeInspector._positive_int(audio.get("sample_rate"))
        channels = FfprobeInspector._positive_int(audio.get("channels"))
        if sample_rate is None or not 8_000 <= sample_rate <= 384_000 or channels is None or channels > 32:
            raise MediaProbeError("CONTENT_METADATA_INVALID", "Audio metadata is invalid", retryable=False)
        return ProbedMedia(
            None, None, duration_ms, codec, container, None, None, True,
            bitrate, sample_rate, channels, None,
            {"stream_count": len(streams)},
        )

    @staticmethod
    def _positive_int(value: Any) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _positive_float(value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if 0 < parsed < float("inf") else None

    @staticmethod
    def _frame_rate(stream: dict[str, Any]) -> Fraction:
        for key in ("avg_frame_rate", "r_frame_rate"):
            try:
                value = Fraction(str(stream.get(key, "0/1")))
            except (ValueError, ZeroDivisionError):
                continue
            if 0 < value <= 240:
                return value
        raise MediaProbeError("CONTENT_METADATA_INVALID", "Video frame rate is invalid", retryable=False)

    @staticmethod
    def _rotation(stream: dict[str, Any]) -> int | None:
        values: list[Any] = []
        tags = stream.get("tags")
        if isinstance(tags, dict):
            values.append(tags.get("rotate"))
        side_data = stream.get("side_data_list")
        if isinstance(side_data, list):
            values.extend(item.get("rotation") for item in side_data if isinstance(item, dict))
        for value in values:
            try:
                rotation = int(float(value))
            except (TypeError, ValueError):
                continue
            if -360 <= rotation <= 360:
                return rotation
        return None
