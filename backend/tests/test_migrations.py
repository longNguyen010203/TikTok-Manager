"""Tests for Alembic migrations."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

INITIAL_REVISION = "20260918_0001"
PRE_JOB_REVISION = "20260918_0002"
PRE_JOB_LOG_REVISION = "20260918_0003"
PRE_REDROID_CONFIG_REVISION = "20260918_0004"
PRE_UNIQUE_CONFIG_REVISION = "20261001_0005"
PRE_PROVISIONING_REVISION = "20261001_0006"
LATEST_REVISION = "20261007_0047"


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
        assert {
            "accounts",
            "devices",
            "job_logs",
            "jobs",
            "redroid_provisionings",
            "runtimes",
            "job_artifacts",
            "content_assets",
            "content_asset_versions",
            "content_asset_tags",
            "content_blobs",
            "content_variants",
            "content_deliveries",
            "content_events",
            "workflows",
            "workflow_steps",
            "workflow_step_job_runs",
            "workflow_events",
            "managed_apps",
            "managed_app_versions",
            "managed_app_events",
            "runtime_app_installations",
            "runtime_app_installation_runs",
            "publishing_sessions",
            "tiktok_ui_profiles",
            "account_tags",
            "account_secrets",
        }.issubset(
            inspector.get_table_names()
        )
        content_asset_columns = {
            column["name"]: column for column in inspector.get_columns("content_assets")
        }
        assert content_asset_columns["purpose"]["nullable"] is False
        managed_version_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("managed_app_versions")
        }
        assert ("managed_app_id", "sha256") in managed_version_uniques
        assert ("content_asset_version_id",) in managed_version_uniques
        managed_version_columns = {
            column["name"]: column
            for column in inspector.get_columns("managed_app_versions")
        }
        assert managed_version_columns["inspection_level"]["nullable"] is False
        assert "basic_approved_at" in managed_version_columns
        account_columns = {
            column["name"]: column for column in inspector.get_columns("accounts")
        }
        assert account_columns["username"]["nullable"] is True
        assert {
            "display_name", "email", "phone", "registration_state", "health_status",
            "status_reason", "niche", "archived_at", "follower_count",
            "following_count", "likes_count", "video_count", "metrics_updated_at",
        }.issubset(account_columns)
        runtime_app_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(
                "runtime_app_installations"
            )
        }
        assert ("runtime_id", "managed_app_id") in runtime_app_uniques
        runtime_app_fks = {
            tuple(foreign_key["constrained_columns"]): foreign_key
            for foreign_key in inspector.get_foreign_keys(
                "runtime_app_installations"
            )
        }
        assert runtime_app_fks[("runtime_id",)]["options"]["ondelete"] == "SET NULL"
        assert runtime_app_fks[("desired_managed_app_version_id",)]["options"]["ondelete"] == "RESTRICT"
        run_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(
                "runtime_app_installation_runs"
            )
        }
        assert ("job_id",) in run_uniques
        workflow_columns = {
            column["name"] for column in inspector.get_columns("workflows")
        }
        assert {"managed_app_id", "managed_app_version_id"}.issubset(workflow_columns)
        publishing_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("publishing_sessions")
        }
        assert ("workflow_id",) in publishing_uniques
        with test_engine.connect() as connection:
            profiles = connection.execute(text(
                "SELECT version, package_name, min_version_code, max_version_code, status "
                "FROM tiktok_ui_profiles ORDER BY version"
            )).all()
            assert profiles == [
                (1, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                (2, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                (3, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                (4, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                    (5, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                    (6, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                    (7, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                    (8, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                    (9, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                        (10, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                        (11, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                        (12, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                        (13, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                        (14, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                        (15, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                        (16, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                        (17, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                        (18, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                        (19, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                        (20, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                        (21, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                        (22, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                        (23, "com.ss.android.ugc.trill", 440403, 440403, "testing"),
                    ]
        assert "alembic_version" in inspector.get_table_names()
        assert {
            "runtime_network_configs",
            "runtime_network_config_revisions",
            "runtime_network_credentials",
            "runtime_network_states",
        }.issubset(inspector.get_table_names())
        delivery_columns = {
            column["name"]: column
            for column in inspector.get_columns("content_deliveries")
        }
        assert delivery_columns["import_media"]["nullable"] is False
        assert delivery_columns["remote_filename"]["nullable"] is False
        assert {"started_at", "completed_at"}.issubset(delivery_columns)
        delivery_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("content_deliveries")
        }
        assert (
            "content_asset_version_id", "runtime_id_snapshot", "idempotency_key"
        ) in delivery_uniques
        account_columns = {
            column["name"] for column in inspector.get_columns("accounts")
        }
        assert "runtime_id" in account_columns
        runtime_columns = {
            column["name"]: column
            for column in inspector.get_columns("runtimes")
        }
        assert runtime_columns["docker_container_name"]["nullable"] is True
        assert runtime_columns["adb_serial"]["nullable"] is True
        runtime_unique_constraints = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("runtimes")
        }
        assert ("docker_container_name",) in runtime_unique_constraints
        assert ("adb_serial",) in runtime_unique_constraints
        provisioning_columns = {
            column["name"]
            for column in inspector.get_columns("redroid_provisionings")
        }
        assert provisioning_columns == {
            "id", "idempotency_key", "request_fingerprint", "ownership_token",
            "installation_id", "state", "device_number", "container_name",
            "docker_container_id", "adb_host_port", "adb_serial", "data_path",
            "network_name", "docker_network_id", "image_reference", "device_id",
            "runtime_id", "data_directory_created", "network_created",
            "container_created", "historical_device_id", "historical_runtime_id",
            "container_removed", "network_removed", "data_preserved",
            "error_code", "error_message", "created_at", "updated_at",
        }
        provisioning_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(
                "redroid_provisionings"
            )
        }
        for column in (
            "idempotency_key", "ownership_token", "device_number",
            "container_name", "adb_host_port", "adb_serial", "data_path",
            "network_name", "device_id", "runtime_id",
        ):
            assert (column,) in provisioning_uniques
        job_columns = {
            column["name"]: column for column in inspector.get_columns("jobs")
        }
        assert {
            "id",
            "job_type",
            "status",
            "account_id",
            "runtime_id",
            "payload",
            "result",
            "error_message",
            "error_code",
            "error_retryable",
            "attempt_count",
            "max_attempts",
            "scheduled_at",
            "started_at",
            "completed_at",
            "claim_token_hash",
            "claimed_by",
            "claimed_at",
            "heartbeat_at",
            "lease_expires_at",
            "cancellation_requested_at",
            "execution_started_at",
            "execution_stage",
            "created_at",
            "updated_at",
        } == set(job_columns)
        assert job_columns["account_id"]["nullable"] is True
        assert job_columns["runtime_id"]["nullable"] is True

        job_foreign_keys = {
            tuple(foreign_key["constrained_columns"]): foreign_key
            for foreign_key in inspector.get_foreign_keys("jobs")
        }
        assert job_foreign_keys[("account_id",)]["referred_table"] == "accounts"
        assert job_foreign_keys[("account_id",)]["options"]["ondelete"] == "SET NULL"
        assert job_foreign_keys[("runtime_id",)]["referred_table"] == "runtimes"
        assert job_foreign_keys[("runtime_id",)]["options"]["ondelete"] == "SET NULL"

        job_log_columns = {
            column["name"] for column in inspector.get_columns("job_logs")
        }
        assert job_log_columns == {
            "id",
            "job_id",
            "level",
            "message",
            "event_type",
            "metadata",
            "created_at",
        }
        job_log_foreign_key = inspector.get_foreign_keys("job_logs")[0]
        assert job_log_foreign_key["referred_table"] == "jobs"
        assert job_log_foreign_key["options"]["ondelete"] == "CASCADE"

        network_config_columns = {
            column["name"] for column in inspector.get_columns("runtime_network_configs")
        }
        assert network_config_columns == {
            "id", "runtime_id", "mode", "proxy_host", "proxy_port",
            "proxy_username_secret_ref", "proxy_password_secret_ref",
            "credential_source",
            "bridge_host_port", "bridge_device_port", "desired_revision",
            "created_at", "updated_at",
        }
        network_config_fk = inspector.get_foreign_keys("runtime_network_configs")[0]
        assert network_config_fk["referred_table"] == "runtimes"
        assert network_config_fk["options"]["ondelete"] == "CASCADE"
        network_config_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("runtime_network_configs")
        }
        assert ("runtime_id",) in network_config_uniques
        assert ("bridge_host_port",) in network_config_uniques

        revision_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("runtime_network_config_revisions")
        }
        assert ("runtime_id", "revision") in revision_uniques
        state_columns = {
            column["name"] for column in inspector.get_columns("runtime_network_states")
        }
        assert {"runtime_id", "status", "desired_revision", "applied_revision", "observed_mode"}.issubset(state_columns)
        revision_columns = {
            column["name"]
            for column in inspector.get_columns(
                "runtime_network_config_revisions"
            )
        }
        assert "credential_source" in revision_columns
        credential_columns = {
            column["name"]
            for column in inspector.get_columns("runtime_network_credentials")
        }
        assert credential_columns == {
            "runtime_id",
            "encrypted_username",
            "encrypted_password",
            "encryption_version",
            "created_at",
            "updated_at",
        }
        artifact_columns = {
            column["name"] for column in inspector.get_columns("job_artifacts")
        }
        assert artifact_columns == {
            "id",
            "job_id",
            "kind",
            "original_filename",
            "storage_key",
            "mime_type",
            "size_bytes",
            "sha256",
            "created_at",
            "expires_at",
            "cleanup_status",
        }
        artifact_fk = inspector.get_foreign_keys("job_artifacts")[0]
        assert artifact_fk["referred_table"] == "jobs"
        assert artifact_fk["options"]["ondelete"] == "CASCADE"

        content_blob_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("content_blobs")
        }
        assert {("sha256",), ("storage_key",)}.issubset(content_blob_uniques)
        content_version_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("content_asset_versions")
        }
        assert ("content_asset_id", "version_number") in content_version_uniques
        assert ("inspection_job_id",) in content_version_uniques
        assert ("thumbnail_job_id",) in content_version_uniques
        content_version_fks = {
            tuple(foreign_key["constrained_columns"]): foreign_key
            for foreign_key in inspector.get_foreign_keys("content_asset_versions")
        }
        assert content_version_fks[("content_asset_id",)]["options"]["ondelete"] == "CASCADE"
        assert content_version_fks[("blob_id",)]["options"]["ondelete"] == "RESTRICT"
        assert content_version_fks[("source_job_artifact_id",)]["options"]["ondelete"] == "SET NULL"
        assert content_version_fks[("inspection_job_id",)]["referred_table"] == "jobs"
        assert content_version_fks[("inspection_job_id",)]["options"]["ondelete"] == "SET NULL"
        assert content_version_fks[("thumbnail_job_id",)]["referred_table"] == "jobs"
        assert content_version_fks[("thumbnail_job_id",)]["options"]["ondelete"] == "SET NULL"

        with test_engine.connect() as connection:
            migration_context = MigrationContext.configure(connection)
            assert migration_context.get_current_revision() == LATEST_REVISION
    finally:
        test_engine.dispose()


def test_network_credential_migration_preserves_legacy_environment_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "legacy-network.db"
    database_url = URL.create(drivername="sqlite", database=str(database_path))
    monkeypatch.setenv(
        "DATABASE_URL", database_url.render_as_string(hide_password=False)
    )
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "20261003_0009")
    test_engine = create_engine(database_url)
    try:
        with test_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO devices (id,name,device_type,platform,os_version,status,created_at,updated_at) "
                    "VALUES (1,'Legacy','virtual','android','12','offline',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO runtimes (id,device_id,name,runtime_type,docker_container_name,adb_serial,status,created_at,updated_at) "
                    "VALUES (1,1,'Legacy Runtime','redroid','legacy-runtime','localhost:5998','stopped',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
                )
            )
            for table, revision_column in (
                ("runtime_network_configs", "desired_revision"),
                ("runtime_network_config_revisions", "revision"),
            ):
                connection.execute(
                    text(
                        f"INSERT INTO {table} (runtime_id,mode,proxy_host,proxy_port,"
                        "proxy_username_secret_ref,proxy_password_secret_ref,bridge_host_port,"
                        f"bridge_device_port,{revision_column},created_at"
                        + (",updated_at" if table == "runtime_network_configs" else "")
                        + ") VALUES (1,'http_proxy','proxy.example',3128,"
                        "'env:TIKTOK_PROXY_LEGACY_USER','env:TIKTOK_PROXY_LEGACY_PASSWORD',"
                        "18880,18888,1,CURRENT_TIMESTAMP"
                        + (",CURRENT_TIMESTAMP" if table == "runtime_network_configs" else "")
                        + ")"
                    )
                )

        command.upgrade(config, "head")

        with test_engine.connect() as connection:
            current = connection.execute(
                text(
                    "SELECT credential_source,proxy_username_secret_ref,proxy_password_secret_ref "
                    "FROM runtime_network_configs WHERE runtime_id=1"
                )
            ).one()
            history = connection.execute(
                text(
                    "SELECT credential_source FROM runtime_network_config_revisions "
                    "WHERE runtime_id=1 AND revision=1"
                )
            ).scalar_one()
            encrypted_count = connection.execute(
                text("SELECT count(*) FROM runtime_network_credentials")
            ).scalar_one()
        assert current == (
            "environment_reference",
            "env:TIKTOK_PROXY_LEGACY_USER",
            "env:TIKTOK_PROXY_LEGACY_PASSWORD",
        )
        assert history == "environment_reference"
        assert encrypted_count == 0
    finally:
        test_engine.dispose()


def test_upgrade_preserves_existing_accounts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "existing.db"
    database_url = URL.create(drivername="sqlite", database=str(database_path))
    monkeypatch.setenv("DATABASE_URL", database_url.render_as_string(hide_password=False))
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, INITIAL_REVISION)
    test_engine = create_engine(database_url)
    try:
        with test_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        name, username, platform, status, notes,
                        created_at, updated_at
                    ) VALUES (
                        'Existing Account', 'existing', 'tiktok', 'active', NULL,
                        '2026-09-18 00:00:00', '2026-09-18 00:00:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with test_engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT name, display_name, username, registration_state, health_status, runtime_id FROM accounts "
                    "WHERE username = 'existing'"
                )
            ).one()
            migration_context = MigrationContext.configure(connection)
            current_revision = migration_context.get_current_revision()

        assert row.name == "Existing Account"
        assert row.display_name == "Existing Account"
        assert row.username == "existing"
        assert row.registration_state == "unknown"
        assert row.health_status == "unknown"
        assert row.runtime_id is None
        assert current_revision == LATEST_REVISION
    finally:
        test_engine.dispose()


def test_job_migration_preserves_existing_device_runtime_and_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "pre-job.db"
    database_url = URL.create(drivername="sqlite", database=str(database_path))
    monkeypatch.setenv("DATABASE_URL", database_url.render_as_string(hide_password=False))
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, PRE_JOB_REVISION)
    test_engine = create_engine(database_url)
    try:
        with test_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO devices (
                        id, name, device_type, platform, os_version, status,
                        notes, created_at, updated_at
                    ) VALUES (
                        1, 'Existing Device', 'physical', 'android', '15',
                        'online', NULL, '2026-09-18 00:00:00',
                        '2026-09-18 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO runtimes (
                        id, device_id, name, runtime_type, status, last_seen_at,
                        created_at, updated_at
                    ) VALUES (
                        1, 1, 'Existing Runtime', 'app', 'running', NULL,
                        '2026-09-18 00:00:00', '2026-09-18 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        id, name, username, platform, status, notes, runtime_id,
                        created_at, updated_at
                    ) VALUES (
                        1, 'Existing Account', 'existing-job-target', 'tiktok',
                        'active', NULL, 1, '2026-09-18 00:00:00',
                        '2026-09-18 00:00:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with test_engine.connect() as connection:
            device_name = connection.scalar(text("SELECT name FROM devices WHERE id = 1"))
            runtime_row = connection.execute(
                text("SELECT name, device_id FROM runtimes WHERE id = 1")
            ).one()
            account_row = connection.execute(
                text("SELECT username, runtime_id FROM accounts WHERE id = 1")
            ).one()
            migration_context = MigrationContext.configure(connection)
            current_revision = migration_context.get_current_revision()

        assert device_name == "Existing Device"
        assert runtime_row == ("Existing Runtime", 1)
        assert account_row == ("existing-job-target", 1)
        assert current_revision == LATEST_REVISION
    finally:
        test_engine.dispose()


def test_job_log_migration_preserves_existing_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "pre-job-log.db"
    database_url = URL.create(drivername="sqlite", database=str(database_path))
    monkeypatch.setenv("DATABASE_URL", database_url.render_as_string(hide_password=False))
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, PRE_JOB_LOG_REVISION)
    test_engine = create_engine(database_url)
    try:
        with test_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO jobs (
                        id, job_type, status, account_id, runtime_id, payload,
                        result, error_message, attempt_count, max_attempts,
                        scheduled_at, started_at, completed_at,
                        created_at, updated_at
                    ) VALUES (
                        1, 'existing_job', 'failed', NULL, NULL, '{"key": 1}',
                        NULL, 'Existing failure', 1, 3, NULL,
                        '2026-09-18 00:00:00', '2026-09-18 00:01:00',
                        '2026-09-18 00:00:00', '2026-09-18 00:01:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with test_engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT job_type, status, attempt_count, error_message "
                    "FROM jobs WHERE id = 1"
                )
            ).one()
            migration_context = MigrationContext.configure(connection)
            current_revision = migration_context.get_current_revision()

        assert row == ("existing_job", "failed", 1, "Existing failure")
        assert current_revision == LATEST_REVISION
    finally:
        test_engine.dispose()


def test_redroid_config_migration_preserves_existing_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "pre-redroid-config.db"
    database_url = URL.create(drivername="sqlite", database=str(database_path))
    monkeypatch.setenv("DATABASE_URL", database_url.render_as_string(hide_password=False))
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))

    command.upgrade(config, PRE_REDROID_CONFIG_REVISION)
    test_engine = create_engine(database_url)
    try:
        with test_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO devices (
                        id, name, device_type, platform, os_version, status,
                        notes, created_at, updated_at
                    ) VALUES (
                        1, 'Existing Host', 'virtual', 'android', '14',
                        'online', NULL, '2026-09-18 00:00:00',
                        '2026-09-18 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO runtimes (
                        id, device_id, name, runtime_type, status, last_seen_at,
                        created_at, updated_at
                    ) VALUES (
                        1, 1, 'Existing Runtime', 'emulator', 'running', NULL,
                        '2026-09-18 00:00:00', '2026-09-18 00:00:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with test_engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT name, runtime_type, docker_container_name, adb_serial "
                    "FROM runtimes WHERE id = 1"
                )
            ).one()
            migration_context = MigrationContext.configure(connection)
            current_revision = migration_context.get_current_revision()

        assert row == ("Existing Runtime", "emulator", None, None)
        assert current_revision == LATEST_REVISION
    finally:
        test_engine.dispose()
