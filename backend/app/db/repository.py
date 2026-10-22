"""Repository-style data access for the analysis schema.

Every function takes an explicit SQLAlchemy ``Session`` (dependency
injected by FastAPI) and commits its own transaction — the service
layer never touches ``db.commit()``.

Transient database failures (the RDS instance sits in a private
subnet and can blip) are retried with exponential backoff by the
``@retried`` decorator: 3 attempts, 0.5s / 1s / 2s, rolling back
the failed transaction before each retry.
"""

from __future__ import annotations

import functools
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import AnalysisResult, Entity, Message, MessageEntity
from app.services.entities import normalize_entity_value


def retried(attempts: int = 3, base_delay: float = 0.5):
    """Retry a repository function on transient DB errors."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except OperationalError as exc:
                    last_exc = exc
                    db = args[0] if args else None
                    if isinstance(db, Session):
                        db.rollback()  # the failed transaction is dead
                    if attempt == attempts:
                        break
                    time.sleep(base_delay * (2 ** (attempt - 1)))
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


# --------------------------------------------------------------------------- #
# Messages and analysis results
# --------------------------------------------------------------------------- #
@retried()
def save_message(db: Session, *, raw_text: str, source: str) -> Message:
    message = Message(raw_text=raw_text, source=source)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@retried()
def save_analysis(
    db: Session,
    *,
    message_id: int,
    scam_type: str,
    confidence: float,
    is_scam: bool,
    explanation: str,
    embedding: list[float] | None,
) -> AnalysisResult:
    result = AnalysisResult(
        message_id=message_id,
        scam_type=scam_type,
        confidence=confidence,
        is_scam=is_scam,
        explanation=explanation,
        embedding=embedding,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


@retried()
def find_similar_analyses(
    db: Session,
    *,
    embedding: list[float],
    max_distance: float = 0.15,
    exclude_message_id: int | None = None,
    limit: int = 5,
) -> list[dict]:
    """Nearest stored embeddings by pgvector cosine distance.

    distance = 1 - cosine_similarity, so ``max_distance=0.15`` means
    "cosine similarity >= 0.85" — the same threshold the ml package
    uses for near-duplicate detection. Only the top-N candidates are
    fetched from the DB and filtered here; at student-project scale
    the IVFFlat index already narrows the scan.
    """
    stmt = (
        select(
            AnalysisResult.message_id,
            AnalysisResult.embedding.cosine_distance(embedding).label("distance"),
        )
        .where(
            AnalysisResult.is_scam.is_(True),
            AnalysisResult.embedding.is_not(None),
        )
        .order_by("distance")
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    similar = []
    for row in rows:
        if row.distance is None or row.distance > max_distance:
            continue
        if exclude_message_id is not None and row.message_id == exclude_message_id:
            continue
        similar.append({"message_id": row.message_id, "distance": float(row.distance)})
    return similar


# --------------------------------------------------------------------------- #
# Entities (scam graph nodes)
# --------------------------------------------------------------------------- #
@retried()
def find_or_create_entity(db: Session, *, entity_type: str, value: str) -> Entity:
    normalized_value = normalize_entity_value(entity_type, value)
    entity = db.scalar(
        select(Entity).where(
            Entity.entity_type == entity_type, Entity.normalized_value == normalized_value
        )
    )
    if entity is None:
        entity = Entity(entity_type=entity_type, normalized_value=normalized_value)
        db.add(entity)
        db.commit()
        db.refresh(entity)
    return entity


@retried()
def link_message_entity(db: Session, *, message_id: int, entity_id: int) -> None:
    stmt = insert(MessageEntity).values(message_id=message_id, entity_id=entity_id)
    stmt = stmt.on_conflict_do_nothing(
        constraint="message_entities_pkey"
    )  # composite PK = (message_id, entity_id)
    db.execute(stmt)
    db.commit()


@retried()
def increment_report_count(db: Session, *, entity_id: int) -> int:
    """Bump the lifetime report counter; returns the new count."""
    result = db.execute(
        update(Entity)
        .where(Entity.id == entity_id)
        .values(report_count=Entity.report_count + 1)
        .returning(Entity.report_count)
    )
    db.commit()
    return int(result.scalar_one())


@retried()
def get_recent_report_count(
    db: Session,
    *,
    entity_id: int,
    window_minutes: int,
    exclude_message_id: int | None = None,
    now: datetime | None = None,
) -> int:
    """Reports mentioning this entity within the trailing time window.

    ``exclude_message_id`` lets the caller ask "how many reports
    existed BEFORE the current one" — which is what the API returns
    as ``prior_reports`` and what the alert rule is evaluated
    against (current report = prior + 1).
    """
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(minutes=window_minutes)
    stmt = (
        select(func.count(MessageEntity.message_id))
        .join(Message, MessageEntity.message_id == Message.id)
        .where(
            MessageEntity.entity_id == entity_id,
            Message.created_at >= cutoff,
        )
    )
    if exclude_message_id is not None:
        stmt = stmt.where(Message.id != exclude_message_id)
    return int(db.scalar(stmt) or 0)


@retried()
def get_entity_history(
    db: Session, *, entity_id: int, limit: int = 20
) -> list[dict]:
    """The most recent reports mentioning an entity (for the
    "search before you pay" endpoint)."""
    stmt = (
        select(Message, AnalysisResult)
        .join(MessageEntity, MessageEntity.message_id == Message.id)
        .outerjoin(AnalysisResult, AnalysisResult.message_id == Message.id)
        .where(MessageEntity.entity_id == entity_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "message_id": message.id,
            "source": message.source,
            "scam_type": analysis.scam_type if analysis else None,
            "confidence": analysis.confidence if analysis else None,
            "is_scam": analysis.is_scam if analysis else None,
            "created_at": message.created_at,
        }
        for message, analysis in rows
    ]


@retried()
def find_entity_by_value(
    db: Session, *, value: str, entity_type: str | None = None
) -> Entity | None:
    """Look up an entity by its normalised value alone (the API
    surface exposes value-only search; the unique constraint is
    (type, value), so this takes the first match)."""
    if entity_type:
        normalized = normalize_entity_value(entity_type, value)
        stmt = select(Entity).where(
            Entity.entity_type == entity_type,
            Entity.normalized_value == normalized,
        )
        return db.scalar(stmt)

    candidates: list[tuple[str, str]] = []
    for candidate_type in ("upi", "phone", "url"):
        try:
            candidates.append((candidate_type, normalize_entity_value(candidate_type, value)))
        except ValueError:
            continue
    if not candidates:
        return None
    return db.scalar(
        select(Entity).where(
            or_(
                *(
                    (Entity.entity_type == candidate_type)
                    & (Entity.normalized_value == normalized)
                    for candidate_type, normalized in candidates
                )
            )
        )
    )
