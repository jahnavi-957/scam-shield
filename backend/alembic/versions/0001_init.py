"""initial scam graph schema

Enables pgvector and creates the M1 core tables:
reports, entities, report_entities, patterns, verdicts.

NOTE: vector columns are NOT added here — they arrive with M2 (similarity)
once the pipeline exists. The extension is enabled now so M2 needs no
infrastructure change and to prove pgvector loading in the local image.

Revision ID: 0001
Revises:
Create Date: 2026-10-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "reports",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("normalized_content", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=20), server_default="text", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="submitted", nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('text', 'screenshot')",
            name="ck_reports_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('submitted', 'processing', 'completed', 'failed')",
            name="ck_reports_status",
        ),
    )
    op.create_index("ix_reports_status", "reports", ["status"])

    op.create_table(
        "entities",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("entity_type", "normalized_value", name="uq_entities_type_value"),
    )
    op.create_index("ix_entities_entity_type", "entities", ["entity_type"])
    op.create_index("ix_entities_normalized_value", "entities", ["normalized_value"])

    op.create_table(
        "report_entities",
        sa.Column("report_id", sa.BigInteger(), primary_key=True),
        sa.Column("entity_id", sa.BigInteger(), primary_key=True),
        sa.Column("role", sa.String(length=50), server_default="identifier", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("report_id", "entity_id", name="uq_report_entities_report_entity"),
    )

    op.create_table(
        "patterns",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("code", name="uq_patterns_code"),
    )

    op.create_table(
        "verdicts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision IN ('scam_likely', 'suspicious', 'legitimate', 'unverified')",
            name="ck_verdicts_decision",
        ),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("report_id", name="uq_verdicts_report"),
    )


def downgrade() -> None:
    op.drop_table("verdicts")
    op.drop_table("patterns")
    op.drop_table("report_entities")
    op.drop_index("ix_entities_normalized_value", table_name="entities")
    op.drop_index("ix_entities_entity_type", table_name="entities")
    op.drop_table("entities")
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_table("reports")
    # The extension is intentionally left installed on downgrade: removing it
    # would also drop any vector columns that later milestones add, which a
    # schema rollback should never do silently.
    # op.execute("DROP EXTENSION IF EXISTS vector")