"""Sentence embeddings + near-duplicate matching.

Wraps the pretrained `sentence-transformers/all-MiniLM-L6-v2` model and
provides cosine-similarity matching against a list of stored vectors.

DESIGN DECISION — this module NEVER touches the database. It takes
vectors in and returns vectors/scores out; the backend layer owns
persistence (RDS/pgvector). That keeps the ML package standalone and
testable.

DEFAULT THRESHOLD (0.85) — how it was chosen:
With all-MiniLM-L6-v2, rewordings/paraphrases of the SAME scam message
typically score cosine 0.80-0.95, while genuinely different scam
messages usually score below ~0.75 (and unrelated messages ~0.2-0.5).
0.85 sits inside that gap and deliberately favours PRECISION: it is
better to miss a clever reword than to flag a legitimate message as a
known scam. Tune it on your own labelled near-duplicate pairs — every
function accepts a `threshold` argument.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # fixed output length of all-MiniLM-L6-v2
DEFAULT_SIMILARITY_THRESHOLD = 0.85

# Loaded once (lazily) and reused — model load is ~90 MB, so we never
# pay it per request.
_model = None


def _load_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: Sequence[str], batch_size: int = 32, normalize: bool = True) -> np.ndarray:
    """Embed a batch of texts into fixed-length vectors (n, 384).

    `normalize=True` unit-normalises rows so cosine similarity becomes a
    plain dot product (faster, and identical results).
    """
    model = _load_model()
    vectors = model.encode(list(texts), batch_size=batch_size, convert_to_numpy=True, show_progress_bar=False)
    if normalize:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / np.maximum(norms, 1e-12)
    return vectors


def embed(text: str) -> np.ndarray:
    """Embed a single text into a fixed-length (384,) unit vector."""
    return embed_texts([text])[0]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity in [-1, 1]; 1.0 = identical direction."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def similarity_scores(
    query_embedding: np.ndarray,
    stored_embeddings: Sequence[np.ndarray],
) -> np.ndarray:
    """Cosine similarity of the query against every stored vector."""
    if len(stored_embeddings) == 0:
        return np.array([])
    stacked = np.vstack([np.asarray(e, dtype=np.float64) for e in stored_embeddings])
    norms = np.linalg.norm(stacked, axis=1) * np.linalg.norm(query_embedding)
    # Guard against zero vectors (empty input produced them).
    safe = np.where(norms == 0, 1.0, norms)
    return np.clip(np.dot(stacked, query_embedding) / safe, -1.0, 1.0)


def find_best_match(
    query_embedding: np.ndarray,
    stored_embeddings: Sequence[np.ndarray],
    stored_ids: Sequence[str] | None = None,
) -> dict | None:
    """Best cosine-similarity match for the query among stored vectors.

    Returns {"match_id": str|int, "score": float} or None when there is
    nothing to compare against. `match_id` uses stored_ids[i] when
    provided, else the index i.
    """
    scores = similarity_scores(query_embedding, stored_embeddings)
    if scores.size == 0:
        return None
    idx = int(np.argmax(scores))
    match_id = stored_ids[idx] if stored_ids is not None else idx
    return {"match_id": match_id, "score": float(scores[idx])}


def is_near_duplicate(
    query_embedding: np.ndarray,
    stored_embeddings: Sequence[np.ndarray],
    stored_ids: Sequence[str] | None = None,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> dict:
    """Decide "is this a near-duplicate of a known scam?".

    Returns {"is_near_duplicate": bool, "match_id": str|int|None,
    "score": float|None}. Empty stored_embeddings always yields False.
    """
    best = find_best_match(query_embedding, stored_embeddings, stored_ids)
    if best is None:
        return {"is_near_duplicate": False, "match_id": None, "score": None}
    is_dup = best["score"] >= threshold
    return {
        "is_near_duplicate": bool(is_dup),
        "match_id": best["match_id"] if is_dup else None,
        "score": best["score"],
    }
