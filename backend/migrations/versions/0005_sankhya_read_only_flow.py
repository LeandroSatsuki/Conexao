"""sankhya read only flow

Revision ID: 0005_sankhya_read_only_flow
Revises: 0004_sankhya_connection_test_operation
Create Date: 2026-06-22 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_sankhya_read_only_flow"
down_revision = "0004_sankhya_connection_test_operation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("integration_flows", sa.Column("config_json", sa.JSON(), nullable=True))
    op.add_column("sync_jobs", sa.Column("records_count", sa.Integer(), nullable=True))
    op.add_column("integration_logs", sa.Column("mode", sa.String(length=32), nullable=True))
    op.add_column("integration_logs", sa.Column("records_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("integration_logs", "records_count")
    op.drop_column("integration_logs", "mode")
    op.drop_column("sync_jobs", "records_count")
    op.drop_column("integration_flows", "config_json")
