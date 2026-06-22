from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class IntegrationError(Base):
    __tablename__ = "integration_errors"
    __table_args__ = (
        Index("ix_integration_errors_tenant_id", "tenant_id"),
        Index("ix_integration_errors_job_id", "job_id"),
        Index("ix_integration_errors_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("sync_jobs.id"), nullable=True)
    log_id: Mapped[str | None] = mapped_column(ForeignKey("integration_logs.id"), nullable=True)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    tenant = relationship("Tenant")
    sync_job = relationship("SyncJob")
    integration_log = relationship("IntegrationLog")
