"""Production runtime configuration and encrypted credential tests."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import (
    ApplicationConfigurationError,
    bootstrap_application_config,
    load_application_config,
)
from app.database import DatabaseConfigurationError, DatabaseSettings, init_db, resolve_database_settings
from app.models import Device, Runtime, RuntimeNetworkConfig, RuntimeNetworkCredential
from app.services.network_credentials import (
    MasterKeyManager,
    NetworkCredentialError,
    NetworkCredentialProvider,
)
from app.services.network_secrets import SecretValue
from app.services.database_startup import DatabaseStartupError, DatabaseStartupValidator


def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in (
        "DATABASE_URL",
        "TIKTOK_MANAGER_RUNTIME_MODE",
        "TIKTOK_MANAGER_CONFIG",
        "TIKTOK_MANAGER_CREDENTIAL_KEY_PATH",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))


def test_default_database_is_authoritative_per_user_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clean_environment(monkeypatch, tmp_path)

    settings = resolve_database_settings()

    assert settings.mode == "operational"
    assert settings.sqlite_path == tmp_path / "data/tiktok-manager/tiktok_manager.db"
    assert "backend/tiktok_manager.db" not in settings.url


def test_explicit_development_database_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clean_environment(monkeypatch, tmp_path)
    override = tmp_path / "development.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{override}")

    settings = resolve_database_settings()

    assert settings.mode == "development-override"
    assert settings.sqlite_path == override


def test_production_rejects_repository_local_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_database = Path(__file__).parents[2] / "backend/tiktok_manager.db"
    monkeypatch.setenv("TIKTOK_MANAGER_RUNTIME_MODE", "production")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{repository_database}")

    with pytest.raises(DatabaseConfigurationError, match="inside the repository"):
        resolve_database_settings()


def test_operational_config_cannot_redirect_canonical_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clean_environment(monkeypatch, tmp_path)
    config = bootstrap_application_config()
    text = config.config_path.read_text(encoding="utf-8").replace(
        str(config.database_path), str(tmp_path / "alternate.db")
    )
    config.config_path.write_text(text, encoding="utf-8")
    config.config_path.chmod(0o600)

    with pytest.raises(DatabaseConfigurationError, match="canonical"):
        resolve_database_settings()


def test_startup_does_not_create_missing_database(tmp_path: Path) -> None:
    path = tmp_path / "missing/operational.db"
    engine = create_engine(f"sqlite:///{path}")
    validator = DatabaseStartupValidator(
        engine, DatabaseSettings(f"sqlite:///{path}", "operational", path)
    )

    with pytest.raises(DatabaseStartupError, match="does not exist"):
        validator.validate()

    assert not path.exists()
    engine.dispose()


def test_startup_accepts_integral_current_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clean_environment(monkeypatch, tmp_path)
    path = tmp_path / "operational.db"
    url = f"sqlite:///{path}"
    monkeypatch.setenv("DATABASE_URL", url)
    alembic = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(alembic, "head")
    engine = create_engine(url)

    DatabaseStartupValidator(
        engine, DatabaseSettings(url, "development-override", path)
    ).validate()

    engine.dispose()


def test_config_bootstrap_is_private_persistent_and_loadable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clean_environment(monkeypatch, tmp_path)

    first = bootstrap_application_config()
    original = first.config_path.read_bytes()
    second = bootstrap_application_config()

    assert first == second
    assert second.database_path == tmp_path / "data/tiktok-manager/tiktok_manager.db"
    assert second.redroid_base_adb_port == 5554
    assert second.bridge_systemd_scope == "user"
    assert second.artifact_root == tmp_path / "data/tiktok-manager/artifacts"
    assert second.artifact_max_size_bytes == 100 * 1024 * 1024
    assert second.artifact_max_total_bytes == 1024 * 1024 * 1024
    assert second.artifact_retention_days == 30
    assert second.artifact_upload_retention_days == 7
    assert second.artifact_cleanup_interval_hours == 6
    assert second.content_root == tmp_path / "data/tiktok-manager/content"
    assert second.content_max_upload_bytes == 500 * 1024 * 1024
    assert second.content_max_total_bytes == 20 * 1024 * 1024 * 1024
    assert second.content_ffprobe_path == Path("/usr/bin/ffprobe")
    assert second.content_ffprobe_timeout_seconds == 30
    assert second.content_ffprobe_max_output_bytes == 1024 * 1024
    assert second.content_max_image_dimension == 32768
    assert second.content_max_image_pixels == 100_000_000
    assert second.content_max_image_frames == 500
    assert stat.S_IMODE(first.config_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(first.config_path.parent.stat().st_mode) == 0o700
    assert first.config_path.read_bytes() == original
    assert load_application_config() == first


def test_config_loader_rejects_symlink(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clean_environment(monkeypatch, tmp_path)
    real = tmp_path / "real.toml"
    real.write_text("not trusted", encoding="utf-8")
    link = tmp_path / "config-link.toml"
    link.symlink_to(real)

    with pytest.raises(ApplicationConfigurationError, match="unsafe"):
        load_application_config(link)


def test_config_bootstrap_adds_new_retention_defaults_without_overwriting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clean_environment(monkeypatch, tmp_path)
    first = bootstrap_application_config()
    legacy = "\n".join(
        line
        for line in first.config_path.read_text(encoding="utf-8").splitlines()
        if not line.startswith(
            (
                "artifact_max_total_bytes",
                "artifact_retention_days",
                "artifact_upload_retention_days",
                "artifact_cleanup_interval_hours",
            )
        )
    )
    legacy = legacy.replace(
        "artifact_max_size_bytes = 104857600",
        "artifact_max_size_bytes = 52428800",
    )
    first.config_path.write_text(legacy + "\n", encoding="utf-8")
    first.config_path.chmod(0o600)

    upgraded = bootstrap_application_config()

    assert upgraded.artifact_max_size_bytes == 50 * 1024 * 1024
    assert upgraded.artifact_max_total_bytes == 1024 * 1024 * 1024
    assert upgraded.artifact_retention_days == 30
    assert upgraded.content_root == tmp_path / "data/tiktok-manager/content"
    assert upgraded.content_max_upload_bytes == 500 * 1024 * 1024
    assert upgraded.content_max_total_bytes == 20 * 1024 * 1024 * 1024
    text = first.config_path.read_text(encoding="utf-8")
    assert text.count("[content]") == 1
    assert stat.S_IMODE(first.config_path.stat().st_mode) == 0o600


def credential_database(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'credentials.db'}")
    init_db(engine)
    with Session(engine, expire_on_commit=False) as session:
        device = Device(
            name="Credential Device",
            device_type="virtual",
            platform="android",
            os_version="12",
            status="offline",
        )
        runtime = Runtime(
            name="Credential Runtime",
            runtime_type="redroid",
            status="stopped",
            docker_container_name="credential-runtime",
            adb_serial="localhost:5999",
        )
        device.runtimes.append(runtime)
        session.add(device)
        session.commit()
        session.add(
            RuntimeNetworkConfig(
                runtime_id=runtime.id,
                mode="http_proxy",
                proxy_host="proxy.example.test",
                proxy_port=3128,
                credential_source="stored_encrypted",
                bridge_host_port=18999,
                bridge_device_port=18888,
                desired_revision=1,
            )
        )
        session.commit()
        runtime_id = runtime.id
    return engine, runtime_id


def test_master_key_creation_persistence_and_encrypted_round_trip(
    tmp_path: Path,
) -> None:
    engine, runtime_id = credential_database(tmp_path)
    key_path = tmp_path / "config/credentials.key"
    manager = MasterKeyManager(key_path)
    provider = NetworkCredentialProvider(manager)
    username = "credential-user-plaintext"
    password = "credential-password-plaintext"
    with Session(engine) as session:
        provider.replace(
            session, runtime_id, SecretValue(username), SecretValue(password)
        )
        session.commit()
        config = session.scalar(
            select(RuntimeNetworkConfig).where(
                RuntimeNetworkConfig.runtime_id == runtime_id
            )
        )
        resolved = provider.resolve(session, config)
        stored = session.get(RuntimeNetworkCredential, runtime_id)
        assert stored.encrypted_username != username.encode()
        assert stored.encrypted_password != password.encode()
        assert resolved.username.reveal() == username
        assert resolved.password.reveal() == password

    first_key = key_path.read_bytes()
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    assert manager.load_or_create(encrypted_credentials_exist=True) == first_key
    dump = (tmp_path / "credentials.db").read_bytes()
    assert username.encode() not in dump
    assert password.encode() not in dump
    engine.dispose()


def test_missing_or_wrong_master_key_fails_existing_encrypted_credentials(
    tmp_path: Path,
) -> None:
    engine, runtime_id = credential_database(tmp_path)
    key_path = tmp_path / "config/credentials.key"
    provider = NetworkCredentialProvider(MasterKeyManager(key_path))
    with Session(engine) as session:
        provider.replace(
            session,
            runtime_id,
            SecretValue("secret-user"),
            SecretValue("secret-password"),
        )
        session.commit()
    key_path.unlink()
    with Session(engine) as session:
        config = session.scalar(
            select(RuntimeNetworkConfig).where(
                RuntimeNetworkConfig.runtime_id == runtime_id
            )
        )
        with pytest.raises(NetworkCredentialError, match="key is missing"):
            provider.resolve(session, config)

    key_path.write_bytes(Fernet.generate_key())
    key_path.chmod(0o600)
    with Session(engine) as session:
        with pytest.raises(NetworkCredentialError, match="cannot decrypt"):
            provider.ensure_key(session)
        config = session.scalar(
            select(RuntimeNetworkConfig).where(
                RuntimeNetworkConfig.runtime_id == runtime_id
            )
        )
        with pytest.raises(NetworkCredentialError, match="cannot be decrypted"):
            provider.resolve(session, config)
    engine.dispose()


def test_master_key_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_bytes(Fernet.generate_key())
    target.chmod(0o600)
    link = tmp_path / "credentials.key"
    link.symlink_to(target)

    with pytest.raises(NetworkCredentialError, match="unsafe"):
        MasterKeyManager(link).load_or_create(encrypted_credentials_exist=False)


def test_user_service_uses_native_user_manager_and_contains_no_secrets() -> None:
    service = (
        Path(__file__).parents[2] / "deploy/tiktok-manager-backend.service"
    ).read_text(encoding="utf-8")

    assert "--host 127.0.0.1 --port 8000" in service
    assert "Restart=on-failure" in service
    assert "TIKTOK_MANAGER_RUNTIME_MODE=production" in service
    assert "XDG_RUNTIME_DIR" not in service
    assert "DBUS_SESSION_BUS_ADDRESS" not in service
    assert "TIKTOK_PROXY_" not in service
    assert "credentials.key" not in service
    assert "WorkingDirectory=@PROJECT_ROOT@/backend" in service
    assert "@PROJECT_ROOT@/backend/.venv/bin/python" in service

    installer = (
        Path(__file__).parents[2] / "scripts/install-tiktok-manager.sh"
    ).read_text(encoding="utf-8")
    assert "alembic\" upgrade head" in installer
    assert "app.bootstrap --ensure-key" in installer
    assert "systemctl --user enable --now" in installer
    assert "Configured ffprobe is missing or unsafe" in installer


def test_worker_and_artifact_cleanup_service_assets_are_production_safe() -> None:
    root = Path(__file__).parents[2]
    worker = (root / "deploy/tiktok-manager-worker.service").read_text(
        encoding="utf-8"
    )
    cleanup = (
        root / "deploy/tiktok-manager-artifact-cleanup.service"
    ).read_text(encoding="utf-8")
    timer = (
        root / "deploy/tiktok-manager-artifact-cleanup.timer"
    ).read_text(encoding="utf-8")
    installer = (root / "scripts/install-tiktok-manager.sh").read_text(
        encoding="utf-8"
    )

    assert "After=tiktok-manager-backend.service" in worker
    assert "WorkingDirectory=@PROJECT_ROOT@/workers" in worker
    assert "@PROJECT_ROOT@/backend/.venv/bin/python -m worker" in worker
    assert "WORKER_BACKEND_URL=http://127.0.0.1:8000" in worker
    assert "PYTHONDONTWRITEBYTECODE=1" in worker
    assert "Restart=on-failure" in worker
    assert "claim_token" not in worker.lower()
    assert "password" not in worker.lower()
    assert "python -m app.artifact_cleanup" in cleanup
    assert "OnUnitActiveSec=@CLEANUP_INTERVAL@h" in timer
    assert "Persistent=true" in timer
    assert "enable --now tiktok-manager-worker.service" in installer
    assert "enable --now tiktok-manager-artifact-cleanup.timer" in installer
