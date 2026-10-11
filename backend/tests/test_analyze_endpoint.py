"""Integration tests for POST /analyze/text.

The AI pipeline is mocked (see conftest.py) — the real
DistilBERT/MiniLM models are far too slow to load in a
test suite. These tests cover the endpoint contract,
persistence, entity report counting and the alert rule
end-to-end.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.ai import AIPipelineError
from app.db.models import Message
from app.services import alerts

pytestmark = pytest.mark.integration

SCAM_TEXT = "Congratulations! Pay Rs. 500 to fraud123@okaxis to claim your prize."


def test_analyze_text_returns_verdict_and_persists(
    client: TestClient, db_session
):
    response = client.post("/analyze/text", json={"text": SCAM_TEXT})
    assert response.status_code == 200
    body = response.json()

    assert body["is_scam"] is True
    assert body["scam_type"] == "fake_prize"
    assert body["confidence"] == 0.9
    assert body["source"] == "text"
    assert body["prior_reports"] == 0
    assert body["alert_triggered"] is False  # 1st report < threshold (5)
    assert body["near_duplicates"] == []  # no prior reports yet

    entity = body["entities"][0]
    assert entity["type"] == "upi"
    assert entity["value"] == "fraud123@okaxis"
    assert entity["report_count"] == 1

    # Persisted: the message row exists with the raw text.
    message = db_session.get(Message, body["message_id"])
    assert message is not None
    assert message.raw_text == SCAM_TEXT


def test_analyze_text_multiple_entities(
    client: TestClient, mock_ai
):
    text = "Congrats fraud123@okaxis! Pay 9876543210 via bit.ly/claim-prize"
    response = client.post("/analyze/text", json={"text": text})
    assert response.status_code == 200
    types = sorted(entity["type"] for entity in response.json()["entities"])
    assert types == ["phone", "upi", "url"]


def test_alert_fires_exactly_at_fifth_report(client: TestClient):
    """The alert rule fires on the 5th report within the
    window — not the 4th, not the 6th."""
    for report_number in range(1, 6):
        response = client.post("/analyze/text", json={"text": SCAM_TEXT})
        assert response.status_code == 200
        assert response.json()["alert_triggered"] is (report_number == 5)


def test_no_duplicate_alert_for_sixth_report(client: TestClient):
    """Within the same window, further reports do not
    re-alert (the last_alert_at cooldown)."""
    for _ in range(6):
        response = client.post("/analyze/text", json={"text": SCAM_TEXT})
    assert response.json()["alert_triggered"] is False
    assert response.json()["prior_reports"] == 5


def test_prior_reports_increments_per_report(client: TestClient):
    first = client.post("/analyze/text", json={"text": SCAM_TEXT}).json()
    second = client.post("/analyze/text", json={"text": SCAM_TEXT}).json()
    assert first["prior_reports"] == 0
    assert second["prior_reports"] == 1


def test_sns_failure_does_not_block_the_response(client: TestClient, monkeypatch):
    """If SNS is down, the verdict still returns — the
    alert is logged, not the user's problem."""
    monkeypatch.setattr(alerts, "_topic_arn", "arn:aws:sns:us-east-1:123456789012:scam-shield")

    class ExplodingSNS:
        def publish(self, **kwargs):
            raise RuntimeError("SNS is down")

    monkeypatch.setattr(alerts, "_sns", ExplodingSNS())

    for _ in range(5):
        response = client.post("/analyze/text", json={"text": SCAM_TEXT})
    assert response.status_code == 200
    assert response.json()["alert_triggered"] is True


def test_analyze_text_rejects_empty_text(client: TestClient):
    response = client.post("/analyze/text", json={"text": ""})
    assert response.status_code == 422


def test_analyze_text_rejects_oversized_text(client: TestClient):
    response = client.post("/analyze/text", json={"text": "a" * 10_001})
    assert response.status_code == 422


def test_ai_failure_returns_generic_500(client: TestClient, monkeypatch):
    """A model failure becomes a clean 500 with a generic
    message — the real error is logged server-side."""

    def boom(text: str):
        raise AIPipelineError("model exploded")

    monkeypatch.setattr("app.services.analysis.ai.analyze", boom)
    response = client.post("/analyze/text", json={"text": "anything at all"})
    assert response.status_code == 500
    assert response.json()["detail"] == "Analysis failed. Please try again later."


def test_entity_history_endpoint(client: TestClient):
    for _ in range(2):
        client.post("/analyze/text", json={"text": SCAM_TEXT})

    response = client.get("/entities/fraud123@okaxis")
    assert response.status_code == 200
    body = response.json()
    assert body["entity_type"] == "upi"
    assert body["report_count"] == 2
    assert len(body["recent_reports"]) == 2


def test_entity_history_unknown_entity_returns_404(client: TestClient):
    response = client.get("/entities/never-seen@okaxis")
    assert response.status_code == 404


def test_presigned_url_requires_configured_bucket(client: TestClient):
    """Without an S3 bucket (local dev default), the endpoint
    explains that storage is not configured."""
    response = client.get("/uploads/presigned-url")
    assert response.status_code == 503


def test_presigned_url_rejects_bad_content_type(client: TestClient):
    """Only screenshot content types get presigned URLs."""
    response = client.get(
        "/uploads/presigned-url", params={"content_type": "application/pdf"}
    )
    assert response.status_code == 422
