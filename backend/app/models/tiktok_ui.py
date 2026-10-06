"""Immutable metadata for repository-owned TikTok UI profiles."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.timestamps import utc_now


class TikTokUiProfile(Base):
    __tablename__ = "tiktok_ui_profiles"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_tiktok_ui_profile_key_version"),
        CheckConstraint("version > 0", name="ck_tiktok_ui_profile_version"),
        CheckConstraint("status IN ('testing','active','retired')", name="ck_tiktok_ui_profile_status"),
        CheckConstraint(
            "length(profile_fingerprint) = 64 AND profile_fingerprint = lower(profile_fingerprint) AND profile_fingerprint NOT GLOB '*[^0-9a-f]*'",
            name="ck_tiktok_ui_profile_fingerprint",
        ),
        CheckConstraint(
            "min_version_code IS NULL OR max_version_code IS NULL OR min_version_code <= max_version_code",
            name="ck_tiktok_ui_profile_version_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    package_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    min_version_code: Mapped[int | None] = mapped_column(Integer)
    max_version_code: Mapped[int | None] = mapped_column(Integer)
    min_version_name: Mapped[str | None] = mapped_column(String(100))
    max_version_name: Mapped[str | None] = mapped_column(String(100))
    locale_assumption: Mapped[str | None] = mapped_column(String(35))
    profile_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    resource_key: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
