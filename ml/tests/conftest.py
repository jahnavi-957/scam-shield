"""Shared fixtures for the Scam Shield test suite."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest

# Make `scamshield_ml` importable when running pytest from the repo root.
ML_DIR = Path(__file__).resolve().parents[1]
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from scamshield_ml.classifier import RuleBasedClassifier  # noqa: E402


class StubEmbedder:
    """Deterministic 8-dim embedder for offline pipeline tests.

    Routes texts by keyword so near-duplicate behaviour is
    reproducible without downloading a real model:
      * contains "prize"/"won"  -> vector A
      * contains "hello"/"hi"   -> vector B
      * anything else           -> hash-derived vector
    """

    kind = "stub"
    dim = 8

    def embed(self, text: str) -> np.ndarray:
        lowered = (text or "").lower()
        if "prize" in lowered or "won" in lowered:
            vec = np.zeros(self.dim, dtype=np.float32)
            vec[0] = 1.0
            return vec
        if "hello" in lowered or "hi " in lowered or lowered.startswith("hi"):
            vec = np.zeros(self.dim, dtype=np.float32)
            vec[1] = 1.0
            return vec
        digest = hashlib.md5(lowered.encode()).digest()
        vec = np.frombuffer(digest, dtype=np.uint8).astype(np.float32)[: self.dim]
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-9)


@pytest.fixture
def rule_classifier() -> RuleBasedClassifier:
    return RuleBasedClassifier()


@pytest.fixture
def stub_embedder() -> StubEmbedder:
    return StubEmbedder()


PRIZE_MESSAGE = (
    "Congratulations! You've won Rs. 50,000 in the lucky draw. "
    "Pay a Rs. 500 processing fee to fraud123@okaxis or visit "
    "bit.ly/claim-prize to claim now."
)
PHISHING_MESSAGE = (
    "URGENT: Your SBI account will be suspended. Verify your KYC "
    "immediately at sbi-secure-kyc.com or your account will be blocked."
)
IMPERSONATION_MESSAGE = (
    "Mummy, I need Rs. 20,000 urgently. My phone is charging, "
    "send money to 9876543210. This is my new number."
)
LOAN_MESSAGE = (
    "Instant loan approved! Get Rs. 5,00,000 instantly. Pay 2% "
    "processing fee to loanapp@okaxis. No CIBIL check required."
)
INVESTMENT_MESSAGE = (
    "Double your money in 30 days! Invest Rs. 10,000 and get "
    "guaranteed returns. Join our WhatsApp group: bit.ly/trade-profit-in"
)
LEGIT_MESSAGES = [
    "Your OTP for SBI netbanking is 452318. Do not share with anyone.",
    "Meeting postponed to 4 PM tomorrow. Please join the usual Google Meet link.",
    "Can you send the report by EOD? Thanks for your help.",
    "Train 12045 Delhi-Chandigarh delayed by 20 minutes. Check irctc.co.in for updates.",
]
