"""Tests for database setup and models."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.database import init_db
from app.models import Account, Device, Runtime


@pytest.fixture
def database_engine(tmp_path: Path) -> Iterator[Engine]:
    database_url = URL.create(
        drivername="sqlite", database=str(tmp_path / "test.db")
    )
    test_engine = create_engine(database_url)
    yield test_engine
    test_engine.dispose()


def test_init_db_creates_application_tables(database_engine: Engine) -> None:
    init_db(database_engine)
    init_db(database_engine)

    inspector = inspect(database_engine)
    assert {"accounts", "devices", "runtimes"}.issubset(
        inspector.get_table_names()
    )

    columns = {column["name"]: column for column in inspector.get_columns("accounts")}
    assert set(columns) == {
        "id",
        "name",
        "username",
        "platform",
        "status",
        "notes",
        "runtime_id",
        "created_at",
        "updated_at",
    }
    assert columns["id"]["primary_key"] == 1
    assert columns["notes"]["nullable"] is True
    assert columns["runtime_id"]["nullable"] is True
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


def test_device_runtime_and_account_relationships(database_engine: Engine) -> None:
    init_db(database_engine)
    device = Device(
        name="Local Android Device",
        device_type="physical",
        platform="android",
        os_version="15",
        status="online",
    )
    runtime = Runtime(
        name="TikTok Runtime",
        runtime_type="app",
        status="running",
    )
    device.runtimes.append(runtime)
    account = Account(
        name="Assigned Account",
        username="assigned",
        platform="tiktok",
        status="active",
        runtime=runtime,
    )

    with Session(database_engine) as session:
        session.add_all([device, account])
        session.commit()
        session.refresh(device)
        session.refresh(runtime)
        session.refresh(account)

        assert runtime.device_id == device.id
        assert runtime in device.runtimes
        assert account.runtime_id == runtime.id
        assert account.runtime is runtime
        assert account in runtime.accounts

        session.delete(runtime)
        session.commit()
        session.refresh(account)

        assert account.runtime_id is None
        assert account.runtime is None
