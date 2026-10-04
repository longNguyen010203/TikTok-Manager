"""Bounded, signature-based admission checks for reusable content."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


class ContentValidationError(ValueError):
    def __init__(self, code: str, safe_message: str) -> None:
        self.code = code
        self.safe_message = safe_message
        super().__init__(safe_message)


@dataclass(frozen=True)
class DetectedContent:
    asset_type: str
    mime_type: str
    canonical_extension: str
    allowed_extensions: frozenset[str]


_SAFE_FILENAME_CHARACTER = re.compile(r"[^A-Za-z0-9._-]")
_MIME_ALIASES = {
    "image/jpg": "image/jpeg",
    "audio/x-wav": "audio/wav",
    "audio/wave": "audio/wav",
    "audio/x-m4a": "audio/mp4",
    "video/x-quicktime": "video/quicktime",
}


def normalize_content_filename(filename: str) -> str:
    """Normalize a display filename while rejecting all path syntax."""
    if not isinstance(filename, str):
        raise ContentValidationError("INVALID_CONTENT_FILENAME", "Content filename is invalid")
    normalized = unicodedata.normalize("NFKC", filename).strip()
    if (
        not normalized
        or normalized in {".", ".."}
        or "/" in normalized
        or "\\" in normalized
        or any(ord(character) < 32 or ord(character) == 127 for character in normalized)
    ):
        raise ContentValidationError("INVALID_CONTENT_FILENAME", "Content filename is invalid")
    safe = _SAFE_FILENAME_CHARACTER.sub("_", normalized).strip(".")
    if not safe or len(safe) > 255:
        raise ContentValidationError("INVALID_CONTENT_FILENAME", "Content filename is invalid")
    return safe


def detect_content_signature(header: bytes) -> DetectedContent:
    """Recognize only the conservative Phase 2 media allowlist."""
    detected: DetectedContent | None = None
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        detected = DetectedContent("image", "image/png", ".png", frozenset({".png"}))
    elif header.startswith(b"\xff\xd8\xff"):
        detected = DetectedContent(
            "image", "image/jpeg", ".jpg", frozenset({".jpg", ".jpeg"})
        )
    elif len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        detected = DetectedContent("image", "image/webp", ".webp", frozenset({".webp"}))
    elif len(header) >= 12 and header[4:8] == b"ftyp":
        major_brand = header[8:12]
        if major_brand == b"qt  ":
            detected = DetectedContent(
                "video", "video/quicktime", ".mov", frozenset({".mov"})
            )
        elif major_brand in {b"M4A ", b"M4B ", b"M4P "}:
            detected = DetectedContent(
                "audio", "audio/mp4", ".m4a", frozenset({".m4a", ".aac"})
            )
        else:
            detected = DetectedContent(
                "video", "video/mp4", ".mp4", frozenset({".mp4", ".m4v"})
            )
    elif header.startswith(b"\x1aE\xdf\xa3"):
        detected = DetectedContent("video", "video/webm", ".webm", frozenset({".webm"}))
    elif header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WAVE":
        detected = DetectedContent("audio", "audio/wav", ".wav", frozenset({".wav"}))
    elif header.startswith(b"OggS") and any(
        marker in header[:65536] for marker in (b"OpusHead", b"vorbis", b"Speex")
    ):
        detected = DetectedContent(
            "audio", "audio/ogg", ".ogg", frozenset({".ogg", ".opus"})
        )
    elif header.startswith(b"ID3") or (
        len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
    ):
        # ADTS uses layer bits 00; MPEG audio uses a non-zero layer value.
        if len(header) >= 2 and header[0] == 0xFF and header[1] & 0x06 == 0:
            detected = DetectedContent(
                "audio", "audio/aac", ".aac", frozenset({".aac"})
            )
        else:
            detected = DetectedContent(
                "audio", "audio/mpeg", ".mp3", frozenset({".mp3"})
            )
    if detected is None:
        raise ContentValidationError(
            "UNSUPPORTED_CONTENT_TYPE", "Content format is unsupported or malformed"
        )
    return detected


def validate_content_hints(
    filename: str, declared_mime_type: str | None, detected: DetectedContent
) -> str:
    """Validate extension/MIME hints and return a safe original filename."""
    safe_filename = normalize_content_filename(filename)
    extension = Path(safe_filename).suffix.lower()
    if extension and extension not in detected.allowed_extensions:
        raise ContentValidationError(
            "CONTENT_TYPE_MISMATCH",
            "Content filename extension does not match detected media type",
        )
    declared = (declared_mime_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    declared = _MIME_ALIASES.get(declared, declared)
    if declared not in {"", "application/octet-stream", detected.mime_type}:
        raise ContentValidationError(
            "CONTENT_TYPE_MISMATCH",
            "Declared content type does not match detected media type",
        )
    return safe_filename
