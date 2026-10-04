"""Durable metadata for files managed by device automation."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.timestamps import utc_now

if TYPE_CHECKING:
    from app.models.job import Job


class JobArtifact(Base):
    """Metadata for an artifact stored beneath the managed artifact root."""

    __tablename__ = "job_artifacts"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_job_artifacts_size_nonnegative"),
        CheckConstraint(
            "cleanup_status IN ('active', 'deleted', 'failed')",
            name="ck_job_artifacts_cleanup_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    cleanup_status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", nullable=False
    )
    job: Mapped["Job | None"] = relationship(back_populates="artifacts")
