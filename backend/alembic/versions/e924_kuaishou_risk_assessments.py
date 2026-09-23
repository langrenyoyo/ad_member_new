"""add manual kuaishou risk assessment snapshots

Revision ID: e924_kuaishou_risk_assessments
Revises: e923_agent_analysis
"""

from alembic import op
import sqlalchemy as sa


revision = "e924_kuaishou_risk_assessments"
down_revision = "e923_agent_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kuaishou_risk_assessments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assessment_date", sa.Date(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("game_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pay_rate", sa.Float(), nullable=False),
        sa.Column("retain_1", sa.Float(), nullable=False),
        sa.Column("ctr", sa.Float(), nullable=False),
        sa.Column("flow_growth", sa.Float(), nullable=False),
        sa.Column("device_repeat", sa.Float(), nullable=False),
        sa.Column("pay_score", sa.Float(), nullable=False),
        sa.Column("retain_score", sa.Float(), nullable=False),
        sa.Column("ctr_score", sa.Float(), nullable=False),
        sa.Column("flow_score", sa.Float(), nullable=False),
        sa.Column("device_score", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False, server_default="v1-revised"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("operator_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("operator_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kuaishou_risk_assessments_assessment_date", "kuaishou_risk_assessments", ["assessment_date"])
    op.create_index("ix_kuaishou_risk_assessments_agent_id", "kuaishou_risk_assessments", ["agent_id"])
    op.create_index("ix_kuaishou_risk_assessments_game_id", "kuaishou_risk_assessments", ["game_id"])


def downgrade() -> None:
    op.drop_index("ix_kuaishou_risk_assessments_game_id", table_name="kuaishou_risk_assessments")
    op.drop_index("ix_kuaishou_risk_assessments_agent_id", table_name="kuaishou_risk_assessments")
    op.drop_index("ix_kuaishou_risk_assessments_assessment_date", table_name="kuaishou_risk_assessments")
    op.drop_table("kuaishou_risk_assessments")
