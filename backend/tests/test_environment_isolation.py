"""Focused environment, database, state-root, and Alembic safety tests."""

from pathlib import Path

import pytest
from app.config import ApplicationConfigurationError, load_application_config
from app.database import DatabaseConfigurationError, resolve_database_settings
from app.environment import (
    EnvironmentConfigurationError,
    ManagerEnvironment,
    resolve_environment,
    resolve_environment_settings,
)


def _select(monkeypatch: pytest.MonkeyPatch, name: str, home: Path) -> None:
    monkeypatch.setenv("TIKTOK_MANAGER_ENV", name)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TIKTOK_MANAGER_CONFIG", raising=False)


def test_production_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _select(monkeypatch, "production", tmp_path)
    settings = resolve_environment_settings()
    database = resolve_database_settings()

    assert settings.environment is ManagerEnvironment.PRODUCTION
    assert settings.data_root == tmp_path / ".local/share/tiktok-manager"
    assert settings.database_path == settings.data_root / "tiktok_manager.db"
    assert database.sqlite_path == settings.database_path
    assert settings.host_reconciliation_enabled is True


def test_development_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _select(monkeypatch, "development", tmp_path)
    settings = resolve_environment_settings()
    database = resolve_database_settings()
    config = load_application_config()

    assert settings.data_root == tmp_path / ".local/share/tiktok-manager-dev"
    assert settings.database_path == settings.data_root / "tiktok_manager.db"
    assert database.sqlite_path == settings.database_path
    assert config.artifact_root == settings.data_root / "artifacts"
    assert config.content_root == settings.data_root / "content"
    assert config.redroid_data_root == settings.data_root / "redroid"
    assert settings.host_reconciliation_enabled is False


def test_test_database_is_isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TIKTOK_MANAGER_ENV", "test")
    monkeypatch.setenv("TIKTOK_MANAGER_TEST_ROOT", str(tmp_path / "isolated"))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = resolve_database_settings()

    assert settings.sqlite_path == tmp_path / "isolated/tiktok_manager.db"


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(EnvironmentConfigurationError, match="must be one of"):
        resolve_environment({"TIKTOK_MANAGER_ENV": "staging"})


@pytest.mark.parametrize("environment", ["development", "test"])
def test_nonproduction_rejects_production_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, environment: str
) -> None:
    _select(monkeypatch, environment, tmp_path)
    if environment == "test":
        monkeypatch.setenv("TIKTOK_MANAGER_TEST_ROOT", str(tmp_path / "test"))
    production = tmp_path / ".local/share/tiktok-manager/tiktok_manager.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{production}")

    with pytest.raises(DatabaseConfigurationError):
        resolve_database_settings()


def test_production_rejects_development_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _select(monkeypatch, "production", tmp_path)
    development = tmp_path / ".local/share/tiktok-manager-dev/tiktok_manager.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{development}")

    with pytest.raises(DatabaseConfigurationError, match="canonical"):
        resolve_database_settings()


def test_development_rejects_production_mutable_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _select(monkeypatch, "development", tmp_path)
    monkeypatch.setenv(
        "TIKTOK_MANAGER_ARTIFACT_ROOT",
        str(tmp_path / ".local/share/tiktok-manager/artifacts"),
    )

    with pytest.raises(ApplicationConfigurationError):
        load_application_config()


def test_alembic_uses_central_database_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _select(monkeypatch, "development", tmp_path)
    alembic_env = (Path(__file__).parents[1] / "alembic/env.py").read_text()

    assert "resolve_database_settings().url" in alembic_env
    assert resolve_database_settings().sqlite_path == (
        tmp_path / ".local/share/tiktok-manager-dev/tiktok_manager.db"
    )


def test_prepared_service_contracts_are_environment_pinned() -> None:
    root = Path(__file__).parents[2]
    production_backend = (
        root / "deploy/production/tiktok-manager-backend.service"
    ).read_text()
    production_worker = (
        root / "deploy/production/tiktok-manager-worker.service"
    ).read_text()
    development_backend = (
        root / "deploy/development/tiktok-manager-backend-dev.service"
    ).read_text()
    development_worker = (
        root / "deploy/development/tiktok-manager-worker-dev.service"
    ).read_text()

    assert "TikTok-Manager-prod/backend/.venv/bin/python" in production_backend
    assert "--host 127.0.0.1 --port 8000" in production_backend
    assert "TIKTOK_MANAGER_ENV=production" in production_backend
    assert "WORKER_BACKEND_URL=http://127.0.0.1:8000" in production_worker
    assert "--host 127.0.0.1 --port 8001" in development_backend
    assert "TIKTOK_MANAGER_ENV=development" in development_backend
    assert "WORKER_BACKEND_URL=http://127.0.0.1:8001" in development_worker
