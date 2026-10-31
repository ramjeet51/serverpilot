"""Plugins, software inventory, deployments, metrics, notifications, audit and credential references."""

import uuid
from datetime import datetime

from sqlalchemy import (BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPrimaryKey


class CredentialReference(UUIDPrimaryKey, Timestamps, Base):
    """Points to a secret held elsewhere (env var, macOS Keychain, Vault, file). Never stores the secret itself."""

    __tablename__ = "credentials_references"

    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_key: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class Plugin(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "plugins"

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    publisher: Mapped[str] = mapped_column(String(128), default="serverpilot", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    latest_version: Mapped[str | None] = mapped_column(String(32))

    versions: Mapped[list["PluginVersion"]] = relationship(back_populates="plugin", cascade="all, delete-orphan")


class PluginVersion(UUIDPrimaryKey, Base):
    __tablename__ = "plugin_versions"
    __table_args__ = (UniqueConstraint("plugin_id", "version", name="uq_plugin_versions_plugin_version"),)

    plugin_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plugins.id", ondelete="CASCADE"),
                                                 nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    supported_os: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    is_trusted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    plugin: Mapped[Plugin] = relationship(back_populates="versions")


class SoftwareInventory(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "software_inventory"
    __table_args__ = (UniqueConstraint("server_id", "package_name", name="uq_software_inventory_server_package"),)

    server_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"),
                                                 nullable=False, index=True)
    package_name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str | None] = mapped_column(String(128))
    candidate_version: Mapped[str | None] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(32), default="apt", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="installed", nullable=False)
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ServiceInventory(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "service_inventory"
    __table_args__ = (UniqueConstraint("server_id", "unit_name", name="uq_service_inventory_server_unit"),)

    server_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"),
                                                 nullable=False, index=True)
    unit_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    active_state: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    sub_state: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    unit_file_state: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)


class Deployment(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "deployments"

    server_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"),
                                                 nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    deployment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    repository_url: Mapped[str | None] = mapped_column(String(512))
    branch: Mapped[str | None] = mapped_column(String(255))
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    current_version: Mapped[str | None] = mapped_column(String(64))
    credentials_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credentials_references.id", ondelete="SET NULL"))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    history: Mapped[list["DeploymentHistory"]] = relationship(back_populates="deployment", cascade="all, delete-orphan")


class DeploymentHistory(UUIDPrimaryKey, Base):
    __tablename__ = "deployment_history"

    deployment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deployments.id", ondelete="CASCADE"),
                                                     nullable=False, index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"))
    version: Mapped[str | None] = mapped_column(String(64))
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    is_rollback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    deployment: Mapped[Deployment] = relationship(back_populates="history")


class ServerMetric(Base):
    __tablename__ = "server_metrics"
    __table_args__ = (Index("ix_server_metrics_server_collected", "server_id", "collected_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"),
                                                 nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False)
    memory_percent: Mapped[float] = mapped_column(Float, nullable=False)
    memory_used_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    disk_percent: Mapped[float] = mapped_column(Float, nullable=False)
    net_rx_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    net_tx_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    load_1: Mapped[float | None] = mapped_column(Float)
    load_5: Mapped[float | None] = mapped_column(Float)
    load_15: Mapped[float | None] = mapped_column(Float)
    process_count: Mapped[int | None] = mapped_column(Integer)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_actor_user_id", "actor_user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    actor_type: Mapped[str] = mapped_column(String(16), default="user", nullable=False)
    actor_label: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(16), default="success", nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NotificationSetting(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "notification_settings"

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                                                      index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    event_types: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    target_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credentials_references.id", ondelete="SET NULL"))
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_severity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
