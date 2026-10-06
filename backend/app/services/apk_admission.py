"""Bounded structural admission for single-file Android APK packages."""

from __future__ import annotations

import zipfile
import stat
from pathlib import PurePosixPath
from typing import BinaryIO


class ApkAdmissionError(ValueError):
    def __init__(self, code: str, safe_message: str) -> None:
        self.code = code
        self.safe_message = safe_message
        super().__init__(safe_message)


def validate_apk_archive(
    stream: BinaryIO,
    *,
    max_entries: int,
    max_expanded_bytes: int,
    max_compression_ratio: int,
) -> None:
    if max_entries <= 0 or max_expanded_bytes <= 0 or max_compression_ratio <= 0:
        raise ApkAdmissionError("APK_ADMISSION_INVALID", "APK admission limits are invalid")
    try:
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > max_entries:
                raise ApkAdmissionError("APK_INVALID", "APK archive structure is invalid")
            expanded = 0
            manifest = False
            for entry in entries:
                name = entry.filename
                if not name or "\\" in name or name.startswith("/"):
                    raise ApkAdmissionError("APK_INVALID", "APK archive structure is invalid")
                path = PurePosixPath(name)
                if any(part in {"", ".", ".."} for part in path.parts):
                    raise ApkAdmissionError("APK_INVALID", "APK archive structure is invalid")
                if entry.flag_bits & 0x1:
                    raise ApkAdmissionError("APK_ENCRYPTED", "Encrypted APK entries are unsupported")
                unix_mode = entry.external_attr >> 16
                if unix_mode and stat.S_ISLNK(unix_mode):
                    raise ApkAdmissionError("APK_INVALID", "APK archive structure is invalid")
                expanded += entry.file_size
                if expanded > max_expanded_bytes:
                    raise ApkAdmissionError("APK_EXPANSION_LIMIT", "APK expanded size exceeds the safety limit")
                if entry.file_size and entry.file_size / max(1, entry.compress_size) > max_compression_ratio:
                    raise ApkAdmissionError("APK_COMPRESSION_LIMIT", "APK compression ratio exceeds the safety limit")
                if name == "AndroidManifest.xml" and not entry.is_dir() and entry.file_size > 0:
                    manifest = True
            if not manifest:
                raise ApkAdmissionError("APK_MANIFEST_MISSING", "APK manifest is missing")
    except ApkAdmissionError:
        raise
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError) as error:
        raise ApkAdmissionError("APK_INVALID", "APK archive is malformed") from error
