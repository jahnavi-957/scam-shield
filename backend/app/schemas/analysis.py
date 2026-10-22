"""Pydantic request/response models for the analysis API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
class AnalyzeTextRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=10_000,
        examples=["Congratulations! You've won a prize. Pay Rs. 500 to fraud123@okaxis"],
    )


class AnalyzeScreenshotRequest(BaseModel):
    # Flat uploads/{uuid}.{png|jpg} keys only — no path
    # traversal, no user-controlled prefixes.
    s3_key: str = Field(
        pattern=r"^uploads/[0-9a-f]{32}\.(?:png|jpg)$",
        examples=["uploads/9f8c2b1a4d5e6f708192a3b4c5d6e7f8.png"],
    )


class PresignedUploadRequest(BaseModel):
    """Validated query parameters for a presigned screenshot upload."""

    content_type: Literal["image/png", "image/jpeg"] = "image/png"
    expires_in: int | None = Field(default=None, ge=1, le=300)


class EntityLookupQuery(BaseModel):
    """Query-string form of entity lookup, including optional type context."""

    value: str = Field(min_length=1, max_length=512)
    entity_type: Literal["upi", "phone", "url"] | None = None


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #
class EntitySummary(BaseModel):
    """One extracted entity, with its current report count."""

    type: str
    value: str
    report_count: int


class AnalysisResponse(BaseModel):
    """Full verdict returned by POST /analyze/*."""

    message_id: int
    source: str
    is_scam: bool
    scam_type: str
    confidence: float
    explanation: str
    entities: list[EntitySummary]
    # Reports on the most-reported entity in this message,
    # EXCLUDING the current one (0 for a first report).
    prior_reports: int
    # Message IDs of near-duplicate past reports
    # (pgvector cosine similarity >= 0.85).
    near_duplicates: list[int]
    alert_triggered: bool
    created_at: datetime
    # Diagnostics carried through from ScamVerdict. Database-backed
    # `near_duplicates` remains the authoritative report-match list.
    truncated: bool = False
    classifier_kind: str = ""
    similarity_score: float | None = None
    matched_scam_id: str | None = None


class PresignedUploadResponse(BaseModel):
    """A direct-to-S3 upload capability for the frontend."""

    s3_key: str
    url: str
    method: str = "PUT"
    # The frontend MUST send this Content-Type with the PUT
    # request — the URL is signed for it.
    content_type: str
    expires_in: int


class ReportSummary(BaseModel):
    """One past report for the entity history endpoint."""

    message_id: int
    source: str
    scam_type: str | None = None
    confidence: float | None = None
    is_scam: bool | None = None
    created_at: datetime


class EntityHistoryResponse(BaseModel):
    """Report history for one UPI ID / phone / URL —
    powers the "search before you pay" feature."""

    entity_type: str
    value: str
    report_count: int
    first_seen_at: datetime
    last_alert_at: datetime | None = None
    recent_reports: list[ReportSummary]
