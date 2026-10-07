"""Account database model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.timestamps import utc_now

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.runtime import Runtime


ACCOUNT_STATUSES = (
    "pending",
    "active",
    "inactive",
    "restricted",
    "suspended",
    "disabled",
    "archived",
)
ACCOUNT_REGISTRATION_STATES = ("unknown", "pending", "registered", "failed")
ACCOUNT_HEALTH_STATUSES = ("unknown", "healthy", "warning", "unhealthy")
ACCOUNT_SECRET_TYPES = ("account_password", "email_password", "recovery_credential")


class Account(Base):
    """A social platform account managed by the application."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    # ``name`` and ``platform`` remain for compatibility with the original API.
    # New callers should use display_name; writes keep both names synchronized.
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    registration_state: Mapped[str] = mapped_column(
        String(30), default="unknown", nullable=False
    )
    health_status: Mapped[str] = mapped_column(
        String(30), default="unknown", nullable=False
    )
    status_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    niche: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_id: Mapped[int | None] = mapped_column(
        ForeignKey("runtimes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    follower_count: Mapped[int | None] = mapped_column(Integer)
    following_count: Mapped[int | None] = mapped_column(Integer)
    likes_count: Mapped[int | None] = mapped_column(Integer)
    video_count: Mapped[int | None] = mapped_column(Integer)
    metrics_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    runtime: Mapped["Runtime | None"] = relationship(back_populates="accounts")
    jobs: Mapped[list["Job"]] = relationship(back_populates="account")
    tags: Mapped[list["AccountTag"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    secrets: Mapped[list["AccountSecret"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class AccountTag(Base):
    """Normalized lightweight organization tag for an Account."""

    __tablename__ = "account_tags"
    __table_args__ = (
        UniqueConstraint("account_id", "tag", name="uq_account_tags_account_tag"),
        CheckConstraint("length(tag) BETWEEN 1 AND 50", name="ck_account_tags_length"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag: Mapped[str] = mapped_column(String(50), nullable=False)
    account: Mapped["Account"] = relationship(back_populates="tags")


class AccountSecret(Base):
    """Encrypted credential material; plaintext never enters Account rows."""

    __tablename__ = "account_secrets"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "secret_type", name="uq_account_secrets_account_type"
        ),
        CheckConstraint(
            "secret_type IN ('account_password', 'email_password', "
            "'recovery_credential')",
            name="ck_account_secrets_type",
        ),
        CheckConstraint(
            "encryption_version = 'fernet-v1'",
            name="ck_account_secrets_encryption_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    secret_type: Mapped[str] = mapped_column(String(40), nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_version: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    account: Mapped["Account"] = relationship(back_populates="secrets")

    def __repr__(self) -> str:
        return (
            f"AccountSecret(id={self.id!r}, account_id={self.account_id!r}, "
            f"secret_type={self.secret_type!r}, encrypted_value=[REDACTED])"
        )
