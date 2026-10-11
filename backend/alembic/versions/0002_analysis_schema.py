"""Analysis schema — the real schema for the detection engine.

Replaces the M1 placeholder tables (reports / report_entities /
verdicts / patterns were scaffolding with different semantics:
`verdicts.decision` is a 4-value enum, whereas the pipeline
produces a scam_type label, a confidence and an embedding).

Creates:
    messages            raw submitted messages
    analysis_results    verdicts + pgvector embedding per message
    entities            scam graph nodes (UPI / phone / URL)
    message_entities    graph links (many-to-many)

The `vector` extension was already enabled by migration 0001, so
this migration needs no extra infrastructure.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- retire the M1 placeholder tables (empty; superseded) ---
    op.drop_table("report_entities")
    op.drop_table("verdicts")
    op.drop_table("patterns")
    op.drop_table("reports")
    op.drop_table("entities")

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=20), server_default="text", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('text', 'email', 'screenshot')", name="ck_messages_source"
        ),
    )
    op.create_index("ix_messages_created_at", "messages", ["created_at"])

    # --- entities (scam graph nodes) ---
    op.create_table(
        "entities",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("report_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_alert_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "entity_type IN ('upi', 'phone', 'url')", name="ck_entities_type"
        ),
        sa.UniqueConstraint("entity_type", "normalized_value", name="uq_entities_type_value"),
    )
    op.create_index("ix_entities_entity_type", "entities", ["entity_type"])

    # --- analysis results (one per message, embedding as pgvector) ---
    op.create_table(
        "analysis_results",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("scam_type", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("is_scam", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("message_id", name="uq_analysis_results_message"),
    )
    # Cosine-similarity index. IVFFlat with a small `lists` value is
    # right for a student-scale dataset; HNSW is the production
    # upgrade once reports reach the hundreds of thousands.
    op.execute(
        "CREATE INDEX ix_analysis_results_embedding "
        "ON analysis_results USING ivfflat (embedding vector_cosine_ops) WITH (lists = 16)"
    )

    # --- message <-> entity links ---
    op.create_table(
        "message_entities",
        sa.Column("message_id", sa.BigInteger(), primary_key=True),
        sa.Column("entity_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("message_entities")
    op.drop_index("ix_analysis_results_embedding", table_name="analysis_results")
    op.drop_table("analysis_results")
    op.drop_index("ix_entities_entity_type", table_name="entities")
    op.drop_table("entities")
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_table("messages")
