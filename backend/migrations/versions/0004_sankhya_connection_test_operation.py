"""sankhya connection test operation

Revision ID: 0004_sankhya_connection_test_operation
Revises: 0003_async_execution_engine
Create Date: 2026-06-22 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_sankhya_connection_test_operation"
down_revision = "0003_async_execution_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("integration_logs", sa.Column("operation", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("integration_logs", "operation")
