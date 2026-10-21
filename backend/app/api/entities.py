"""Entity lookup endpoints for UPI IDs, phones and URLs."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.db import repository
from app.db.session import get_db
from app.schemas.analysis import EntityHistoryResponse, EntityLookupQuery, ReportSummary
from app.schemas.errors import ERROR_RESPONSES
from app.services.entities import infer_entity_type, normalize_entity_value

logger = logging.getLogger(__name__)

router = APIRouter(tags=["entities"], responses=ERROR_RESPONSES)


def _lookup(value: str, entity_type: str | None, db: Session) -> EntityHistoryResponse:
    raw_value = value.strip()
    if not raw_value:
        raise HTTPException(status_code=422, detail="entity value must not be empty")

    resolved_type = entity_type or infer_entity_type(raw_value)
    if resolved_type:
        try:
            normalized_value = normalize_entity_value(resolved_type, raw_value)
        except ValueError:
            raise HTTPException(status_code=422, detail="entity value is invalid")
    else:
        normalized_value = raw_value.lower()

    try:
        entity = repository.find_entity_by_value(
            db,
            value=normalized_value,
            entity_type=resolved_type,
        )
    except ValueError:
        raise HTTPException(status_code=422, detail="entity value is invalid")
    if entity is None:
        raise HTTPException(status_code=404, detail="No reports found for this entity.")

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


@router.get("/entities", response_model=EntityHistoryResponse)
def entity_history_query(
    query: Annotated[EntityLookupQuery, Query()],
    db: Session = Depends(get_db),
) -> EntityHistoryResponse:
    """Look up an entity using a query parameter, which safely carries URLs."""
    return _lookup(query.value, query.entity_type, db)


@router.get("/entities/{entity_value}", response_model=EntityHistoryResponse)
def entity_history(
    entity_value: Annotated[str, Path(min_length=1, max_length=512)],
    db: Session = Depends(get_db),
) -> EntityHistoryResponse:
    """Backward-compatible path form of entity lookup."""
    return _lookup(entity_value, None, db)
