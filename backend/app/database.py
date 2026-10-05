"""Authoritative database resolution, engine, session, and schema setup."""

import os
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import default_data_directory, load_application_config


class DatabaseConfigurationError(ValueError):
    """Raised when production database resolution is unsafe."""


@dataclass(frozen=True)
class DatabaseSettings:
    url: str
    mode: str
    sqlite_path: Path | None


def resolve_database_settings() -> DatabaseSettings:
    explicit = os.getenv("DATABASE_URL")
    runtime_mode = os.getenv("TIKTOK_MANAGER_RUNTIME_MODE", "").strip().lower()
    if explicit:
        url = explicit
        mode = "production-override" if runtime_mode == "production" else "development-override"
    else:
        application = load_application_config()
        url = URL.create(
            drivername="sqlite", database=str(application.database_path)
        ).render_as_string(hide_password=False)
        mode = "operational"
    parsed = make_url(url)
    sqlite_path: Path | None = None
    if parsed.drivername.startswith("sqlite") and parsed.database not in {None, "", ":memory:"}:
        sqlite_path = Path(parsed.database).expanduser().resolve()
        if runtime_mode == "production" or mode == "operational":
            repository_root = Path(__file__).resolve().parents[2]
            if sqlite_path == repository_root or repository_root in sqlite_path.parents:
                raise DatabaseConfigurationError(
                    "Production database must not be located inside the repository"
                )
        if mode == "operational":
            canonical_path = (default_data_directory() / "tiktok_manager.db").resolve()
            if sqlite_path != canonical_path:
                raise DatabaseConfigurationError(
                    "Operational database path must be the canonical per-user database"
                )
        if runtime_mode == "production":
            canonical_path = (default_data_directory() / "tiktok_manager.db").resolve()
            if sqlite_path != canonical_path:
                raise DatabaseConfigurationError(
                    "Production database must be the canonical per-user database"
                )
    elif runtime_mode == "production":
        raise DatabaseConfigurationError(
            "Production runtime requires the canonical SQLite database"
        )
    return DatabaseSettings(url=url, mode=mode, sqlite_path=sqlite_path)


DATABASE_SETTINGS = resolve_database_settings()
DATABASE_URL = DATABASE_SETTINGS.url


def _connect_args(database_url: str) -> dict[str, bool]:
    """Return driver options needed by the configured database."""
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(DATABASE_URL, connect_args=_connect_args(DATABASE_URL))


def _enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    """Enable SQLite FK actions for every application connection.

    SQLite defaults foreign-key enforcement off per connection.  Relying on a
    one-time startup PRAGMA leaves pooled and service-specific connections able
    to create dangling references during deletes.
    """
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


if DATABASE_URL.startswith("sqlite"):
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)

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
