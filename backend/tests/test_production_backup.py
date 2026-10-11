"""Tests for the consistent production SQLite backup helper."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.environment import resolve_environment_settings
from app.production_backup import ProductionBackupError, backup_production_database


def test_backup_is_consistent_and_never_overwrites(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TIKTOK_MANAGER_ENV", "production")
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = resolve_environment_settings()
    settings.data_root.mkdir(parents=True)
    with sqlite3.connect(settings.database_path) as database:
        database.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        database.execute("INSERT INTO marker VALUES ('safe')")
    instant = datetime(2026, 10, 12, 1, 2, 3, 456789, tzinfo=UTC)

    backup = backup_production_database(now=instant)

    assert backup.parent == settings.data_root / "backups"
    assert backup.name == "tiktok_manager-20261012T010203.456789Z.db"
    with sqlite3.connect(backup) as database:
        assert database.execute("SELECT value FROM marker").fetchone() == ("safe",)
        assert database.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    with pytest.raises(ProductionBackupError, match="already exists"):
        backup_production_database(now=instant)


def test_backup_requires_explicit_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TIKTOK_MANAGER_ENV", "development")

    with pytest.raises(ProductionBackupError, match="requires"):
        backup_production_database()
