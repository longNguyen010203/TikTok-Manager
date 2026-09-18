"""Tests for database setup and models."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.database import init_db
from app.models import Account, Device, Job, JobLog, JobStatus, Runtime
from app.services.job_logs import append_job_log


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
    assert {"accounts", "devices", "job_logs", "jobs", "runtimes"}.issubset(
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

    job_columns = {
        column["name"]: column for column in inspector.get_columns("jobs")
    }
    assert set(job_columns) == {
        "id",
        "job_type",
        "status",
        "account_id",
        "runtime_id",
        "payload",
        "result",
        "error_message",
        "attempt_count",
        "max_attempts",
        "scheduled_at",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    }
    assert job_columns["id"]["primary_key"] == 1
    for field in (
        "account_id",
        "runtime_id",
        "payload",
        "result",
        "error_message",
        "scheduled_at",
        "started_at",
        "completed_at",
    ):
        assert job_columns[field]["nullable"] is True
    for field in (
        "job_type",
        "status",
        "attempt_count",
        "max_attempts",
        "created_at",
        "updated_at",
    ):
        assert job_columns[field]["nullable"] is False

    foreign_keys = {
        tuple(foreign_key["constrained_columns"]): foreign_key
        for foreign_key in inspector.get_foreign_keys("jobs")
    }
    assert foreign_keys[("account_id",)]["referred_table"] == "accounts"
    assert foreign_keys[("account_id",)]["options"]["ondelete"] == "SET NULL"
    assert foreign_keys[("runtime_id",)]["referred_table"] == "runtimes"
    assert foreign_keys[("runtime_id",)]["options"]["ondelete"] == "SET NULL"

    job_log_columns = {
        column["name"]: column for column in inspector.get_columns("job_logs")
    }
    assert set(job_log_columns) == {
        "id",
        "job_id",
        "level",
        "message",
        "metadata",
        "created_at",
    }
    assert job_log_columns["id"]["primary_key"] == 1
    assert job_log_columns["metadata"]["nullable"] is True
    for field in ("job_id", "level", "message", "created_at"):
        assert job_log_columns[field]["nullable"] is False
    job_log_foreign_key = inspector.get_foreign_keys("job_logs")[0]
    assert job_log_foreign_key["constrained_columns"] == ["job_id"]
    assert job_log_foreign_key["referred_table"] == "jobs"
    assert job_log_foreign_key["options"]["ondelete"] == "CASCADE"


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


def test_job_can_be_persisted_with_targets_and_json(database_engine: Engine) -> None:
    init_db(database_engine)
    device = Device(
        name="Job Device",
        device_type="physical",
        platform="android",
        os_version="15",
        status="online",
    )
    runtime = Runtime(name="Job Runtime", runtime_type="app", status="running")
    device.runtimes.append(runtime)
    account = Account(
        name="Job Account",
        username="job-account",
        platform="tiktok",
        status="active",
        runtime=runtime,
    )
    job = Job(
        job_type="publish_video",
        account=account,
        runtime=runtime,
        payload={"video_id": 42},
        result={"published": True},
    )

    with Session(database_engine) as session:
        session.add_all([device, account, job])
        session.commit()
        session.refresh(job)

        assert job.status == JobStatus.PENDING.value
        assert job.attempt_count == 0
        assert job.max_attempts == 3
        assert job.account_id == account.id
        assert job.runtime_id == runtime.id
        assert job.payload == {"video_id": 42}
        assert job.result == {"published": True}
        assert job in account.jobs
        assert job in runtime.jobs
        assert job.created_at is not None
        assert job.updated_at is not None

        session.delete(account)
        session.delete(runtime)
        session.commit()
        session.refresh(job)

        assert job.account_id is None
        assert job.runtime_id is None


def test_job_status_is_constrained(database_engine: Engine) -> None:
    init_db(database_engine)
    assert {status.value for status in JobStatus} == {
        "pending",
        "running",
        "succeeded",
        "failed",
        "retrying",
        "cancelled",
    }

    with Session(database_engine) as session:
        session.add(Job(job_type="invalid", status="unknown"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_append_job_log_and_job_delete_cascades_logs(
    database_engine: Engine,
) -> None:
    init_db(database_engine)
    job = Job(job_type="logged_job")

    with Session(database_engine) as session:
        session.add(job)
        session.commit()
        session.refresh(job)

        log = append_job_log(
            session,
            job,
            level="info",
            message="Manual test log",
            metadata={"source": "test"},
        )
        session.commit()
        session.refresh(log)
        job_id = job.id
        log_id = log.id

        assert log.job_id == job_id
        assert log.log_metadata == {"source": "test"}
        assert log.created_at is not None
        assert log in job.logs

        session.delete(job)
        session.commit()

        assert session.get(Job, job_id) is None
        assert session.get(JobLog, log_id) is None
