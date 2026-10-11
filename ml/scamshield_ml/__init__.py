"""Scam Shield ML package.

Standalone NLP + deep-learning module for scam detection. Importable
without FastAPI, AWS SDKs, or a database:

    from scamshield_ml import analyze_message, extract_entities, classify

Layers:
    labels.py      — label taxonomy (single source of truth)
    extraction.py  — regex entity extraction (UPI IDs, phones, URLs, amounts)
    classifier.py  — fine-tuned DistilBERT + rule-based fallback
    embeddings.py  — sentence-transformer embeddings + cosine matching
    pipeline.py    — analyze_message() -> ScamVerdict (the backend's entry point)
"""

from .classifier import (
    ClassifierProtocol,
    RuleBasedClassifier,
    TransformersClassifier,
    classify,
    get_classifier,
)
from .embeddings import (
    DEFAULT_SIMILARITY_THRESHOLD,
    cosine_similarity,
    embed,
    embed_texts,
    find_best_match,
    is_near_duplicate,
)
from .extraction import (
    extract_amounts,
    extract_entities,
    extract_phone_numbers,
    extract_upi_ids,
    extract_urls,
    is_likely_upi_id,
)
from .labels import ALL_LABELS, LABEL_DESCRIPTIONS, NOT_SCAM, PRECEDENCE, SCAM_LABELS, is_scam_label
from .pipeline import ScamVerdict, analyze_message

__version__ = "0.1.0"

__all__ = [
    # labels
    "ALL_LABELS",
    "SCAM_LABELS",
    "NOT_SCAM",
    "PRECEDENCE",
    "LABEL_DESCRIPTIONS",
    "is_scam_label",
    # extraction
    "extract_entities",
    "extract_upi_ids",
    "extract_phone_numbers",
    "extract_urls",
    "extract_amounts",
    "is_likely_upi_id",
    # classifier
    "classify",
    "get_classifier",
    "RuleBasedClassifier",
    "TransformersClassifier",
    "ClassifierProtocol",
    # embeddings
    "embed",
    "embed_texts",
    "cosine_similarity",
    "find_best_match",
    "is_near_duplicate",
    "DEFAULT_SIMILARITY_THRESHOLD",
    # pipeline
    "analyze_message",
    "ScamVerdict",
]
