"""Durable desired and observed per-Runtime network configuration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.timestamps import utc_now

if TYPE_CHECKING:
    from app.models.runtime import Runtime


NETWORK_MODES = ("direct", "http_proxy")
NETWORK_STATUSES = ("disabled", "pending", "applying", "ready", "degraded", "failed")
OBSERVED_NETWORK_MODES = ("unknown",) + NETWORK_MODES
BRIDGE_STATUSES = ("unknown", "stopped", "starting", "running", "unhealthy")

_MODE_CHECK = (
    "(mode = 'direct' AND proxy_host IS NULL AND proxy_port IS NULL "
    "AND proxy_username_secret_ref IS NULL AND proxy_password_secret_ref IS NULL "
    "AND bridge_host_port IS NULL AND bridge_device_port IS NULL) OR "
    "(mode = 'http_proxy' AND proxy_host IS NOT NULL AND proxy_port IS NOT NULL "
    "AND bridge_host_port IS NOT NULL AND bridge_device_port IS NOT NULL)"
)


class RuntimeNetworkConfig(Base):
    """The current desired network configuration for one Runtime."""

    __tablename__ = "runtime_network_configs"
    __table_args__ = (
        CheckConstraint("mode IN ('direct', 'http_proxy')", name="ck_runtime_network_configs_mode"),
        CheckConstraint(_MODE_CHECK, name="ck_runtime_network_configs_mode_fields"),
        CheckConstraint("proxy_port IS NULL OR (proxy_port >= 1 AND proxy_port <= 65535)", name="ck_runtime_network_configs_proxy_port"),
        CheckConstraint("bridge_host_port IS NULL OR (bridge_host_port >= 1 AND bridge_host_port <= 65535)", name="ck_runtime_network_configs_bridge_host_port"),
        CheckConstraint("bridge_device_port IS NULL OR (bridge_device_port >= 1 AND bridge_device_port <= 65535)", name="ck_runtime_network_configs_bridge_device_port"),
        CheckConstraint("desired_revision > 0", name="ck_runtime_network_configs_revision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    runtime_id: Mapped[int] = mapped_column(ForeignKey("runtimes.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    proxy_host: Mapped[str | None] = mapped_column(String(253))
    proxy_port: Mapped[int | None] = mapped_column(Integer)
    proxy_username_secret_ref: Mapped[str | None] = mapped_column(String(255))
    proxy_password_secret_ref: Mapped[str | None] = mapped_column(String(255))
    bridge_host_port: Mapped[int | None] = mapped_column(Integer, unique=True)
    bridge_device_port: Mapped[int | None] = mapped_column(Integer)
    desired_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    runtime: Mapped["Runtime"] = relationship(back_populates="network_config")


class RuntimeNetworkConfigRevision(Base):
    """Immutable snapshot of a Runtime's desired network configuration."""

    __tablename__ = "runtime_network_config_revisions"
    __table_args__ = (
        UniqueConstraint("runtime_id", "revision", name="uq_runtime_network_revision"),
        CheckConstraint("mode IN ('direct', 'http_proxy')", name="ck_runtime_network_revisions_mode"),
        CheckConstraint(_MODE_CHECK, name="ck_runtime_network_revisions_mode_fields"),
        CheckConstraint("proxy_port IS NULL OR (proxy_port >= 1 AND proxy_port <= 65535)", name="ck_runtime_network_revisions_proxy_port"),
        CheckConstraint("bridge_host_port IS NULL OR (bridge_host_port >= 1 AND bridge_host_port <= 65535)", name="ck_runtime_network_revisions_bridge_host_port"),
        CheckConstraint("bridge_device_port IS NULL OR (bridge_device_port >= 1 AND bridge_device_port <= 65535)", name="ck_runtime_network_revisions_bridge_device_port"),
        CheckConstraint("revision > 0", name="ck_runtime_network_revisions_revision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    runtime_id: Mapped[int] = mapped_column(ForeignKey("runtimes.id", ondelete="CASCADE"), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    proxy_host: Mapped[str | None] = mapped_column(String(253))
    proxy_port: Mapped[int | None] = mapped_column(Integer)
    proxy_username_secret_ref: Mapped[str | None] = mapped_column(String(255))
    proxy_password_secret_ref: Mapped[str | None] = mapped_column(String(255))
    bridge_host_port: Mapped[int | None] = mapped_column(Integer)
    bridge_device_port: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    runtime: Mapped["Runtime"] = relationship(back_populates="network_config_revisions")


class RuntimeNetworkState(Base):
    """Last observed application state for one managed Runtime network."""

    __tablename__ = "runtime_network_states"
    __table_args__ = (
        CheckConstraint("status IN ('disabled', 'pending', 'applying', 'ready', 'degraded', 'failed')", name="ck_runtime_network_states_status"),
        CheckConstraint("observed_mode IN ('unknown', 'direct', 'http_proxy')", name="ck_runtime_network_states_observed_mode"),
        CheckConstraint("bridge_status IN ('unknown', 'stopped', 'starting', 'running', 'unhealthy')", name="ck_runtime_network_states_bridge_status"),
        CheckConstraint("desired_revision > 0", name="ck_runtime_network_states_desired_revision"),
        CheckConstraint("applied_revision IS NULL OR applied_revision > 0", name="ck_runtime_network_states_applied_revision"),
        CheckConstraint("observed_android_proxy_port IS NULL OR (observed_android_proxy_port >= 1 AND observed_android_proxy_port <= 65535)", name="ck_runtime_network_states_proxy_port"),
    )

    runtime_id: Mapped[int] = mapped_column(ForeignKey("runtimes.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    desired_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    applied_revision: Mapped[int | None] = mapped_column(Integer)
    observed_mode: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    observed_android_proxy_host: Mapped[str | None] = mapped_column(String(253))
    observed_android_proxy_port: Mapped[int | None] = mapped_column(Integer)
    reverse_present: Mapped[bool | None]
    bridge_status: Mapped[str] = mapped_column(String(20), default="stopped", nullable=False)
    bridge_owner_token: Mapped[str | None] = mapped_column(String(36))
    bridge_supervisor_id: Mapped[str | None] = mapped_column(String(255))
    bridge_pid: Mapped[int | None] = mapped_column(Integer)
    bridge_process_start_token: Mapped[str | None] = mapped_column(String(100))
    last_apply_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_probe_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    runtime: Mapped["Runtime"] = relationship(back_populates="network_state")

