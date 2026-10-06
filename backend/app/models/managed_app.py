"""Managed Android package definitions, immutable versions, and safe history."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.content import ContentAsset, ContentAssetVersion
from app.models.job import Job
from app.models.timestamps import utc_now

if TYPE_CHECKING:
    from app.models.runtime import Runtime


class ManagedApp(Base):
    __tablename__ = "managed_apps"
    __table_args__ = (
        CheckConstraint("length(key) BETWEEN 1 AND 64", name="ck_managed_apps_key_length"),
        CheckConstraint("length(display_name) BETWEEN 1 AND 255", name="ck_managed_apps_name_length"),
        CheckConstraint("length(android_package_name) BETWEEN 3 AND 255", name="ck_managed_apps_package_length"),
        CheckConstraint("status IN ('active','disabled','archived')", name="ck_managed_apps_status"),
        CheckConstraint("install_policy IN ('required','optional','disabled')", name="ck_managed_apps_policy"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    android_package_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active", nullable=False, index=True)
    install_policy: Mapped[str] = mapped_column(String(20), default="optional", server_default="optional", nullable=False)
    # Application-enforced because this pointer creates a DDL cycle and readiness
    # is a state predicate rather than a relational FK predicate.
    current_version_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "managed_app_versions.id",
            ondelete="RESTRICT",
            use_alter=True,
            name="fk_managed_apps_current_version",
        )
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    versions: Mapped[list["ManagedAppVersion"]] = relationship(
        back_populates="managed_app", cascade="all, delete-orphan",
        foreign_keys="ManagedAppVersion.managed_app_id",
    )
    events: Mapped[list["ManagedAppEvent"]] = relationship(
        back_populates="managed_app", cascade="all, delete-orphan"
    )


class ManagedAppVersion(Base):
    __tablename__ = "managed_app_versions"
    __table_args__ = (
        UniqueConstraint("managed_app_id", "sha256", name="uq_managed_app_version_digest"),
        UniqueConstraint("content_asset_version_id", name="uq_managed_app_content_version"),
        UniqueConstraint("inspection_job_id", name="uq_managed_app_inspection_job"),
        CheckConstraint(
            "status IN ('uploaded','inspecting','ready','invalid','retired')",
            name="ck_managed_app_versions_status",
        ),
        CheckConstraint(
            "inspection_level IN ('basic','verified')",
            name="ck_managed_app_versions_inspection_level",
        ),
        CheckConstraint(
            "length(sha256) = 64 AND sha256 = lower(sha256) AND sha256 NOT GLOB '*[^0-9a-f]*'",
            name="ck_managed_app_versions_sha256",
        ),
        CheckConstraint("version_code IS NULL OR version_code >= 0", name="ck_managed_app_versions_code"),
        CheckConstraint("signer_metadata IS NULL OR length(signer_metadata) <= 4096", name="ck_managed_app_versions_signers"),
        CheckConstraint("error_message IS NULL OR length(error_message) <= 500", name="ck_managed_app_versions_error"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    managed_app_id: Mapped[int] = mapped_column(ForeignKey("managed_apps.id", ondelete="CASCADE"), nullable=False, index=True)
    content_asset_id: Mapped[int] = mapped_column(ForeignKey("content_assets.id", ondelete="RESTRICT"), nullable=False)
    content_asset_version_id: Mapped[int] = mapped_column(ForeignKey("content_asset_versions.id", ondelete="RESTRICT"), nullable=False)
    version_name: Mapped[str | None] = mapped_column(String(255))
    version_code: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    discovered_package_name: Mapped[str | None] = mapped_column(String(255))
    min_sdk: Mapped[int | None] = mapped_column(Integer)
    target_sdk: Mapped[int | None] = mapped_column(Integer)
    signer_fingerprint: Mapped[str | None] = mapped_column(String(64))
    signer_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    inspection_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="basic", server_default="basic"
    )
    basic_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    inspection_job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), index=True)
    inspector_name: Mapped[str] = mapped_column(String(100), nullable=False, default="aapt2+apksigner", server_default="aapt2+apksigner")
    inspector_version: Mapped[str | None] = mapped_column(String(255))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    managed_app: Mapped[ManagedApp] = relationship(back_populates="versions", foreign_keys=[managed_app_id])
    content_asset: Mapped[ContentAsset] = relationship(foreign_keys=[content_asset_id])
    content_asset_version: Mapped[ContentAssetVersion] = relationship(foreign_keys=[content_asset_version_id])
    inspection_job: Mapped[Job | None] = relationship(foreign_keys=[inspection_job_id])
    events: Mapped[list["ManagedAppEvent"]] = relationship(back_populates="managed_app_version")


class ManagedAppEvent(Base):
    __tablename__ = "managed_app_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('app_created','version_uploaded','inspection_queued','inspection_started',"
            "'version_ready','version_invalid','version_activated','version_retired','app_updated',"
            "'version_basic_approved',"
            "'installation_created','install_requested','install_started','install_succeeded',"
            "'install_failed','verify_requested','verified','marked_outdated','runtime_removed')",
            name="ck_managed_app_events_type",
        ),
        CheckConstraint("metadata_json IS NULL OR length(metadata_json) <= 8192", name="ck_managed_app_events_metadata"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    managed_app_id: Mapped[int] = mapped_column(ForeignKey("managed_apps.id", ondelete="CASCADE"), nullable=False, index=True)
    managed_app_version_id: Mapped[int | None] = mapped_column(ForeignKey("managed_app_versions.id", ondelete="SET NULL"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    managed_app: Mapped[ManagedApp] = relationship(back_populates="events")
    managed_app_version: Mapped[ManagedAppVersion | None] = relationship(back_populates="events")


class RuntimeAppInstallation(Base):
    """Desired and observed state for one managed app on one live Runtime."""

    __tablename__ = "runtime_app_installations"
    __table_args__ = (
        UniqueConstraint(
            "runtime_id", "managed_app_id",
            name="uq_runtime_app_installation_live_app",
        ),
        UniqueConstraint(
            "latest_job_id", name="uq_runtime_app_installation_latest_job"
        ),
        CheckConstraint(
            "status IN ('pending','installing','installed','failed','outdated','removed')",
            name="ck_runtime_app_installations_status",
        ),
        CheckConstraint(
            "runtime_id_snapshot > 0", name="ck_runtime_app_installations_snapshot"
        ),
        CheckConstraint(
            "observed_version_code IS NULL OR observed_version_code >= 0",
            name="ck_runtime_app_installations_version_code",
        ),
        CheckConstraint(
            "error_message IS NULL OR length(error_message) <= 500",
            name="ck_runtime_app_installations_error",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    runtime_id: Mapped[int | None] = mapped_column(
        ForeignKey("runtimes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    runtime_id_snapshot: Mapped[int] = mapped_column(nullable=False)
    managed_app_id: Mapped[int] = mapped_column(
        ForeignKey("managed_apps.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    desired_managed_app_version_id: Mapped[int] = mapped_column(
        ForeignKey("managed_app_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    observed_managed_app_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("managed_app_versions.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending", index=True
    )
    observed_package_name: Mapped[str | None] = mapped_column(String(255))
    observed_version_name: Mapped[str | None] = mapped_column(String(255))
    observed_version_code: Mapped[int | None] = mapped_column(Integer)
    observed_signer_fingerprint: Mapped[str | None] = mapped_column(String(64))
    latest_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), unique=True, index=True
    )
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    runtime: Mapped["Runtime | None"] = relationship(
        back_populates="app_installations", foreign_keys=[runtime_id]
    )
    managed_app: Mapped[ManagedApp] = relationship(foreign_keys=[managed_app_id])
    desired_version: Mapped[ManagedAppVersion] = relationship(
        foreign_keys=[desired_managed_app_version_id]
    )
    observed_version: Mapped[ManagedAppVersion | None] = relationship(
        foreign_keys=[observed_managed_app_version_id]
    )
    latest_job: Mapped[Job | None] = relationship(foreign_keys=[latest_job_id])
    runs: Mapped[list["RuntimeAppInstallationRun"]] = relationship(
        back_populates="installation", cascade="all, delete-orphan"
    )


class RuntimeAppInstallationRun(Base):
    """Immutable Job history for installation and verification attempts."""

    __tablename__ = "runtime_app_installation_runs"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_runtime_app_installation_run_job"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    runtime_app_installation_id: Mapped[int] = mapped_column(
        ForeignKey("runtime_app_installations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    desired_managed_app_version_id: Mapped[int] = mapped_column(
        ForeignKey("managed_app_versions.id", ondelete="RESTRICT"), nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    installation: Mapped[RuntimeAppInstallation] = relationship(back_populates="runs")
    desired_version: Mapped[ManagedAppVersion] = relationship()
    job: Mapped[Job] = relationship()
