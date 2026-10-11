"""Consistent, non-overwriting SQLite backup helper for release operations."""

from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.environment import ManagerEnvironment, resolve_environment_settings


class ProductionBackupError(RuntimeError):
    """Raised when a production backup cannot be completed safely."""


def backup_production_database(*, now: datetime | None = None) -> Path:
    settings = resolve_environment_settings()
    if settings.environment is not ManagerEnvironment.PRODUCTION:
        raise ProductionBackupError("backup requires TIKTOK_MANAGER_ENV=production")

    source_path = settings.database_path
    if not source_path.is_file() or source_path.is_symlink():
        raise ProductionBackupError(f"production database is missing or unsafe: {source_path}")

    backup_directory = settings.data_root / "backups"
    backup_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if backup_directory.is_symlink() or not backup_directory.is_dir():
        raise ProductionBackupError(f"backup directory is unsafe: {backup_directory}")
    os.chmod(backup_directory, 0o700)

    timestamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%S.%fZ")
    destination_path = backup_directory / f"tiktok_manager-{timestamp}.db"
    try:
        descriptor = os.open(destination_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ProductionBackupError(f"backup already exists: {destination_path}") from error
    else:
        os.close(descriptor)

    source_uri = f"{source_path.as_uri()}?mode=ro"
    try:
        with sqlite3.connect(source_uri, uri=True) as source:
            with sqlite3.connect(destination_path) as destination:
                source.backup(destination)
                result = destination.execute("PRAGMA integrity_check").fetchone()
                if result != ("ok",):
                    raise ProductionBackupError(
                        f"backup integrity check failed: {result!r}"
                    )
        os.chmod(destination_path, 0o600)
        with destination_path.open("rb") as backup_file:
            os.fsync(backup_file.fileno())
        directory_fd = os.open(backup_directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception as error:
        failed_path = destination_path.with_suffix(".db.failed")
        try:
            if not failed_path.exists():
                destination_path.rename(failed_path)
        except OSError:
            pass
        if isinstance(error, ProductionBackupError):
            raise
        raise ProductionBackupError(f"production backup failed: {error}") from error
    return destination_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        destination = backup_production_database()
    except ProductionBackupError as error:
        parser.exit(1, f"backup error: {error}\n")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
