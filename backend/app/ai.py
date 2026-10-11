"""Adapter around the ml/ AI module (scamshield_ml).

Two jobs:

1. **Lazy loading** — importing scamshield_ml.pipeline pulls in
   torch/transformers/sentence-transformers (~1 GB of imports).
   The import happens on the FIRST request instead of at container
   startup, keeping startup fast on a small EC2 instance.
2. **Error isolation** — any model failure (OOM, corrupt weights,
   HF hub hiccup) is converted to ``AIPipelineError`` so the API
   can return a clean, generic 500 instead of crashing the
   request with a stack trace to the client.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_analyze_message = None


class AIPipelineError(RuntimeError):
    """The AI pipeline failed. The caller maps this to a generic
    500 — the real error is logged here, never exposed to clients."""


def analyze(text: str) -> dict:
    """Run the full ml pipeline on raw text.

    Returns a plain dict (JSON-friendly) with the verdict fields
    the API persists and returns: is_scam, scam_type, confidence,
    explanation, embedding (384 floats) and the extracted entities.
    """
    global _analyze_message
    try:
        if _analyze_message is None:
            # Heavy import, deliberately deferred to first use.
            from scamshield_ml.pipeline import analyze_message

            _analyze_message = analyze_message
        verdict = _analyze_message(text)
    except AIPipelineError:
        raise
    except Exception as exc:
        logger.error("AI pipeline call failed", exc_info=True)
        raise AIPipelineError(f"AI pipeline failed: {exc}") from exc

    return {
        "is_scam": bool(verdict.is_scam),
        "scam_type": verdict.scam_type,
        "confidence": float(verdict.confidence),
        "explanation": verdict.explanation,
        "embedding": [float(x) for x in verdict.embedding],
        "entities": verdict.entities_found,
    }
