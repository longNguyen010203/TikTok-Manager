"""Tests for Alembic migrations."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

INITIAL_REVISION = "20260918_0001"
PRE_JOB_REVISION = "20260918_0002"
PRE_JOB_LOG_REVISION = "20260918_0003"
LATEST_REVISION = "20260918_0004"


def test_upgrade_head_creates_accounts_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "migration.db"
    database_url = URL.create(drivername="sqlite", database=str(database_path))
    monkeypatch.setenv("DATABASE_URL", database_url.render_as_string(hide_password=False))

    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")

    test_engine = create_engine(database_url)
    try:
        inspector = inspect(test_engine)
        assert {"accounts", "devices", "job_logs", "jobs", "runtimes"}.issubset(
            inspector.get_table_names()
        )
        assert "alembic_version" in inspector.get_table_names()
        account_columns = {
            column["name"] for column in inspector.get_columns("accounts")
        }
        assert "runtime_id" in account_columns
        job_columns = {
            column["name"]: column for column in inspector.get_columns("jobs")
        }
        assert {
            "id",
            "job_type",
            "status",
            "account_id",
            "runtime_id",
            "payload",
            "result",
            "error_message",
            "attempt_count",
            "max_attempts",
            "scheduled_at",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        } == set(job_columns)
        assert job_columns["account_id"]["nullable"] is True
        assert job_columns["runtime_id"]["nullable"] is True

        job_foreign_keys = {
            tuple(foreign_key["constrained_columns"]): foreign_key
            for foreign_key in inspector.get_foreign_keys("jobs")
        }
        assert job_foreign_keys[("account_id",)]["referred_table"] == "accounts"
        assert job_foreign_keys[("account_id",)]["options"]["ondelete"] == "SET NULL"
        assert job_foreign_keys[("runtime_id",)]["referred_table"] == "runtimes"
        assert job_foreign_keys[("runtime_id",)]["options"]["ondelete"] == "SET NULL"

        job_log_columns = {
            column["name"] for column in inspector.get_columns("job_logs")
        }
        assert job_log_columns == {
            "id",
            "job_id",
            "level",
            "message",
            "metadata",
            "created_at",
        }
        job_log_foreign_key = inspector.get_foreign_keys("job_logs")[0]
        assert job_log_foreign_key["referred_table"] == "jobs"
        assert job_log_foreign_key["options"]["ondelete"] == "CASCADE"

        with test_engine.connect() as connection:
            migration_context = MigrationContext.configure(connection)
            assert migration_context.get_current_revision() == LATEST_REVISION
    finally:
        test_engine.dispose()


def test_upgrade_preserves_existing_accounts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "existing.db"
    database_url = URL.create(drivername="sqlite", database=str(database_path))
    monkeypatch.setenv("DATABASE_URL", database_url.render_as_string(hide_password=False))
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, INITIAL_REVISION)
    test_engine = create_engine(database_url)
    try:
        with test_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        name, username, platform, status, notes,
                        created_at, updated_at
                    ) VALUES (
                        'Existing Account', 'existing', 'tiktok', 'active', NULL,
                        '2026-09-18 00:00:00', '2026-09-18 00:00:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with test_engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT name, username, runtime_id FROM accounts "
                    "WHERE username = 'existing'"
                )
            ).one()
            migration_context = MigrationContext.configure(connection)
            current_revision = migration_context.get_current_revision()

        assert row.name == "Existing Account"
        assert row.username == "existing"
        assert row.runtime_id is None
        assert current_revision == LATEST_REVISION
    finally:
        test_engine.dispose()


def test_job_migration_preserves_existing_device_runtime_and_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "pre-job.db"
    database_url = URL.create(drivername="sqlite", database=str(database_path))
    monkeypatch.setenv("DATABASE_URL", database_url.render_as_string(hide_password=False))
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, PRE_JOB_REVISION)
    test_engine = create_engine(database_url)
    try:
        with test_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO devices (
                        id, name, device_type, platform, os_version, status,
                        notes, created_at, updated_at
                    ) VALUES (
                        1, 'Existing Device', 'physical', 'android', '15',
                        'online', NULL, '2026-09-18 00:00:00',
                        '2026-09-18 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO runtimes (
                        id, device_id, name, runtime_type, status, last_seen_at,
                        created_at, updated_at
                    ) VALUES (
                        1, 1, 'Existing Runtime', 'app', 'running', NULL,
                        '2026-09-18 00:00:00', '2026-09-18 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        id, name, username, platform, status, notes, runtime_id,
                        created_at, updated_at
                    ) VALUES (
                        1, 'Existing Account', 'existing-job-target', 'tiktok',
                        'active', NULL, 1, '2026-09-18 00:00:00',
                        '2026-09-18 00:00:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with test_engine.connect() as connection:
            device_name = connection.scalar(text("SELECT name FROM devices WHERE id = 1"))
            runtime_row = connection.execute(
                text("SELECT name, device_id FROM runtimes WHERE id = 1")
            ).one()
            account_row = connection.execute(
                text("SELECT username, runtime_id FROM accounts WHERE id = 1")
            ).one()
            migration_context = MigrationContext.configure(connection)
            current_revision = migration_context.get_current_revision()

        assert device_name == "Existing Device"
        assert runtime_row == ("Existing Runtime", 1)
        assert account_row == ("existing-job-target", 1)
        assert current_revision == LATEST_REVISION
    finally:
        test_engine.dispose()


def test_job_log_migration_preserves_existing_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "pre-job-log.db"
    database_url = URL.create(drivername="sqlite", database=str(database_path))
    monkeypatch.setenv("DATABASE_URL", database_url.render_as_string(hide_password=False))
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, PRE_JOB_LOG_REVISION)
    test_engine = create_engine(database_url)
    try:
        with test_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO jobs (
                        id, job_type, status, account_id, runtime_id, payload,
                        result, error_message, attempt_count, max_attempts,
                        scheduled_at, started_at, completed_at,
                        created_at, updated_at
                    ) VALUES (
                        1, 'existing_job', 'failed', NULL, NULL, '{"key": 1}',
                        NULL, 'Existing failure', 1, 3, NULL,
                        '2026-09-18 00:00:00', '2026-09-18 00:01:00',
                        '2026-09-18 00:00:00', '2026-09-18 00:01:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with test_engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT job_type, status, attempt_count, error_message "
                    "FROM jobs WHERE id = 1"
                )
            ).one()
            migration_context = MigrationContext.configure(connection)
            current_revision = migration_context.get_current_revision()

        assert row == ("existing_job", "failed", 1, "Existing failure")
        assert current_revision == LATEST_REVISION
    finally:
        test_engine.dispose()
