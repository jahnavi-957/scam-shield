"""Unified analysis pipeline — the single entry point the backend calls.

analyze_message(text) -> ScamVerdict runs, in order:

    1. Entity extraction (regex, scamshield_ml.extraction)
    2. Scam-type classification (fine-tuned DistilBERT)
    3. Sentence embedding (all-MiniLM-L6-v2) for near-duplicate matching
       against previously reported scams (vectors passed in by the
       backend — this module never touches the database)

and bundles everything into one typed, JSON-serialisable verdict with a
template-based human-readable explanation (no LLM call needed at
inference time — deterministic and free).

Both the classifier and the embedder are injectable (dependency
injection), so tests can run offline with deterministic stubs while
production uses the real models.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence

import numpy as np
from pydantic import BaseModel, Field

from . import embeddings as embeddings_module
from . import extraction
from .classifier import ClassifierProtocol, get_classifier
from .embeddings import DEFAULT_SIMILARITY_THRESHOLD
from .labels import NOT_SCAM, is_scam_label


class EmbedderProtocol(Protocol):
    """Anything with embed(text) -> fixed-length vector."""

    def embed(self, text: str) -> np.ndarray: ...


class _DefaultEmbedder:
    """Adapts the module-level sentence-transformer embedder to the protocol."""

    kind = embeddings_module.MODEL_NAME

    def embed(self, text: str) -> np.ndarray:
        return embeddings_module.embed(text)


class ScamVerdict(BaseModel):
    """Structured result for one analysed message.

    JSON-serialisable (FastAPI can return it directly as a response
    model). `embedding` is a list[float] so it round-trips through
    JSON/REST cleanly.
    """

    is_scam: bool
    scam_type: str
    confidence: float
    entities_found: dict[str, Any]
    embedding: list[float]
    explanation: str
    # Optional extras populated when the backend supplies known scams.
    near_duplicate: bool = False
    similarity_score: float | None = None
    matched_scam_id: str | None = None
    # Diagnostics.
    truncated: bool = False
    classifier_kind: str = ""

    model_config = {"extra": "forbid"}


def _format_entities(entities: dict) -> str:
    """One-line human summary of extracted entities (max 2 samples each)."""
    parts: list[str] = []
    if entities["upi_ids"]:
        sample = ", ".join(entities["upi_ids"][:2])
        parts.append(f"{entities['counts']['upi_ids']} UPI ID(s) ({sample})")
    if entities["phone_numbers"]:
        sample = ", ".join(entities["phone_numbers"][:2])
        parts.append(f"{entities['counts']['phone_numbers']} phone number(s) ({sample})")
    if entities["urls"]:
        sample = ", ".join(entities["urls"][:2])
        parts.append(f"{entities['counts']['urls']} URL(s) ({sample})")
    if entities["amounts"]:
        sample = ", ".join(a["raw"] for a in entities["amounts"][:2])
        parts.append(f"{entities['counts']['amounts']} amount(s) ({sample})")
    return "; ".join(parts)


def _build_explanation(
    *,
    label: str,
    confidence: float,
    entity_summary: str,
    near_duplicate: bool,
    similarity_score: float | None,
    matched_id: str | None,
) -> str:
    """Template-based explanation built from classifier + extractor output."""
    if is_scam_label(label):
        head = f"Classified as {label} with {confidence:.0%} confidence."
        if entity_summary:
            ent = f" Extracted entities: {entity_summary}."
        else:
            ent = " No extractable entities (UPI ID, phone, URL, amount) found."
        dup = (
            f" This message is a near-duplicate of known scam '{matched_id}' "
            f"(cosine similarity {similarity_score:.2f})."
            if near_duplicate
            else ""
        )
        action = (
            " Recommendation: do not click links, reply, or send money; "
            "report this message in Scam Shield."
        )
        return head + ent + dup + action

    head = f"Classified as legitimate (not a scam) with {confidence:.0%} confidence."
    if entity_summary:
        ent = (
            f" Note: the message does contain {entity_summary}, "
            "but no scam pattern was detected."
        )
    else:
        ent = " No suspicious entities or scam indicators found."
    return head + ent


def analyze_message(
    text: str,
    *,
    classifier: ClassifierProtocol | None = None,
    embedder: EmbedderProtocol | None = None,
    known_embeddings: Sequence[np.ndarray] | None = None,
    known_ids: Sequence[str] | None = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> ScamVerdict:
    """Analyse one message end-to-end.

    Args:
        text: raw message text (SMS / WhatsApp / email body).
        classifier: classifier to use; defaults to the shared singleton
            (fine-tuned DistilBERT, or the rule-based fallback).
        embedder: embedder to use; defaults to all-MiniLM-L6-v2.
        known_embeddings: vectors of previously reported scams (owned by
            the backend). When given, a near-duplicate check is run.
        known_ids: identifiers parallel to known_embeddings.
        similarity_threshold: cosine threshold for the near-duplicate
            verdict (default 0.85, see embeddings.py).

    Returns:
        ScamVerdict — the single object the FastAPI backend returns.
    """
    classifier = classifier or get_classifier()
    embedder = embedder or _DefaultEmbedder()

    # 1. Entities
    entities = extraction.extract_entities(text)

    # 2. Classification
    result = classifier.classify(text)
    label = result["label"]

    # 3. Embedding (+ optional near-duplicate check)
    vector = np.asarray(embedder.embed(text), dtype=np.float64)
    near_dup, score, match_id = False, None, None
    if known_embeddings:
        dup = embeddings_module.is_near_duplicate(
            vector, known_embeddings, known_ids, threshold=similarity_threshold
        )
        near_dup = dup["is_near_duplicate"]
        score = dup["score"]
        match_id = dup["match_id"]

    entity_summary = _format_entities(entities)
    explanation = _build_explanation(
        label=label,
        confidence=result["confidence"],
        entity_summary=entity_summary,
        near_duplicate=near_dup,
        similarity_score=score,
        matched_id=match_id,
    )

    return ScamVerdict(
        is_scam=is_scam_label(label),
        scam_type=label,
        confidence=float(result["confidence"]),
        entities_found=entities,
        embedding=[float(x) for x in vector.tolist()],
        explanation=explanation,
        near_duplicate=near_dup,
        similarity_score=float(score) if score is not None else None,
        matched_scam_id=match_id,
        truncated=bool(result.get("truncated", False)),
        classifier_kind=classifier.kind,
    )


__all__ = ["ScamVerdict", "analyze_message", "EmbedderProtocol"]
