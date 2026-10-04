"""Job database model."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.timestamps import utc_now

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.job_artifact import JobArtifact
    from app.models.job_log import JobLog
    from app.models.runtime import Runtime


class JobStatus(str, Enum):
    """Lifecycle states supported by a job."""

    PENDING = "pending"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


JOB_STATUS_VALUES = tuple(status.value for status in JobStatus)


class Job(Base):
    """A durable unit of work optionally targeting an account or runtime."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', "
            "'retrying', 'cancelling', 'cancelled')",
            name="ck_jobs_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_jobs_attempt_count"),
        CheckConstraint("max_attempts > 0", name="ck_jobs_max_attempts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default=JobStatus.PENDING.value,
        server_default=JobStatus.PENDING.value,
        nullable=False,
    )
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    runtime_id: Mapped[int | None] = mapped_column(
        ForeignKey("runtimes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payload: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    result: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    attempt_count: Mapped[int] = mapped_column(
        default=0, server_default="0", nullable=False
    )
    max_attempts: Mapped[int] = mapped_column(
        default=3, server_default="3", nullable=False
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    claim_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    account: Mapped["Account | None"] = relationship(back_populates="jobs")
    runtime: Mapped["Runtime | None"] = relationship(back_populates="jobs")
    logs: Mapped[list["JobLog"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["JobArtifact"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
