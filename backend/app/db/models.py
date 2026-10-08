"""ORM models for the Scam Shield relational scam graph (per master spec §9).

Logical model:
    reports  --<  report_entities  >--  entities
                    |
              (scam-side identifiers: URL, UPI ID, phone number, ...)
    reports  --   verdicts          (one verdict per report)
    patterns                          (rule detections -> evidence, filled in M2)
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
    String,
    Text,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Report(Base):
    """A single submitted scam report (text or screenshot-derived)."""

    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('text', 'screenshot')",
            name="ck_reports_source_type",
        ),
        CheckConstraint(
            "status IN ('submitted', 'processing', 'completed', 'failed')",
            name="ck_reports_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # redacted content after M2
    normalized_content: Mapped[str | None] = mapped_column(Text, nullable=True)  # filled by M2 pipeline
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="text")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="submitted", index=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1, filled by M2 scoring
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    verdict: Mapped["Verdict | None"] = relationship(back_populates="report", uselist=False)
    entities: Mapped[list["ReportEntity"]] = relationship(back_populates="report")


class Entity(Base):
    """A scam-side identifier extracted from reports (the graph nodes).

    Only strong identifiers become graph links (URL, UPI ID, phone number,
    account-like identifier). Attributes like amount stay on the report.
    """

    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("entity_type", "normalized_value", name="uq_entities_type_value"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # url | upi_id | phone | ...
    normalized_value: Mapped[str] = mapped_column(Text, nullable=False, index=True)  # stable form for linking
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)  # as submitted
    metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # extraction details (M2)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    reports: Mapped[list["ReportEntity"]] = relationship(back_populates="entity")


class ReportEntity(Base):
    """Edge table: which report mentions which entity (the graph links)."""

    __tablename__ = "report_entities"
    __table_args__ = (
        UniqueConstraint("report_id", "entity_id", name="uq_report_entities_report_entity"),
    )

    report_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("reports.id", ondelete="CASCADE"), primary_key=True
    )
    entity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default="identifier")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    report: Mapped[Report] = relationship(back_populates="entities")
    entity: Mapped[Entity] = relationship(back_populates="reports")


class Pattern(Base):
    """A rule-engine detection pattern. Catalog populated in M2; report->pattern
    matches become evidence entries attached to verdicts later."""

    __tablename__ = "patterns"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)  # e.g. urgent_language
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # content_evidence | link | ...
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Verdict(Base):
    """Final decision for a report. Wording must never claim 'confirmed' from
    reports alone — decision values stay evidence-based (M2+)."""

    __tablename__ = "verdicts"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('scam_likely', 'suspicious', 'legitimate', 'unverified')",
            name="ck_verdicts_decision",
        ),
        UniqueConstraint("report_id", name="uq_verdicts_report"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    report_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # human-readable evidence summary
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    report: Mapped[Report] = relationship(back_populates="verdict")