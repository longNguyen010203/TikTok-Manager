"""Durable manifest for managed Redroid provisioning attempts."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.timestamps import utc_now


PROVISIONING_STATES = (
    "requested",
    "preflighting",
    "reserved",
    "data_created",
    "network_created",
    "container_created",
    "inspected",
    "completed",
    "rolling_back",
    "rolled_back",
    "failed",
    "rollback_failed",
    "inconsistent",
)


class RedroidProvisioning(Base):
    """Allocation, ownership, and recovery state for one provisioning request."""

    __tablename__ = "redroid_provisionings"
    __table_args__ = (
        CheckConstraint(
            "state IN (" + ", ".join(repr(value) for value in PROVISIONING_STATES) + ")",
            name="ck_redroid_provisionings_state",
        ),
        CheckConstraint(
            "device_number IS NULL OR device_number > 0",
            name="ck_redroid_provisionings_device_number_positive",
        ),
        CheckConstraint(
            "adb_host_port IS NULL OR (adb_host_port >= 1024 AND adb_host_port <= 65535)",
            name="ck_redroid_provisionings_adb_host_port_range",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    ownership_token: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    installation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    device_number: Mapped[int | None] = mapped_column(Integer, unique=True)
    container_name: Mapped[str | None] = mapped_column(String(255), unique=True)
    docker_container_id: Mapped[str | None] = mapped_column(String(255))
    adb_host_port: Mapped[int | None] = mapped_column(Integer, unique=True)
    adb_serial: Mapped[str | None] = mapped_column(String(255), unique=True)
    data_path: Mapped[str | None] = mapped_column(String(1024), unique=True)
    network_name: Mapped[str | None] = mapped_column(String(255), unique=True)
    docker_network_id: Mapped[str | None] = mapped_column(String(255))
    image_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), unique=True
    )
    runtime_id: Mapped[int | None] = mapped_column(
        ForeignKey("runtimes.id", ondelete="SET NULL"), unique=True
    )
    data_directory_created: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    network_created: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    container_created: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
