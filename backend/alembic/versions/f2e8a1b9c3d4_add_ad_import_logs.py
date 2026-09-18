"""add ad import logs

Revision ID: f2e8a1b9c3d4
Revises: c7b8f9a2d1e4
Create Date: 2026-08-23 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2e8a1b9c3d4"
down_revision: Union[str, None] = "c7b8f9a2d1e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ad_import_batches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("file_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("operator_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("operator_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "ad_import_errors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_id", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("message", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("raw_data", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ad_import_errors_batch_id", "ad_import_errors", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_ad_import_errors_batch_id", table_name="ad_import_errors")
    op.drop_table("ad_import_errors")
    op.drop_table("ad_import_batches")
