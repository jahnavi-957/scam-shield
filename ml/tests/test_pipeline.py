"""Integration tests: realistic messages through the FULL pipeline.

Uses the rule-based classifier + stub embedder (dependency injection)
so these run offline and deterministically. The output shape is
identical to production (which swaps in DistilBERT + MiniLM).
"""

from __future__ import annotations

import pytest

from scamshield_ml.pipeline import analyze_message


def test_scam_verdict_shape_and_content(rule_classifier, stub_embedder):
    verdict = analyze_message(
        "Congratulations! You've won Rs. 50,000 in the lucky draw. "
        "Pay a Rs. 500 processing fee to fraud123@okaxis or visit "
        "bit.ly/claim-prize to claim now.",
        classifier=rule_classifier,
        embedder=stub_embedder,
    )
    # shape
    assert verdict.is_scam is True
    assert verdict.scam_type == "fake_prize"
    assert 0.0 <= verdict.confidence <= 1.0
    assert isinstance(verdict.entities_found, dict)
    assert isinstance(verdict.embedding, list)
    assert len(verdict.embedding) == stub_embedder.dim
    assert all(isinstance(x, float) for x in verdict.embedding)
    assert verdict.explanation  # human-readable, non-empty
    assert verdict.classifier_kind == "rule-based-fallback"
    # correctness
    assert verdict.entities_found["upi_ids"] == ["fraud123@okaxis"]
    assert verdict.entities_found["urls"] == ["bit.ly/claim-prize"]
    assert verdict.entities_found["counts"]["amounts"] == 2
    # explanation mentions the key facts
    assert "fake_prize" in verdict.explanation
    assert "fraud123@okaxis" in verdict.explanation


@pytest.mark.parametrize(
    "message,expected_label",
    [
        (
            "URGENT: Your SBI account will be suspended. Verify your KYC "
            "immediately at sbi-secure-kyc.com",
            "phishing",
        ),
        (
            "Mummy, I need Rs. 20,000 urgently. My phone is charging, "
            "send money to 9876543210. This is my new number.",
            "impersonation",
        ),
        (
            "Instant loan approved! Get Rs. 5,00,000 instantly. "
            "Pay 2% processing fee to loanapp@okaxis.",
            "loan_scam",
        ),
        (
            "Double your money in 30 days! Invest Rs. 10,000 and get "
            "guaranteed returns. Join our WhatsApp group: bit.ly/trade-profit-in",
            "investment_fraud",
        ),
    ],
)
def test_all_scam_types_through_pipeline(rule_classifier, stub_embedder, message, expected_label):
    verdict = analyze_message(message, classifier=rule_classifier, embedder=stub_embedder)
    assert verdict.is_scam is True
    assert verdict.scam_type == expected_label
    assert verdict.explanation


@pytest.mark.parametrize(
    "message",
    [
        "Your OTP for SBI netbanking is 452318. Do not share with anyone.",
        "Meeting postponed to 4 PM tomorrow. Please join the usual Google Meet link.",
        "Can you send the report by EOD? Thanks for your help.",
        "Train 12045 Delhi-Chandigarh delayed by 20 minutes. Check irctc.co.in for updates.",
    ],
)
def test_legitimate_messages_are_not_scam(rule_classifier, stub_embedder, message):
    verdict = analyze_message(message, classifier=rule_classifier, embedder=stub_embedder)
    assert verdict.is_scam is False
    assert verdict.scam_type == "not_scam"
    assert "legitimate" in verdict.explanation


def test_near_duplicate_flag(rule_classifier, stub_embedder):
    """A known scam vector is supplied by the 'backend' -> flagged."""
    known = [stub_embedder.embed("you have won a prize, claim now")]
    verdict = analyze_message(
        "Congratulations! You've won a prize. Claim now.",
        classifier=rule_classifier,
        embedder=stub_embedder,
        known_embeddings=known,
        known_ids=["scam-001"],
    )
    assert verdict.near_duplicate is True
    assert verdict.matched_scam_id == "scam-001"
    assert verdict.similarity_score == pytest.approx(1.0)
    assert "scam-001" in verdict.explanation


def test_not_flagged_when_no_known_scams_match(rule_classifier, stub_embedder):
    unrelated = [stub_embedder.embed("hello friend, how are you?")]
    verdict = analyze_message(
        "Congratulations! You've won a prize. Claim now.",
        classifier=rule_classifier,
        embedder=stub_embedder,
        known_embeddings=unrelated,
        known_ids=["scam-999"],
    )
    assert verdict.near_duplicate is False
    assert verdict.matched_scam_id is None


def test_empty_message_handled_gracefully(rule_classifier, stub_embedder):
    verdict = analyze_message("", classifier=rule_classifier, embedder=stub_embedder)
    assert verdict.is_scam is False
    assert verdict.scam_type == "not_scam"
    assert verdict.entities_found["total_entities"] == 0
    assert len(verdict.embedding) == stub_embedder.dim
    assert verdict.explanation


def test_verdict_is_json_serialisable(rule_classifier, stub_embedder):
    import json

    verdict = analyze_message(
        "Pay Rs. 500 to fraud123@okaxis to claim your prize.",
        classifier=rule_classifier,
        embedder=stub_embedder,
    )
    payload = json.loads(verdict.model_dump_json())
    assert payload["is_scam"] is True
    assert payload["scam_type"] == "fake_prize"
    assert isinstance(payload["embedding"][0], float)
