"""add review audit fields

Revision ID: a4d9f2c8e7b1
Revises: f2e8a1b9c3d4
Create Date: 2026-08-30 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4d9f2c8e7b1"
down_revision: Union[str, None] = "f2e8a1b9c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("withdrawals", sa.Column("audit_operator_id", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("withdrawals", sa.Column("audit_operator_name", sa.String(length=128), nullable=False, server_default=""))
    op.add_column("withdrawals", sa.Column("audited_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("withdrawals", sa.Column("transfer_operator_id", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("withdrawals", sa.Column("transfer_operator_name", sa.String(length=128), nullable=False, server_default=""))
    op.add_column("withdrawals", sa.Column("transferred_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("subsidies", sa.Column("audit_operator_id", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("subsidies", sa.Column("audit_operator_name", sa.String(length=128), nullable=False, server_default=""))
    op.add_column("subsidies", sa.Column("audited_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("subsidies", "audited_at")
    op.drop_column("subsidies", "audit_operator_name")
    op.drop_column("subsidies", "audit_operator_id")

    op.drop_column("withdrawals", "transferred_at")
    op.drop_column("withdrawals", "transfer_operator_name")
    op.drop_column("withdrawals", "transfer_operator_id")
    op.drop_column("withdrawals", "audited_at")
    op.drop_column("withdrawals", "audit_operator_name")
    op.drop_column("withdrawals", "audit_operator_id")
