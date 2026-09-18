"""Database engine, session, and schema initialization."""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tiktok_manager.db")


def _connect_args(database_url: str) -> dict[str, bool]:
    """Return driver options needed by the configured database."""
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(DATABASE_URL, connect_args=_connect_args(DATABASE_URL))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for database models."""


def get_db() -> Generator[Session, None, None]:
    """Provide a database session and ensure it is closed afterward."""
    with SessionLocal() as session:
        yield session


def init_db(bind: Engine | None = None) -> None:
    """Create all application tables in the configured database."""
    import app.models  # noqa: F401

    Base.metadata.create_all(bind or engine)
