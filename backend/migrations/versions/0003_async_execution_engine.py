"""async execution engine

Revision ID: 0003_async_execution_engine
Revises: 0002_structural_expansion
Create Date: 2026-06-22 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_async_execution_engine"
down_revision = "0002_structural_expansion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sync_jobs") as batch_op:
        batch_op.add_column(sa.Column("correlation_id", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.text("0")))

    with op.batch_alter_table("integration_logs") as batch_op:
        batch_op.add_column(sa.Column("source_payload_masked", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("transformed_payload_masked", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("response_payload_masked", sa.Text(), nullable=True))

    with op.batch_alter_table("integration_errors") as batch_op:
        batch_op.add_column(sa.Column("flow_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("error_message", sa.String(length=500), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("normalized_message", sa.String(length=500), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("raw_error_masked", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("correlation_id", sa.String(length=100), nullable=True))
        batch_op.create_foreign_key(
            "fk_integration_errors_flow_id_integration_flows",
            "integration_flows",
            ["flow_id"],
            ["id"],
        )

    op.create_index("ix_sync_jobs_correlation_id", "sync_jobs", ["correlation_id"])
    op.create_index("ix_integration_errors_flow_id", "integration_errors", ["flow_id"])
    op.create_index("ix_integration_errors_correlation_id", "integration_errors", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_integration_errors_correlation_id", table_name="integration_errors")
    op.drop_index("ix_integration_errors_flow_id", table_name="integration_errors")
    op.drop_index("ix_sync_jobs_correlation_id", table_name="sync_jobs")

    with op.batch_alter_table("integration_errors") as batch_op:
        batch_op.drop_column("correlation_id")
        batch_op.drop_column("retryable")
        batch_op.drop_column("raw_error_masked")
        batch_op.drop_column("normalized_message")
        batch_op.drop_column("error_message")
        batch_op.drop_column("flow_id")

    with op.batch_alter_table("integration_logs") as batch_op:
        batch_op.drop_column("response_payload_masked")
        batch_op.drop_column("transformed_payload_masked")
        batch_op.drop_column("source_payload_masked")

    with op.batch_alter_table("sync_jobs") as batch_op:
        batch_op.drop_column("cancel_requested")
        batch_op.drop_column("correlation_id")
