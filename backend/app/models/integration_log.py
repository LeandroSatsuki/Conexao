from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class IntegrationLog(Base):
    __tablename__ = "integration_logs"
    __table_args__ = (
        Index("ix_integration_logs_tenant_id", "tenant_id"),
        Index("ix_integration_logs_job_id", "job_id"),
        Index("ix_integration_logs_flow_id", "flow_id"),
        Index("ix_integration_logs_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    connection_id: Mapped[str | None] = mapped_column(ForeignKey("connections.id"), nullable=True)
    flow_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("sync_jobs.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, default="integration_execution")
    operation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_entity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_entity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_payload_masked: Mapped[str | None] = mapped_column(Text, nullable=True)
    transformed_payload_masked: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_payload_masked: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_masked: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    tenant = relationship("Tenant", back_populates="integration_logs")
    connection = relationship("Connection")
    sync_job = relationship("SyncJob", back_populates="integration_logs")
