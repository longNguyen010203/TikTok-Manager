"""Application database connection invariants."""

from __future__ import annotations

import sqlite3

from app.database import _enable_sqlite_foreign_keys


def test_sqlite_connection_enables_foreign_keys() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (0,)
        _enable_sqlite_foreign_keys(connection, object())
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
    finally:
        connection.close()
