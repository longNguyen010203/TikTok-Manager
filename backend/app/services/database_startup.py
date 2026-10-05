"""Fail-closed startup diagnostics for the authoritative operational database."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import DatabaseSettings
from app.services.network_credentials import NetworkCredentialProvider
from app.services.redroid_provisioning_config import RedroidProvisioningSettings

# Uvicorn configures this logger for the installed service, making the database
# identity visible in the journal without requiring a separate logging setup.
logger = logging.getLogger("uvicorn.error")
LATEST_ALEMBIC_REVISION = "20261005_0017"


class DatabaseStartupError(RuntimeError):
    """Raised when the configured operational database is unsafe or incompatible."""


class DatabaseStartupValidator:
    def __init__(
        self,
        engine: Engine,
        settings: DatabaseSettings,
        credential_provider: NetworkCredentialProvider | None = None,
    ) -> None:
        self.engine = engine
        self.settings = settings
        self.credential_provider = credential_provider

    def validate(self) -> None:
        if self.settings.sqlite_path is not None and not self.settings.sqlite_path.is_file():
            raise DatabaseStartupError(
                "Configured database does not exist; run the TikTok Manager installer"
            )
        try:
            with self.engine.connect() as connection:
                if connection.dialect.name == "sqlite":
                    integrity = connection.execute(
                        text("PRAGMA integrity_check")
                    ).scalar_one()
                    if integrity != "ok":
                        raise DatabaseStartupError(
                            "Operational database integrity check failed"
                        )
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
        except DatabaseStartupError:
            raise
        except SQLAlchemyError as error:
            raise DatabaseStartupError(
                "Operational database is unavailable or not initialized"
            ) from error
        if revision != LATEST_ALEMBIC_REVISION:
            raise DatabaseStartupError(
                "Operational database migration revision is incompatible"
            )
        # This validates durable provisioning settings before host mutations.
        RedroidProvisioningSettings.from_environment()
        if self.credential_provider is not None:
            with Session(self.engine) as session:
                # Creates the installation key only when no encrypted rows exist.
                # A missing/wrong key with stored credentials fails closed.
                self.credential_provider.ensure_key(session)
        logger.info(
            "Database ready: mode=%s path=%s alembic_revision=%s",
            self.settings.mode,
            str(self.settings.sqlite_path) if self.settings.sqlite_path else "non-sqlite",
            revision,
        )
