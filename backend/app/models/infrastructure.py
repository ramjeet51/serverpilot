import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPrimaryKey


def str_enum(e: type[enum.Enum], name: str) -> Enum:
    return Enum(e, name=name, native_enum=False, validate_strings=True, length=32,
                values_callable=lambda x: [m.value for m in x])


class ServerStatus(str, enum.Enum):
    pending = "pending"
    online = "online"
    offline = "offline"
    maintenance = "maintenance"


class AgentStatus(str, enum.Enum):
    pending = "pending"
    connected = "connected"
    disconnected = "disconnected"
    revoked = "revoked"


class CertificateStatus(str, enum.Enum):
    active = "active"
    rotated = "rotated"
    revoked = "revoked"
    expired = "expired"


class Server(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "servers"

    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    environment: Mapped[str] = mapped_column(String(32), default="production", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[ServerStatus] = mapped_column(str_enum(ServerStatus, "server_status"), default=ServerStatus.pending,
                                                 nullable=False, index=True)
    os_name: Mapped[str | None] = mapped_column(String(64))
    os_version: Mapped[str | None] = mapped_column(String(64))
    kernel_version: Mapped[str | None] = mapped_column(String(128))
    cpu_cores: Mapped[int | None] = mapped_column(Integer)
    memory_total_bytes: Mapped[int | None] = mapped_column(BigInteger)
    disk_total_bytes: Mapped[int | None] = mapped_column(BigInteger)
    tags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    agent: Mapped["Agent | None"] = relationship(back_populates="server", uselist=False)


class Agent(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "agents"

    server_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"),
                                                 unique=True, nullable=False)
    agent_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    version: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[AgentStatus] = mapped_column(str_enum(AgentStatus, "agent_status"), default=AgentStatus.pending,
                                                nullable=False, index=True)
    auth_mode: Mapped[str] = mapped_column(String(16), default="mtls", nullable=False)
    registration_token_hash: Mapped[str | None] = mapped_column(Text)
    registration_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    remote_ip: Mapped[str | None] = mapped_column(String(45))
    capabilities: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    server: Mapped[Server] = relationship(back_populates="agent")
    certificates: Mapped[list["AgentCertificate"]] = relationship(back_populates="agent", cascade="all, delete-orphan")


class AgentCertificate(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "agent_certificates"

    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"),
                                                nullable=False, index=True)
    serial_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    fingerprint_sha256: Mapped[str] = mapped_column(String(95), unique=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CertificateStatus] = mapped_column(str_enum(CertificateStatus, "certificate_status"),
                                                      default=CertificateStatus.active, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(String(255))

    agent: Mapped[Agent] = relationship(back_populates="certificates")
