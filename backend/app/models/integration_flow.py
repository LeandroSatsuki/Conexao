from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class IntegrationFlow(Base):
    __tablename__ = "integration_flows"
    __table_args__ = (
        Index("ix_integration_flows_tenant_id", "tenant_id"),
        Index("ix_integration_flows_active", "active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_connection_id: Mapped[str] = mapped_column(ForeignKey("connections.id"), nullable=False)
    target_connection_id: Mapped[str] = mapped_column(ForeignKey("connections.id"), nullable=False)
    source_entity: Mapped[str] = mapped_column(String(100), nullable=False)
    target_entity: Mapped[str] = mapped_column(String(100), nullable=False)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    schedule_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant = relationship("Tenant", back_populates="integration_flows")
    source_connection = relationship("Connection", foreign_keys=[source_connection_id])
    target_connection = relationship("Connection", foreign_keys=[target_connection_id])
    field_mappings = relationship("FieldMapping", back_populates="flow", cascade="all, delete-orphan")
