"""Tests for database setup and models."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.database import init_db
from app.models import Account


@pytest.fixture
def database_engine(tmp_path: Path) -> Iterator[Engine]:
    database_url = URL.create(
        drivername="sqlite", database=str(tmp_path / "test.db")
    )
    test_engine = create_engine(database_url)
    yield test_engine
    test_engine.dispose()


def test_init_db_creates_account_table(database_engine: Engine) -> None:
    init_db(database_engine)
    init_db(database_engine)

    inspector = inspect(database_engine)
    assert "accounts" in inspector.get_table_names()

    columns = {column["name"]: column for column in inspector.get_columns("accounts")}
    assert set(columns) == {
        "id",
        "name",
        "username",
        "platform",
        "status",
        "notes",
        "created_at",
        "updated_at",
    }
    assert columns["id"]["primary_key"] == 1
    assert columns["notes"]["nullable"] is True
    for field in (
        "name",
        "username",
        "platform",
        "status",
        "created_at",
        "updated_at",
    ):
        assert columns[field]["nullable"] is False


def test_account_can_be_persisted(database_engine: Engine) -> None:
    init_db(database_engine)
    account = Account(
        name="Primary TikTok Account",
        username="creator",
        platform="tiktok",
        status="active",
    )

    with Session(database_engine) as session:
        session.add(account)
        session.commit()
        session.refresh(account)

    assert account.id is not None
    assert account.notes is None
    assert account.created_at is not None
    assert account.updated_at is not None
