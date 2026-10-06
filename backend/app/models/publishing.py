"""Durable domain history for generic publishing preparation."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.timestamps import utc_now


class PublishingSession(Base):
    __tablename__ = "publishing_sessions"
    __table_args__ = (
        UniqueConstraint("workflow_id", name="uq_publishing_sessions_workflow"),
        CheckConstraint(
            "status IN ('preparing','waiting_approval','prepared','rejected','failed','cancelled')",
            name="ck_publishing_sessions_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="RESTRICT"), nullable=False, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), index=True)
    account_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    runtime_id: Mapped[int | None] = mapped_column(ForeignKey("runtimes.id", ondelete="SET NULL"), index=True)
    runtime_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    content_asset_version_id: Mapped[int] = mapped_column(ForeignKey("content_asset_versions.id", ondelete="RESTRICT"), nullable=False)
    managed_app_id: Mapped[int] = mapped_column(ForeignKey("managed_apps.id", ondelete="RESTRICT"), nullable=False)
    managed_app_version_id: Mapped[int] = mapped_column(ForeignKey("managed_app_versions.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="preparing", server_default="preparing", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))
