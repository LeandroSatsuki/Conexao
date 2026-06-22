"""structural expansion

Revision ID: 0002_structural_expansion
Revises: 0001_initial
Create Date: 2026-06-22 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_structural_expansion"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch_op:
        batch_op.add_column(sa.Column("document", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="active"))

    with op.batch_alter_table("integration_logs") as batch_op:
        batch_op.add_column(sa.Column("source_platform", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("target_platform", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("duration_ms", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("error_type", sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("integration_logs") as batch_op:
        batch_op.drop_column("error_type")
        batch_op.drop_column("duration_ms")
        batch_op.drop_column("target_platform")
        batch_op.drop_column("source_platform")

    with op.batch_alter_table("tenants") as batch_op:
        batch_op.drop_column("status")
        batch_op.drop_column("document")
