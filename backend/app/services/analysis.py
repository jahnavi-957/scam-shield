"""Analysis orchestration: AI pipeline + persistence + entity tracking.

Flow for every analysed message (text or screenshot):

    1. persist the raw message
    2. run the AI pipeline (scamshield_ml.analyze_message)
    3. persist the verdict + its embedding
    4. look for near-duplicate past reports (pgvector cosine distance)
    5. for every extracted UPI ID / phone / URL:
         find-or-create the entity, link it to the message,
         count reports in the alert window, fire the SNS alert
         exactly when the count reaches the threshold, and bump
         the entity's lifetime report counter

SNS and S3 problems never block the classification response:
an SNS publish failure is logged and the verdict still returns.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import ai
from app.db import repository
from app.services import alerts, ocr

logger = logging.getLogger(__name__)

# Extractor output field -> entity type stored in the graph.
ENTITY_FIELDS = (
    ("upi_ids", "upi"),
    ("phone_numbers", "phone"),
    ("urls", "url"),
)

# pgvector cosine distance 0.15 == cosine similarity 0.85, which
# is the same near-duplicate threshold the ml package uses.
SIMILARITY_MAX_DISTANCE = 0.15


def analyze_text(db: Session, config, text: str) -> dict:
    """Analyse a raw text message and persist everything."""
    now = datetime.now(timezone.utc)
    message = repository.save_message(db, raw_text=text, source="text")

    verdict = ai.analyze(text)  # may raise AIPipelineError -> generic 500

    analysis = repository.save_analysis(
        db,
        message_id=message.id,
        scam_type=verdict["scam_type"],
        confidence=verdict["confidence"],
        is_scam=verdict["is_scam"],
        explanation=verdict["explanation"],
        embedding=verdict["embedding"],
    )

    similar = repository.find_similar_analyses(
        db,
        embedding=verdict["embedding"],
        max_distance=SIMILARITY_MAX_DISTANCE,
        exclude_message_id=message.id,
    )

    entities, prior_reports, alert_triggered = _track_entities(
        db, config, message.id, verdict["entities"], now
    )

    return {
        "message_id": message.id,
        "source": "text",
        "is_scam": verdict["is_scam"],
        "scam_type": verdict["scam_type"],
        "confidence": verdict["confidence"],
        "explanation": verdict["explanation"],
        "entities": entities,
        "prior_reports": prior_reports,
        "near_duplicates": [hit["message_id"] for hit in similar],
        "alert_triggered": alert_triggered,
        "created_at": analysis.created_at,
    }


def analyze_screenshot(db: Session, config, s3_key: str) -> dict:
    """OCR an already-uploaded screenshot, then run the same
    pipeline as analyse_text."""
    text = ocr.extract_text_from_image(s3_key)
    if not text.strip():
        raise ValueError("screenshot contains no readable text")

    now = datetime.now(timezone.utc)
    message = repository.save_message(db, raw_text=text, source="screenshot")

    verdict = ai.analyze(text)

    analysis = repository.save_analysis(
        db,
        message_id=message.id,
        scam_type=verdict["scam_type"],
        confidence=verdict["confidence"],
        is_scam=verdict["is_scam"],
        explanation=verdict["explanation"],
        embedding=verdict["embedding"],
    )

    similar = repository.find_similar_analyses(
        db,
        embedding=verdict["embedding"],
        max_distance=SIMILARITY_MAX_DISTANCE,
        exclude_message_id=message.id,
    )

    entities, prior_reports, alert_triggered = _track_entities(
        db, config, message.id, verdict["entities"], now
    )

    return {
        "message_id": message.id,
        "source": "screenshot",
        "is_scam": verdict["is_scam"],
        "scam_type": verdict["scam_type"],
        "confidence": verdict["confidence"],
        "explanation": verdict["explanation"],
        "entities": entities,
        "prior_reports": prior_reports,
        "near_duplicates": [hit["message_id"] for hit in similar],
        "alert_triggered": alert_triggered,
        "created_at": analysis.created_at,
    }


def _track_entities(
    db: Session,
    config,
    message_id: int,
    entities_found: dict,
    now: datetime,
) -> tuple[list[dict], int, bool]:
    """Link extracted entities to the message, evaluate the alert
    rule, and bump report counters.

    Returns (entity_summaries, prior_reports, alert_triggered).
    """
    summaries: list[dict] = []
    prior_reports = 0
    alert_triggered = False
    window = timedelta(minutes=config.alert_window_minutes)

    for field, entity_type in ENTITY_FIELDS:
        for raw_value in entities_found.get(field, []):
            value = str(raw_value).strip().lower()
            if not value:
                continue

            entity = repository.find_or_create_entity(db, entity_type=entity_type, value=value)
            repository.link_message_entity(db, message_id=message_id, entity_id=entity.id)

            # Reports on this entity in the window, EXCLUDING the
            # current message: the response's "prior_reports".
            prior = repository.get_recent_report_count(
                db,
                entity_id=entity.id,
                window_minutes=config.alert_window_minutes,
                exclude_message_id=message_id,
                now=now,
            )
            total_in_window = prior + 1  # including the current report

            if alerts.should_alert(
                total_in_window,
                threshold=config.alert_threshold,
                last_alert_at=entity.last_alert_at,
                now=now,
                window=window,
            ):
                # SNS is never on the critical path: a publish
                # failure is logged, the verdict still returns.
                try:
                    alerts.publish_alert(value, entity_type, total_in_window)
                except Exception:
                    logger.error(
                        "SNS publish failed for entity %s",
                        value,
                        extra={"entity_type": entity_type, "report_count": total_in_window},
                        exc_info=True,
                    )
                # Cooldown is set even if SNS failed: it prevents an
                # alert-retry storm; the rule re-arms next window.
                entity.last_alert_at = now
                db.commit()
                alert_triggered = True

            repository.increment_report_count(db, entity_id=entity.id)

            prior_reports = max(prior_reports, prior)
            summaries.append({"type": entity_type, "value": value, "report_count": total_in_window})

    return summaries, prior_reports, alert_triggered
