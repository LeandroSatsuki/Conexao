"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-22 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=True, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "connectors",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("platform", sa.String(length=100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_connectors_tenant_id", "connectors", ["tenant_id"])
    op.create_index("ix_connectors_platform", "connectors", ["platform"])

    op.create_table(
        "connections",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("platform", sa.String(length=100), nullable=False),
        sa.Column("environment", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_test_status", sa.String(length=32), nullable=True),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_connections_tenant_id", "connections", ["tenant_id"])
    op.create_index("ix_connections_platform", "connections", ["platform"])
    op.create_index("ix_connections_status", "connections", ["status"])
    op.create_index("ix_connections_created_at", "connections", ["created_at"])

    op.create_table(
        "integration_flows",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_connection_id", sa.String(length=36), sa.ForeignKey("connections.id"), nullable=False),
        sa.Column("target_connection_id", sa.String(length=36), sa.ForeignKey("connections.id"), nullable=False),
        sa.Column("source_entity", sa.String(length=100), nullable=False),
        sa.Column("target_entity", sa.String(length=100), nullable=False),
        sa.Column("trigger_type", sa.String(length=50), nullable=False),
        sa.Column("schedule_cron", sa.String(length=100), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_integration_flows_tenant_id", "integration_flows", ["tenant_id"])
    op.create_index("ix_integration_flows_active", "integration_flows", ["active"])

    op.create_table(
        "field_mappings",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("flow_id", sa.String(length=36), sa.ForeignKey("integration_flows.id"), nullable=False),
        sa.Column("source_field", sa.String(length=100), nullable=False),
        sa.Column("target_field", sa.String(length=100), nullable=False),
        sa.Column("transformation_rule", sa.String(length=100), nullable=True),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_field_mappings_tenant_id", "field_mappings", ["tenant_id"])
    op.create_index("ix_field_mappings_flow_id", "field_mappings", ["flow_id"])
    op.create_index("ix_field_mappings_active", "field_mappings", ["active"])

    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("flow_id", sa.String(length=36), nullable=True),
        sa.Column("connection_id", sa.String(length=36), sa.ForeignKey("connections.id"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("source_payload", sa.JSON(), nullable=True),
        sa.Column("transformed_payload", sa.JSON(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sync_jobs_tenant_id", "sync_jobs", ["tenant_id"])
    op.create_index("ix_sync_jobs_status", "sync_jobs", ["status"])
    op.create_index("ix_sync_jobs_flow_id", "sync_jobs", ["flow_id"])
    op.create_index("ix_sync_jobs_created_at", "sync_jobs", ["created_at"])

    op.create_table(
        "integration_logs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("connection_id", sa.String(length=36), sa.ForeignKey("connections.id"), nullable=True),
        sa.Column("flow_id", sa.String(length=36), nullable=True),
        sa.Column("job_id", sa.String(length=36), sa.ForeignKey("sync_jobs.id"), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("platform_source", sa.String(length=100), nullable=True),
        sa.Column("platform_target", sa.String(length=100), nullable=True),
        sa.Column("source_entity", sa.String(length=100), nullable=True),
        sa.Column("target_entity", sa.String(length=100), nullable=True),
        sa.Column("payload_masked", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("http_status_code", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_integration_logs_tenant_id", "integration_logs", ["tenant_id"])
    op.create_index("ix_integration_logs_job_id", "integration_logs", ["job_id"])
    op.create_index("ix_integration_logs_flow_id", "integration_logs", ["flow_id"])
    op.create_index("ix_integration_logs_created_at", "integration_logs", ["created_at"])

    op.create_table(
        "integration_errors",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("job_id", sa.String(length=36), sa.ForeignKey("sync_jobs.id"), nullable=True),
        sa.Column("log_id", sa.String(length=36), sa.ForeignKey("integration_logs.id"), nullable=True),
        sa.Column("error_type", sa.String(length=100), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_integration_errors_tenant_id", "integration_errors", ["tenant_id"])
    op.create_index("ix_integration_errors_job_id", "integration_errors", ["job_id"])
    op.create_index("ix_integration_errors_created_at", "integration_errors", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_integration_errors_created_at", table_name="integration_errors")
    op.drop_index("ix_integration_errors_job_id", table_name="integration_errors")
    op.drop_index("ix_integration_errors_tenant_id", table_name="integration_errors")
    op.drop_table("integration_errors")

    op.drop_index("ix_integration_logs_created_at", table_name="integration_logs")
    op.drop_index("ix_integration_logs_flow_id", table_name="integration_logs")
    op.drop_index("ix_integration_logs_job_id", table_name="integration_logs")
    op.drop_index("ix_integration_logs_tenant_id", table_name="integration_logs")
    op.drop_table("integration_logs")

    op.drop_index("ix_sync_jobs_created_at", table_name="sync_jobs")
    op.drop_index("ix_sync_jobs_flow_id", table_name="sync_jobs")
    op.drop_index("ix_sync_jobs_status", table_name="sync_jobs")
    op.drop_index("ix_sync_jobs_tenant_id", table_name="sync_jobs")
    op.drop_table("sync_jobs")

    op.drop_index("ix_field_mappings_active", table_name="field_mappings")
    op.drop_index("ix_field_mappings_flow_id", table_name="field_mappings")
    op.drop_index("ix_field_mappings_tenant_id", table_name="field_mappings")
    op.drop_table("field_mappings")

    op.drop_index("ix_integration_flows_active", table_name="integration_flows")
    op.drop_index("ix_integration_flows_tenant_id", table_name="integration_flows")
    op.drop_table("integration_flows")

    op.drop_index("ix_connections_created_at", table_name="connections")
    op.drop_index("ix_connections_status", table_name="connections")
    op.drop_index("ix_connections_platform", table_name="connections")
    op.drop_index("ix_connections_tenant_id", table_name="connections")
    op.drop_table("connections")

    op.drop_index("ix_connectors_platform", table_name="connectors")
    op.drop_index("ix_connectors_tenant_id", table_name="connectors")
    op.drop_table("connectors")

    op.drop_table("tenants")
