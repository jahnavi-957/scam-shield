"""Repository integration tests (compose Postgres required).

Covers the data layer: save/find, entity idempotence,
report counting within the alert window, and pgvector
similarity search.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.db import repository
from app.db.models import AnalysisResult, Entity, Message

pytestmark = pytest.mark.integration

NOW = datetime.now(timezone.utc)


def _embedding(first: float) -> list[float]:
    return [first] + [0.0] * 383


def test_save_message_and_analysis(db_session):
    message = repository.save_message(db_session, raw_text="hello", source="text")
    analysis = repository.save_analysis(
        db_session,
        message_id=message.id,
        scam_type="fake_prize",
        confidence=0.9,
        is_scam=True,
        explanation="stub",
        embedding=_embedding(1.0),
    )
    assert analysis.message_id == message.id
    reloaded = db_session.get(AnalysisResult, analysis.id)
    assert reloaded.scam_type == "fake_prize"
    assert reloaded.embedding is not None


def test_find_or_create_entity_is_idempotent(db_session):
    first = repository.find_or_create_entity(db_session, entity_type="upi", value="fraud123@okaxis")
    second = repository.find_or_create_entity(db_session, entity_type="upi", value="fraud123@okaxis")
    assert first.id == second.id
    assert first.report_count == 0


def test_increment_report_count(db_session):
    entity = repository.find_or_create_entity(db_session, entity_type="phone", value="+919876543210")
    assert repository.increment_report_count(db_session, entity_id=entity.id) == 1
    assert repository.increment_report_count(db_session, entity_id=entity.id) == 2


def test_get_recent_report_count_respects_window(db_session):
    entity = repository.find_or_create_entity(db_session, entity_type="url", value="bit.ly/x")

    # A report from 30 days ago is OUTSIDE the 24h window.
    old = repository.save_message(db_session, raw_text="old", source="text")
    db_session.execute(
        update(Message)
        .where(Message.id == old.id)
        .values(created_at=NOW - timedelta(days=30))
    )
    db_session.commit()
    repository.link_message_entity(db_session, message_id=old.id, entity_id=entity.id)

    # A report from now is INSIDE the window.
    new = repository.save_message(db_session, raw_text="new", source="text")
    repository.link_message_entity(db_session, message_id=new.id, entity_id=entity.id)

    assert repository.get_recent_report_count(
        db_session, entity_id=entity.id, window_minutes=1440
    ) == 1
    # Excluding the current message -> the "prior reports" count.
    assert repository.get_recent_report_count(
        db_session,
        entity_id=entity.id,
        window_minutes=1440,
        exclude_message_id=new.id,
    ) == 0


def test_find_similar_analyses_by_cosine_distance(db_session):
    message = repository.save_message(db_session, raw_text="a", source="text")
    repository.save_analysis(
        db_session,
        message_id=message.id,
        scam_type="fake_prize",
        confidence=0.9,
        is_scam=True,
        explanation="stub",
        embedding=_embedding(1.0),
    )

    # Nearly identical embedding -> cosine distance ~0.
    similar = repository.find_similar_analyses(
        db_session, embedding=_embedding(0.99), max_distance=0.15, exclude_message_id=message.id
    )
    assert [hit["message_id"] for hit in similar] == [message.id]

    # Orthogonal embedding -> cosine distance ~1.4, not similar.
    dissimilar = repository.find_similar_analyses(
        db_session, embedding=_embedding(0.0), max_distance=0.15, exclude_message_id=message.id
    )
    assert dissimilar == []


def test_entity_history(db_session):
    entity = repository.find_or_create_entity(db_session, entity_type="upi", value="fraud123@okaxis")
    for i in range(3):
        message = repository.save_message(db_session, raw_text=f"msg {i}", source="text")
        repository.link_message_entity(db_session, message_id=message.id, entity_id=entity.id)
        repository.increment_report_count(db_session, entity_id=entity.id)

    history = repository.get_entity_history(db_session, entity_id=entity.id)
    assert len(history) == 3
    assert history[0]["message_id"] > history[-1]["message_id"]  # newest first
