"""Scam-type classifier: fine-tuned DistilBERT with a rule-based fallback.

`TransformersClassifier` loads the fine-tuned DistilBERT weights ONCE
(singleton via `get_classifier()`) and reuses them per request — never
per-request reloads, that would be ~500 ms of pure overhead.

If no fine-tuned weights exist on disk (fresh clone, CI, first demo),
the package falls back to `RuleBasedClassifier` — a transparent
keyword + entity-signal baseline with the EXACT same interface. This
keeps `scamshield_ml` importable and testable offline; in production
the FastAPI backend points `SCAM_MODEL_DIR` at the trained model.

`torch`/`transformers` are imported lazily inside
`TransformersClassifier.__init__` so importing this module (and the
whole package) stays cheap when only extraction is needed.
"""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path
from typing import Protocol

from .extraction import extract_entities
from .labels import ALL_LABELS, NOT_SCAM, PRECEDENCE, is_scam_label

# Directory the training script writes to; override with SCAM_MODEL_DIR.
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[1] / "model"


class ClassifierProtocol(Protocol):
    """Any object with classify/classify_batch (both concrete classes below)."""

    kind: str

    def classify(self, text: str) -> dict: ...

    def classify_batch(self, texts: list[str]) -> list[dict]: ...


# --------------------------------------------------------------------------- #
# Rule-based fallback (transparent baseline; also useful for smoke tests)
# --------------------------------------------------------------------------- #
# Each pattern is matched case-insensitively against the raw text.
_RULE_SIGNALS: dict[str, list[str]] = {
    "phishing": [
        r"\bkyc\b",
        r"\bverify\b",
        r"\bverification\b",
        r"\bcredentials?\b",
        r"\bpassword\b",
        r"\blog ?in\b",
        r"\bsuspended?\b",
        r"\bblocked\b",
        r"\bdeactivat\w*\b",
        r"\bupdate (?:your )?(?:mobile number|aadhaar|pan)\b",
        r"\bnetbanking (?:password|login|account|update)\b",
        # refund / overdue-bill lures (mirror-site phishing)
        r"\brefund\b",
        r"\boverdue\b",
        r"\bdisconnection\b",
        r"\bsim (?:will be )?(?:deactivat|block)",
    ],
    "fake_prize": [
        r"\bcongratulations?\b",
        r"\byou'?ve won\b",
        r"\byou have won\b",
        r"\bwinner\b",
        r"\bprize\b",
        r"\blottery\b",
        r"\blucky draw\b",
        r"\blucky winner\b",
        r"\bselected\b",
        r"\bclaim (?:your )?(?:prize|now|cash)\b",
        r"\bfree (?:cash|gift|voucher|iphone)\b",
        r"\bclaim (?:fee|now)\b",
        r"\byou won\b",
        r"\b(?:phone|number|mobile) won\b",
    ],
    "loan_scam": [
        r"\bloan\b",
        r"\binstant (?:loan|approval|cash)\b",
        r"\bapproved\b",
        r"\bsanctioned?\b",
        r"\bdisburs(?:al|e)\b",
        r"\bcibil\b",
        r"\bno collateral\b",
        r"\b(?:personal|business|home|emergency) loan\b",
        r"\blow interest\b",
        r"\bminimal documentation\b",
    ],
    "impersonation": [
        r"\bthis is (?:your )?(?:boss|manager|bank manager|nephew|son|daughter|mummy|mom|mum|dad|papa)\b",
        r"\bmummy\b",
        r"\bpapa\b",
        r"\bnew (?:number|mobile)\b",
        r"\bsend money\b",
        r"\bpolice\b",
        r"\bcbi\b",
        r"\barrest\b",
        r"\bfine\b",
        r"\bcyber cell\b",
        r"\bincome tax\b",
        r"\bhospital\b",
        r"\baccident\b",
        r"\bdo not tell\b",
        r"\bmy phone (?:is )?(?:dead|charging|broken)\b",
        r"\bbank fraud team\b",
        r"\b(?:lic|insurance) agent\b",
        r"\belectricity board\b",
        r"\bi am in a meeting\b",
    ],
    "investment_fraud": [
        r"\binvest(?:ment)?\b",
        r"\bdouble (?:your )?money\b",
        r"\bguaranteed (?:returns?|profit)\b",
        r"\bhigh returns?\b",
        r"\bdaily returns?\b",
        r"\bcrypto\b",
        r"\bbitcoin\b",
        r"\btrading\b",
        r"\bforex\b",
        r"\b100% (?:accurate|profit)\b",
        r"\brisk[- ]free\b",
        r"\bwork from home\b",
        r"\bjoin (?:our )?(?:whatsapp|telegram) group\b",
        r"\bear\w* .{0,20}(?:rs\.?|inr|lakh|crore)\b",
    ],
}


class RuleBasedClassifier:
    """Transparent keyword + entity-signal baseline.

    Score per class = number of matched keyword patterns (+0.5 boost when
    a payoff channel — URL / UPI ID / phone — is present). Probabilities
    come from a softmax over the raw scores, so confidence naturally
    reflects ambiguity between competing patterns.
    """

    kind = "rule-based-fallback"

    def classify(self, text: str) -> dict:
        text = (text or "").strip()
        entities = extract_entities(text)
        has_channel = bool(
            entities["urls"] or entities["upi_ids"] or entities["phone_numbers"]
        )

        scores = {}
        for label, patterns in _RULE_SIGNALS.items():
            score = sum(1.0 for p in patterns if re.search(p, text, re.IGNORECASE))
            if score > 0 and has_channel:
                score += 0.5
            scores[label] = score

        # No scam signal at all -> confidently legitimate.
        if max(scores.values()) == 0:
            return {
                "label": NOT_SCAM,
                "confidence": 1.0,
                "all_scores": {label: (1.0 if label == NOT_SCAM else 0.0) for label in ALL_LABELS},
                "empty": not text,
                "truncated": False,
            }

        # Softmax over all six labels (not_scam has score 0).
        logits = {label: scores.get(label, 0.0) for label in ALL_LABELS}
        import math

        max_logit = max(logits.values())
        exps = {label: math.exp(v - max_logit) for label, v in logits.items()}
        total = sum(exps.values())
        probs = {label: e / total for label, e in exps.items()}

        # Argmax with documented precedence on exact ties.
        best_label = None
        best_score = -1.0
        for label in PRECEDENCE:
            if scores[label] > best_score:
                best_score = scores[label]
                best_label = label

        return {
            "label": best_label,
            "confidence": float(probs[best_label]),
            "all_scores": {label: float(p) for label, p in probs.items()},
            "empty": not text,
            "truncated": False,
        }

    def classify_batch(self, texts: list[str]) -> list[dict]:
        return [self.classify(t) for t in texts]


# --------------------------------------------------------------------------- #
# Fine-tuned DistilBERT
# --------------------------------------------------------------------------- #
class TransformersClassifier:
    """Fine-tuned DistilBERT for sequence classification.

    Loads model + tokenizer once in __init__; `classify` is the
    per-request path (single message, low latency). Long inputs are
    truncated to `max_length` tokens and flagged via `truncated=True`
    rather than raising.
    """

    kind = "distilbert-finetuned"

    def __init__(self, model_path: str | Path, max_length: int = 512, batch_size: int = 32):
        import torch  # lazy import: keeps module import cheap
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self.model_path = str(model_path)
        self.max_length = max_length
        self.batch_size = batch_size

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_path)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        self.model.eval()

        id2label = getattr(self.model.config, "id2label", {})
        self.labels = [id2label.get(i, str(i)) for i in range(self.model.config.num_labels)]

    @property
    def _no_grad(self):
        return self._torch.no_grad()

    def classify(self, text: str) -> dict:
        torch = self._torch
        text = (text or "").strip()

        # Empty / whitespace-only input: nothing to classify.
        if not text:
            return {
                "label": NOT_SCAM,
                "confidence": 0.0,
                "all_scores": {},
                "empty": True,
                "truncated": False,
            }

        token_count = len(self.tokenizer.encode(text, add_special_tokens=True))
        truncated = token_count > self.max_length

        encoded = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
            return_attention_mask=True,
        )
        encoded = {k: v.to(self.device) for k, v in encoded.items()}

        with self._no_grad:
            logits = self.model(**encoded).logits[0]
        probs = torch.softmax(logits, dim=-1).cpu().tolist()
        idx = int(max(range(len(probs)), key=probs.__getitem__))

        return {
            "label": self.labels[idx],
            "confidence": float(probs[idx]),
            "all_scores": {label: float(p) for label, p in zip(self.labels, probs)},
            "empty": False,
            "truncated": truncated,
        }

    def classify_batch(self, texts: list[str], batch_size: int | None = None) -> list[dict]:
        torch = self._torch
        batch_size = batch_size or self.batch_size
        results: list[dict] = []
        for start in range(0, len(texts), batch_size):
            chunk = [(i, (t or "").strip()) for i, t in enumerate(texts[start : start + batch_size])]
            non_empty = [(i, t) for i, t in chunk if t]
            if not non_empty:
                results.extend(self.classify(t) for _, t in chunk)
                continue
            encoded = self.tokenizer(
                [t for _, t in non_empty],
                truncation=True,
                max_length=self.max_length,
                padding=True,
                return_tensors="pt",
                return_attention_mask=True,
            )
            encoded = {k: v.to(self.device) for k, v in encoded.items()}
            with self._no_grad:
                logits = self.model(**encoded).logits
            probs = torch.softmax(logits, dim=-1).cpu().tolist()
            prob_map = {i: p for (i, _), p in zip(non_empty, probs)}
            for i, t in chunk:
                if i in prob_map:
                    p = prob_map[i]
                    idx = int(max(range(len(p)), key=p.__getitem__))
                    results.append(
                        {
                            "label": self.labels[idx],
                            "confidence": float(p[idx]),
                            "all_scores": {label: float(v) for label, v in zip(self.labels, p)},
                            "empty": False,
                            "truncated": False,
                        }
                    )
                else:
                    results.append(self.classify(t))
        return results


# --------------------------------------------------------------------------- #
# Singleton access — what the FastAPI backend calls at startup
# --------------------------------------------------------------------------- #
_default_classifier: ClassifierProtocol | None = None


def get_classifier() -> ClassifierProtocol:
    """Return the shared classifier instance (loaded once).

    Uses `SCAM_MODEL_DIR` (default: ml/model) if a fine-tuned model is
    present, otherwise the rule-based fallback.
    """
    global _default_classifier
    if _default_classifier is None:
        model_dir = Path(os.environ.get("SCAM_MODEL_DIR", str(DEFAULT_MODEL_DIR)))
        if (model_dir / "config.json").exists():
            _default_classifier = TransformersClassifier(model_dir)
        else:
            warnings.warn(
                f"No fine-tuned model found at {model_dir}; using rule-based "
                "fallback. Run `python ml/prepare_dataset.py` then "
                "`python ml/train_classifier.py` to train one."
            )
            _default_classifier = RuleBasedClassifier()
    return _default_classifier


def classify(text: str) -> dict:
    """Convenience wrapper: classify one message with the shared classifier.

    Returns {"label": str, "confidence": float, "all_scores": dict,
    "empty": bool, "truncated": bool}.
    """
    return get_classifier().classify(text)


__all__ = [
    "classify",
    "get_classifier",
    "RuleBasedClassifier",
    "TransformersClassifier",
    "ClassifierProtocol",
    "is_scam_label",
]
