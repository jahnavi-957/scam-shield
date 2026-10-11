"""Entity endpoint: report history for a UPI ID / phone / URL."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import repository
from app.db.session import get_db
from app.schemas.analysis import EntityHistoryResponse, ReportSummary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["entities"])


@router.get("/entities/{entity_value}", response_model=EntityHistoryResponse)
def entity_history(entity_value: str, db: Session = Depends(get_db)) -> EntityHistoryResponse:
    """Report history for one entity — the "search before you
    pay" feature. The value is matched on its normalised form
    (phones are +91-normalised, UPI IDs/URLs lowercased by
    the extractor), so pass it URL-encoded.

    Returns 404 when the entity has never been reported —
    for this feature, "not found" is the good outcome.
    """
    value = entity_value.strip().lower()
    if not value:
        raise HTTPException(status_code=422, detail="entity_value must not be empty")

    entity = repository.find_entity_by_value(db, value=value)
    if entity is None:
        raise HTTPException(
            status_code=404,
            detail=f"No reports found for '{entity_value}'.",
        )

    history = repository.get_entity_history(db, entity_id=entity.id)

    logger.info(
        "entity looked up",
        extra={
            "event": "entity_lookup",
            "entity_type": entity.entity_type,
            "report_count": entity.report_count,
        },
    )
    return EntityHistoryResponse(
        entity_type=entity.entity_type,
        value=entity.normalized_value,
        report_count=entity.report_count,
        first_seen_at=entity.first_seen_at,
        last_alert_at=entity.last_alert_at,
        recent_reports=[ReportSummary(**row) for row in history],
    )
