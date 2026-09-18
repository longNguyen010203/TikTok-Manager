"""Tests for Alembic migrations."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

LATEST_REVISION = "20260918_0001"


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
        assert "accounts" in inspector.get_table_names()
        assert "alembic_version" in inspector.get_table_names()

        with test_engine.connect() as connection:
            migration_context = MigrationContext.configure(connection)
            assert migration_context.get_current_revision() == LATEST_REVISION
    finally:
        test_engine.dispose()
