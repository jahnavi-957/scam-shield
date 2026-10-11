"""ORM models for the Scam Shield analysis schema.

Replaces the M1 placeholder tables (reports/verdicts/patterns) via
Alembic migration 0002. Logical model:

    messages  --<  analysis_results        (one verdict per message)
    messages  --<  message_entities  >--  entities
                                            (the scam graph nodes:
                                             UPI IDs, phones, URLs)

`analysis_results.embedding` is a pgvector column: cosine similarity
against past reports runs inside RDS (`embedding <=> query`), so the
small EC2 instance never pays for embedding math.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# pgvector column type. RDS PostgreSQL supports the `vector`
# extension (enabled in migration 0001); locally the compose
# stack uses the pgvector/pgvector image, so the same code
# runs in dev and in the cloud.
try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - only when deps are missing
    raise ImportError(
        "pgvector is required: pip install pgvector "
        "(and enable the `vector` extension in PostgreSQL)"
    )

EMBEDDING_DIM = 384  # output length of all-MiniLM-L6-v2 (ml package)


class Message(Base):
    """One submitted message, raw text only (PII redaction happens
    in the ml layer before anything is persisted beyond this row)."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "source IN ('text', 'email', 'screenshot')",
            name="ck_messages_source",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="text")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    analysis: Mapped["AnalysisResult | None"] = relationship(
        back_populates="message", uselist=False, cascade="all, delete-orphan"
    )
    entities: Mapped[list["MessageEntity"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class AnalysisResult(Base):
    """Verdict for one message. `embedding` is the 384-dim sentence
    vector; stored as pgvector so near-duplicate detection
    (cosine distance <=> operator) happens in the database."""

    __tablename__ = "analysis_results"
    __table_args__ = (UniqueConstraint("message_id", name="uq_analysis_results_message"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    scam_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    is_scam: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    message: Mapped["Message"] = relationship(back_populates="analysis")


class Entity(Base):
    """A scam-side identifier extracted from a message — the nodes of
    the scam intelligence graph. (type, normalized_value) is unique,
    so the same UPI ID reported by different victims links to one
    row whose report_count keeps growing."""

    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("entity_type", "normalized_value", name="uq_entities_type_value"),
        CheckConstraint("entity_type IN ('upi', 'phone', 'url')", name="ck_entities_type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    normalized_value: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # Cooldown timestamp for the SNS alert rule: while it falls
    # inside the alert window, no second alert fires for this entity.
    last_alert_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reports: Mapped[list["MessageEntity"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class MessageEntity(Base):
    """Join table: which message mentioned which entity (the graph links)."""

    __tablename__ = "message_entities"

    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    entity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    message: Mapped["Message"] = relationship(back_populates="entities")
    entity: Mapped["Entity"] = relationship(back_populates="reports")
