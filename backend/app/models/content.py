"""Reusable content-library metadata and durable history."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.timestamps import utc_now

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.job_artifact import JobArtifact
    from app.models.runtime import Runtime


ASSET_TYPES = ("video", "image", "audio", "other")
ASSET_SOURCES = ("upload", "promoted_artifact", "generated", "imported")
ASSET_STATUSES = ("processing", "ready", "invalid", "archived", "deleted")
PROCESSING_STATUSES = ("processing", "ready", "invalid")
BLOB_STATUSES = ("active", "orphaned", "missing", "deleted")
VARIANT_STATUSES = ("processing", "ready", "invalid", "deleted")
DELIVERY_STATUSES = ("pending", "delivering", "succeeded", "failed", "cancelled")
CONTENT_EVENT_TYPES = (
    "uploaded",
    "processing_queued",
    "processing_started",
    "ready",
    "invalid",
    "metadata_updated",
    "archived",
    "restored",
    "deleted",
    "version_added",
    "delivery_requested",
    "delivery_started",
    "delivered",
    "delivery_failed",
    "delivery_cancelled",
    "delivery_repeated",
)


class ContentBlob(Base):
    """One immutable physical file, deduplicated by SHA-256."""

    __tablename__ = "content_blobs"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_content_blobs_size_positive"),
        CheckConstraint(
            "length(sha256) = 64 AND sha256 = lower(sha256) "
            "AND sha256 NOT GLOB '*[^0-9a-f]*'",
            name="ck_content_blobs_sha256",
        ),
        CheckConstraint(
            "length(storage_key) = 32 "
            "AND storage_key NOT GLOB '*[^0-9a-f]*' "
            "AND instr(storage_key, '/') = 0 AND instr(storage_key, '\\') = 0",
            name="ck_content_blobs_storage_key",
        ),
        CheckConstraint(
            "length(detected_mime_type) BETWEEN 1 AND 100",
            name="ck_content_blobs_mime_length",
        ),
        CheckConstraint(
            "status IN ('active', 'orphaned', 'missing', 'deleted')",
            name="ck_content_blobs_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    storage_key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    versions: Mapped[list["ContentAssetVersion"]] = relationship(back_populates="blob")
    variants: Mapped[list["ContentVariant"]] = relationship(back_populates="blob")


class ContentAsset(Base):
    """A mutable logical library entry whose file versions are immutable."""

    __tablename__ = "content_assets"
    __table_args__ = (
        CheckConstraint(
            "asset_type IN ('video', 'image', 'audio', 'other')",
            name="ck_content_assets_type",
        ),
        CheckConstraint(
            "source IN ('upload', 'promoted_artifact', 'generated', 'imported')",
            name="ck_content_assets_source",
        ),
        CheckConstraint(
            "status IN ('processing', 'ready', 'invalid', 'archived', 'deleted')",
            name="ck_content_assets_status",
        ),
        CheckConstraint(
            "length(display_name) BETWEEN 1 AND 255",
            name="ck_content_assets_display_name",
        ),
        CheckConstraint(
            "notes IS NULL OR length(notes) <= 4000",
            name="ck_content_assets_notes_length",
        ),
        CheckConstraint(
            "current_version_id IS NULL OR current_version_id > 0",
            name="ck_content_assets_current_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # Application-enforced pointer avoids a cyclic DDL dependency with versions.
    current_version_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    versions: Mapped[list["ContentAssetVersion"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan",
        order_by="ContentAssetVersion.version_number",
    )
    tags: Mapped[list["ContentAssetTag"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    events: Mapped[list["ContentEvent"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    deliveries: Mapped[list["ContentDelivery"]] = relationship(back_populates="asset")


class ContentAssetVersion(Base):
    """An immutable byte version with Phase 3 media metadata placeholders."""

    __tablename__ = "content_asset_versions"
    __table_args__ = (
        UniqueConstraint(
            "content_asset_id", "version_number", name="uq_content_asset_version"
        ),
        CheckConstraint("version_number > 0", name="ck_content_versions_number"),
        CheckConstraint(
            "processing_status IN ('processing', 'ready', 'invalid')",
            name="ck_content_versions_processing_status",
        ),
        CheckConstraint(
            "length(original_filename) BETWEEN 1 AND 255",
            name="ck_content_versions_filename",
        ),
        CheckConstraint(
            "length(detected_mime_type) BETWEEN 1 AND 100",
            name="ck_content_versions_mime",
        ),
        CheckConstraint(
            "length(canonical_extension) BETWEEN 2 AND 10",
            name="ck_content_versions_extension",
        ),
        CheckConstraint(
            "metadata_json IS NULL OR length(metadata_json) <= 16384",
            name="ck_content_versions_metadata_size",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    content_asset_id: Mapped[int] = mapped_column(
        ForeignKey("content_assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    blob_id: Mapped[int] = mapped_column(
        ForeignKey("content_blobs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    detected_mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    canonical_extension: Mapped[str] = mapped_column(String(10), nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(20), default="processing", server_default="processing", nullable=False
    )
    source_job_artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_artifacts.id", ondelete="SET NULL"), index=True
    )
    inspection_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), unique=True, index=True
    )
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    codec: Mapped[str | None] = mapped_column(String(100))
    frame_rate_numerator: Mapped[int | None] = mapped_column(Integer)
    frame_rate_denominator: Mapped[int | None] = mapped_column(Integer)
    container: Mapped[str | None] = mapped_column(String(100))
    audio_present: Mapped[bool | None] = mapped_column(Boolean)
    bitrate: Mapped[int | None] = mapped_column(Integer)
    sample_rate: Mapped[int | None] = mapped_column(Integer)
    channels: Mapped[int | None] = mapped_column(Integer)
    orientation: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    asset: Mapped["ContentAsset"] = relationship(back_populates="versions")
    blob: Mapped["ContentBlob"] = relationship(back_populates="versions")
    source_job_artifact: Mapped["JobArtifact | None"] = relationship()
    variants: Mapped[list["ContentVariant"]] = relationship(
        back_populates="source_version", cascade="all, delete-orphan"
    )


class ContentVariant(Base):
    """Schema foundation for future generated derivatives."""

    __tablename__ = "content_variants"
    __table_args__ = (
        UniqueConstraint(
            "source_version_id", "variant_kind", "profile_fingerprint",
            name="uq_content_variant_profile",
        ),
        CheckConstraint(
            "status IN ('processing', 'ready', 'invalid', 'deleted')",
            name="ck_content_variants_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_version_id: Mapped[int] = mapped_column(
        ForeignKey("content_asset_versions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    blob_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_blobs.id", ondelete="RESTRICT"), index=True
    )
    variant_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    profile_name: Mapped[str] = mapped_column(String(100), nullable=False)
    profile_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    detected_mime_type: Mapped[str | None] = mapped_column(String(100))
    canonical_extension: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source_version: Mapped["ContentAssetVersion"] = relationship(back_populates="variants")
    blob: Mapped["ContentBlob | None"] = relationship(back_populates="variants")


class ContentAssetTag(Base):
    """One normalized exact-match tag for an asset."""

    __tablename__ = "content_asset_tags"
    __table_args__ = (
        CheckConstraint(
            "length(tag) BETWEEN 1 AND 50 AND tag = lower(tag)",
            name="ck_content_asset_tags_normalized",
        ),
    )

    content_asset_id: Mapped[int] = mapped_column(
        ForeignKey("content_assets.id", ondelete="CASCADE"), primary_key=True
    )
    tag: Mapped[str] = mapped_column(String(50), primary_key=True)

    asset: Mapped["ContentAsset"] = relationship(back_populates="tags")


class ContentDelivery(Base):
    """Durable, exact-version delivery intent and outcome."""

    __tablename__ = "content_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'delivering', 'succeeded', 'failed', 'cancelled')",
            name="ck_content_deliveries_status",
        ),
        CheckConstraint(
            "runtime_id_snapshot > 0", name="ck_content_deliveries_runtime_snapshot"
        ),
        UniqueConstraint(
            "content_asset_version_id",
            "runtime_id_snapshot",
            "idempotency_key",
            name="uq_content_delivery_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    content_asset_id: Mapped[int] = mapped_column(
        ForeignKey("content_assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    content_asset_version_id: Mapped[int] = mapped_column(
        ForeignKey("content_asset_versions.id", ondelete="RESTRICT"), nullable=False
    )
    content_variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_variants.id", ondelete="SET NULL")
    )
    runtime_id: Mapped[int | None] = mapped_column(
        ForeignKey("runtimes.id", ondelete="SET NULL"), index=True
    )
    runtime_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), unique=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    import_media: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    remote_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    remote_path: Mapped[str] = mapped_column(String(512), nullable=False)
    media_uri: Mapped[str | None] = mapped_column(String(512))
    delivered_sha256: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    asset: Mapped["ContentAsset"] = relationship(back_populates="deliveries")
    version: Mapped["ContentAssetVersion"] = relationship()
    variant: Mapped["ContentVariant | None"] = relationship()
    runtime: Mapped["Runtime | None"] = relationship()
    job: Mapped["Job | None"] = relationship()


class ContentEvent(Base):
    """Append-only safe business event for content history."""

    __tablename__ = "content_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('uploaded', 'processing_queued', 'processing_started', "
            "'ready', 'invalid', 'metadata_updated', 'archived', "
            "'restored', 'deleted', 'version_added', 'delivery_requested', "
            "'delivery_started', 'delivered', 'delivery_failed', "
            "'delivery_cancelled', 'delivery_repeated')",
            name="ck_content_events_type",
        ),
        CheckConstraint(
            "metadata_json IS NULL OR length(metadata_json) <= 8192",
            name="ck_content_events_metadata_size",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    content_asset_id: Mapped[int] = mapped_column(
        ForeignKey("content_assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_asset_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_asset_versions.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    asset: Mapped["ContentAsset"] = relationship(back_populates="events")
    version: Mapped["ContentAssetVersion | None"] = relationship()
