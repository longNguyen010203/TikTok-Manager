"""Tests for Alembic migrations."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

INITIAL_REVISION = "20260918_0001"
LATEST_REVISION = "20260918_0002"


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
        assert {"accounts", "devices", "runtimes"}.issubset(
            inspector.get_table_names()
        )
        assert "alembic_version" in inspector.get_table_names()
        account_columns = {
            column["name"] for column in inspector.get_columns("accounts")
        }
        assert "runtime_id" in account_columns

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
