from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    document: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    slug: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)
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

    connections = relationship("Connection", back_populates="tenant", cascade="all, delete-orphan")
    integration_flows = relationship("IntegrationFlow", back_populates="tenant")
    field_mappings = relationship("FieldMapping", back_populates="tenant")
    integration_logs = relationship("IntegrationLog", back_populates="tenant", cascade="all, delete-orphan")
    sync_jobs = relationship("SyncJob", back_populates="tenant", cascade="all, delete-orphan")
