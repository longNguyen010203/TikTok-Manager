"""Fixtures for API and database integration tests."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, init_db
from app.main import create_app


@dataclass(frozen=True)
class IntegrationEnvironment:
    """Resources exposed to an integration test."""

    client: TestClient
    database_path: Path
    engine: Engine


@pytest.fixture
def integration_environment(tmp_path: Path) -> Iterator[IntegrationEnvironment]:
    """Run the real API against a fresh SQLite database for each test."""
    database_path = tmp_path / "integration.db"
    database_url = URL.create(drivername="sqlite", database=str(database_path))
    test_engine = create_engine(
        database_url, connect_args={"check_same_thread": False}
    )
    testing_session = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )
    init_db(test_engine)

    application = create_app()

    def override_get_db() -> Iterator[Session]:
        with testing_session() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(application) as client:
            yield IntegrationEnvironment(
                client=client,
                database_path=database_path,
                engine=test_engine,
            )
    finally:
        application.dependency_overrides.clear()
        test_engine.dispose()
