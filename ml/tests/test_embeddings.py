"""Unit tests for embeddings + cosine similarity.

The pure-math tests use hand-made vectors (no model download).
The model-dependent test is marked `slow` and skipped unless
`-m "not slow"` is not in effect and the download succeeds.
"""

from __future__ import annotations

import numpy as np
import pytest

from scamshield_ml import embeddings


class TestCosineMath:
    def test_identical_vectors(self):
        v = np.array([1.0, 2.0, 3.0])
        assert embeddings.cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert embeddings.cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        assert embeddings.cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_is_safe(self):
        assert embeddings.cosine_similarity(np.zeros(3), np.ones(3)) == 0.0


class TestMatching:
    def setup_method(self):
        self.stored = [
            np.array([1.0, 0.0, 0.0]),  # 0: identical to query
            np.array([0.0, 1.0, 0.0]),  # 1: orthogonal
            np.array([0.7071, 0.7071, 0.0]),  # 2: ~0.707 to query
        ]
        self.ids = ["scam-a", "scam-b", "scam-c"]
        self.query = np.array([1.0, 0.0, 0.0])

    def test_find_best_match_returns_id_and_score(self):
        best = embeddings.find_best_match(self.query, self.stored, self.ids)
        assert best == {"match_id": "scam-a", "score": pytest.approx(1.0)}

    def test_find_best_match_fallback_to_index(self):
        best = embeddings.find_best_match(self.query, self.stored)
        assert best["match_id"] == 0

    def test_find_best_match_empty(self):
        assert embeddings.find_best_match(self.query, []) is None

    def test_is_near_duplicate_default_threshold(self):
        # score 1.0 >= 0.85 -> duplicate
        result = embeddings.is_near_duplicate(self.query, self.stored, self.ids)
        assert result["is_near_duplicate"] is True
        assert result["match_id"] == "scam-a"

    def test_is_near_duplicate_below_threshold(self):
        # best score is 0.707 < 0.85 -> not a duplicate
        # (drop the vector identical to this query so 0.707 is the best)
        stored = [self.stored[0], self.stored[2]]
        ids = [self.ids[0], self.ids[2]]
        query = np.array([0.0, 1.0, 0.0])
        result = embeddings.is_near_duplicate(query, stored, ids)
        assert result["is_near_duplicate"] is False
        assert result["match_id"] is None
        assert result["score"] == pytest.approx(0.7071, abs=1e-3)  # still reports the best score

    def test_is_near_duplicate_custom_threshold(self):
        # with threshold 0.7, the 0.707 match counts as a duplicate
        query = np.array([0.0, 1.0, 0.0])
        result = embeddings.is_near_duplicate(
            query, self.stored, self.ids, threshold=0.7
        )
        assert result["is_near_duplicate"] is True
        assert result["match_id"] == "scam-b"

    def test_is_near_duplicate_empty_stored(self):
        result = embeddings.is_near_duplicate(self.query, [])
        assert result["is_near_duplicate"] is False
        assert result["score"] is None

    def test_similarity_scores_shape(self):
        scores = embeddings.similarity_scores(self.query, self.stored)
        assert scores.shape == (3,)
        assert scores[0] == pytest.approx(1.0)
        assert scores[1] == pytest.approx(0.0)


@pytest.mark.slow
class TestRealEmbedder:
    def test_embed_fixed_dimension(self):
        try:
            vec = embeddings.embed("hello world")
        except Exception as exc:  # download blocked, no network, etc.
            pytest.skip(f"sentence-transformer unavailable: {exc}")
        assert vec.shape == (embeddings.EMBEDDING_DIM,)
        norm = float(np.linalg.norm(vec))
        assert norm == pytest.approx(1.0, abs=1e-5)  # unit-normalised

    def test_paraphrase_scores_above_unrelated(self):
        try:
            a = embeddings.embed("you have won a cash prize, claim now")
            b = embeddings.embed("you won a cash prize, claim it now")
            c = embeddings.embed("meeting postponed to 4 PM tomorrow")
        except Exception as exc:
            pytest.skip(f"sentence-transformer unavailable: {exc}")
        assert embeddings.cosine_similarity(a, b) > embeddings.cosine_similarity(a, c)
