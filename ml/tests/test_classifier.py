"""Unit tests for the classifier (rule-based fallback always runs;
the DistilBERT tests are skipped until a fine-tuned model exists)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scamshield_ml.classifier import (
    DEFAULT_MODEL_DIR,
    RuleBasedClassifier,
    TransformersClassifier,
    classify,
    get_classifier,
)
from scamshield_ml.labels import ALL_LABELS, NOT_SCAM


def _assert_valid_result(result: dict) -> None:
    assert result["label"] in ALL_LABELS
    assert 0.0 <= result["confidence"] <= 1.0
    assert set(result["all_scores"]) == set(ALL_LABELS)
    assert abs(sum(result["all_scores"].values()) - 1.0) < 1e-6


def test_prize_message_classified_as_fake_prize(rule_classifier):
    result = rule_classifier.classify(
        "Congratulations! You've won Rs. 50,000 in the lucky draw. "
        "Pay Rs. 500 to claim now at bit.ly/claim-prize"
    )
    _assert_valid_result(result)
    assert result["label"] == "fake_prize"
    assert result["confidence"] > 0.5


def test_phishing_message(rule_classifier):
    result = rule_classifier.classify(
        "URGENT: Your SBI account will be suspended. Verify your KYC "
        "immediately at sbi-secure-kyc.com"
    )
    _assert_valid_result(result)
    assert result["label"] == "phishing"


def test_impersonation_message(rule_classifier):
    result = rule_classifier.classify(
        "Mummy, I need Rs. 20,000 urgently. My phone is charging, "
        "send money to 9876543210."
    )
    _assert_valid_result(result)
    assert result["label"] == "impersonation"


def test_loan_message(rule_classifier):
    result = rule_classifier.classify(
        "Instant loan approved! Get Rs. 5,00,000 instantly. "
        "Pay 2% processing fee to loanapp@okaxis."
    )
    _assert_valid_result(result)
    assert result["label"] == "loan_scam"


def test_investment_message(rule_classifier):
    result = rule_classifier.classify(
        "Double your money in 30 days! Invest Rs. 10,000, "
        "guaranteed returns. Join our WhatsApp group."
    )
    _assert_valid_result(result)
    assert result["label"] == "investment_fraud"


@pytest.mark.parametrize(
    "text",
    [
        "Your OTP for SBI netbanking is 452318. Do not share with anyone.",
        "Meeting postponed to 4 PM tomorrow. Please join the usual Google Meet link.",
        "Can you send the report by EOD? Thanks for your help.",
    ],
)
def test_legitimate_messages_are_not_scam(rule_classifier, text):
    result = rule_classifier.classify(text)
    _assert_valid_result(result)
    assert result["label"] == NOT_SCAM


def test_empty_input(rule_classifier):
    result = rule_classifier.classify("")
    _assert_valid_result(result)
    assert result["label"] == NOT_SCAM
    assert result["empty"] is True


def test_batch_consistency(rule_classifier):
    texts = ["you won a prize!", "hello there, how are you?"]
    single = [rule_classifier.classify(t) for t in texts]
    batch = rule_classifier.classify_batch(texts)
    assert [s["label"] for s in single] == [b["label"] for b in batch]


def test_get_classifier_singleton():
    first = get_classifier()
    second = get_classifier()
    assert first is second  # loaded once, reused


def test_module_level_classify():
    result = classify("Congratulations! You won a lottery. Pay Rs. 100 to claim.")
    _assert_valid_result(result)
    assert result["label"] == "fake_prize"


# --------------------------------------------------------------------------- #
# Fine-tuned model tests (skipped until a model has been trained)
# --------------------------------------------------------------------------- #
MODEL_DIR = Path(__file__).resolve().parents[1] / "model"
has_model = (MODEL_DIR / "config.json").exists()


@pytest.mark.skipif(not has_model, reason="fine-tuned model not trained yet — run ml/train_classifier.py")
class TestTransformersClassifier:
    def test_loads_and_classifies(self):
        classifier = TransformersClassifier(MODEL_DIR)
        result = classifier.classify("Congratulations! You've won a prize. Pay Rs. 500 to claim.")
        _assert_valid_result(result)
        assert result["empty"] is False
        assert result["truncated"] is False

    def test_empty_input(self):
        classifier = TransformersClassifier(MODEL_DIR)
        result = classifier.classify("")
        assert result["label"] == NOT_SCAM
        assert result["confidence"] == 0.0
        assert result["empty"] is True

    def test_long_input_truncated_gracefully(self):
        classifier = TransformersClassifier(MODEL_DIR, max_length=64)
        result = classifier.classify("word " * 500)
        assert result["truncated"] is True
        _assert_valid_result(result)

    def test_batch(self):
        classifier = TransformersClassifier(MODEL_DIR)
        results = classifier.classify_batch(["you won a prize", "hello friend"])
        assert len(results) == 2
        assert all(r["label"] in ALL_LABELS for r in results)
