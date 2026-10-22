"""Focused unit tests for backend validation, privacy and abuse controls."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from app.core.config import ConfigurationError, Settings, load_secrets_from_ssm
from app.schemas.analysis import PresignedUploadRequest
from app.security import InMemoryRateLimiter
from app.services import alerts, analysis as analysis_service
from app.services.entities import normalize_entity_value
from app.services.privacy import redact_sensitive_text
from app.services.storage import ImageTooLargeError, ImageValidationError, validate_image
from app.main import app


def _png(size: tuple[int, int] = (32, 16)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, "red").save(output, format="PNG")
    return output.getvalue()


def test_presign_query_model_rejects_unsupported_content_and_long_expiry():
    with pytest.raises(ValidationError):
        PresignedUploadRequest(content_type="image/gif")
    with pytest.raises(ValidationError):
        PresignedUploadRequest(expires_in=301)
    assert PresignedUploadRequest(expires_in=300).expires_in == 300


def test_http_errors_have_security_headers_and_typed_validation_body():
    response = TestClient(app).get(
        "/uploads/presigned-url",
        params={"content_type": "image/gif"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_pillow_validation_checks_content_size_and_dimensions():
    assert validate_image(_png()) == ("PNG", 32, 16)

    with pytest.raises(ImageValidationError):
        validate_image(b"PNG-looking-but-not-a-real-image")
    with pytest.raises(ImageTooLargeError):
        validate_image(_png(), SimpleNamespace(max_image_bytes=10))
    with pytest.raises(ImageValidationError):
        validate_image(
            _png((100, 100)),
            SimpleNamespace(max_image_bytes=100_000, max_image_width=64, max_image_height=64),
        )


def test_redaction_happens_only_in_the_persisted_copy(monkeypatch):
    original = "Pay fraud123@okaxis or 9876543210 at https://example.com/claim"
    persisted: dict[str, str] = {}
    seen_by_ai: list[str] = []

    monkeypatch.setattr(
        analysis_service.ai,
        "analyze",
        lambda text: seen_by_ai.append(text)
        or {
            "is_scam": True,
            "scam_type": "fake_prize",
            "confidence": 0.9,
            "explanation": "Contact fraud123@okaxis",
            "embedding": [1.0],
            "entities": {"upi_ids": [], "phone_numbers": [], "urls": []},
        },
    )
    monkeypatch.setattr(
        analysis_service.repository,
        "save_message",
        lambda db, *, raw_text, source: (
            persisted.update(raw_text=raw_text) or SimpleNamespace(id=1)
        ),
    )
    monkeypatch.setattr(
        analysis_service.repository,
        "save_analysis",
        lambda *args, **kwargs: SimpleNamespace(created_at=None),
    )
    monkeypatch.setattr(analysis_service, "_find_near_duplicates", lambda *args: [])
    monkeypatch.setattr(
        analysis_service,
        "_track_entities",
        lambda *args: ([], 0, False),
    )

    result = analysis_service.analyze_text(object(), SimpleNamespace(), original)

    assert seen_by_ai == [original]
    assert persisted["raw_text"] == redact_sensitive_text(original)
    assert original not in persisted["raw_text"]
    assert result["near_duplicates"] == []


def test_phone_normalization_is_shared_by_storage_and_lookup():
    assert normalize_entity_value("phone", "(987) 654-3210") == "+919876543210"
    assert normalize_entity_value("phone", "0091 9876543210") == "+919876543210"
    assert normalize_entity_value("upi", " Fraud123@OKAXIS ") == "fraud123@okaxis"


def test_rate_limiter_enforces_window_and_can_reset():
    limiter = InMemoryRateLimiter()
    assert limiter.allow("client", limit=2, window_seconds=60, now=0) == (True, 0)
    assert limiter.allow("client", limit=2, window_seconds=60, now=1) == (True, 0)
    allowed, retry_after = limiter.allow("client", limit=2, window_seconds=60, now=2)
    assert allowed is False
    assert retry_after > 0
    assert limiter.allow("client", limit=2, window_seconds=60, now=61) == (True, 0)
    limiter.clear()
    assert limiter.allow("client", limit=2, window_seconds=60, now=2) == (True, 0)


def test_mock_sns_does_not_log_entity_value(caplog):
    config = SimpleNamespace(
        sns_mock_enabled=True,
        sns_topic_arn="",
        aws_region="us-east-1",
        alert_window_minutes=60,
    )
    alerts.init_alerts(config)
    with caplog.at_level("DEBUG"):
        assert alerts.publish_alert("secret@bank", "upi", 5) is True
    assert "secret@bank" not in caplog.text
    assert "secret@bank" in alerts.get_mock_messages()[0]["Message"]


def test_production_ssm_failure_does_not_fall_back_to_environment(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("S3_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("S3_PUBLIC_ENDPOINT_URL", raising=False)
    settings = Settings(
        environment="prod",
        ssm_enabled=True,
        cors_origins="https://frontend.example",
        aws_access_key_id="",
        aws_secret_access_key="",
        s3_endpoint_url="",
        s3_public_endpoint_url="",
    )

    class BrokenSSM:
        def get_parameters(self, **kwargs):
            raise RuntimeError("unavailable")

    monkeypatch.setattr("app.core.config.boto3.client", lambda *args, **kwargs: BrokenSSM())
    with pytest.raises(ConfigurationError):
        load_secrets_from_ssm(settings)
