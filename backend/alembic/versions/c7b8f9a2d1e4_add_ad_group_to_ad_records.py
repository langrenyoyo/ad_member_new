"""add ad group to ad records

Revision ID: c7b8f9a2d1e4
Revises: 8db735c18587
Create Date: 2026-08-23 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7b8f9a2d1e4"
down_revision: Union[str, None] = "8db735c18587"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ad_records",
        sa.Column("ad_group", sa.String(length=32), server_default="主广", nullable=False),
    )
    op.execute(
        """
        UPDATE ad_records
        SET ad_group = CASE
            WHEN is_fu = 1
                OR ad_type = '副广'
                OR sub_ad_type = '副广'
                OR ad_type LIKE '%插屏%'
                OR ad_type LIKE '%开屏%'
                OR ad_type LIKE '%横幅%'
                OR ad_type LIKE '%信息流%'
                OR sub_ad_type LIKE '%插屏%'
                OR sub_ad_type LIKE '%开屏%'
                OR sub_ad_type LIKE '%横幅%'
                OR sub_ad_type LIKE '%信息流%'
            THEN '副广'
            ELSE '主广'
        END
        """
    )


def downgrade() -> None:
    op.drop_column("ad_records", "ad_group")
