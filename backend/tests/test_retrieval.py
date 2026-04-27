"""Tests for the retrieval system."""
import pytest
from unittest.mock import AsyncMock, patch

from src.retrieval.ranking import rank_results


class TestRanking:
    def _make_result(self, chunk_id, doc_id, similarity, content="test content", tags=None):
        return {
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "chunk_content": content,
            "similarity": similarity,
            "document_type": "document",
            "document_metadata": {"tags": tags or []},
            "chunk_metadata": {},
        }

    def test_rank_by_similarity(self):
        results = [
            self._make_result("c1", "d1", 0.9),
            self._make_result("c2", "d2", 0.5),
            self._make_result("c3", "d3", 0.7),
        ]
        ranked = rank_results(results, "test query")
        scores = [r["score"] for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_rank_respects_top_k(self):
        results = [self._make_result(f"c{i}", f"d{i}", i * 0.1) for i in range(20)]
        ranked = rank_results(results, "test", top_k=5)
        assert len(ranked) <= 5

    def test_rank_boosts_tag_match(self):
        result_with_tag = self._make_result("c1", "d1", 0.8, tags=["auth"])
        result_no_tag = self._make_result("c2", "d2", 0.8)
        ranked = rank_results(
            [result_with_tag, result_no_tag],
            "auth query",
            filters={"tags": ["auth"]},
        )
        assert ranked[0]["chunk_id"] == "c1"

    def test_rank_empty_results(self):
        assert rank_results([], "query") == []

    def test_rank_adds_score_field(self):
        results = [self._make_result("c1", "d1", 0.7)]
        ranked = rank_results(results, "query")
        assert "score" in ranked[0]

    def test_term_boost_for_matching_content(self):
        result_match = self._make_result("c1", "d1", 0.5, content="auth token login")
        result_no_match = self._make_result("c2", "d2", 0.5, content="irrelevant stuff")
        ranked = rank_results([result_match, result_no_match], "auth login")
        assert ranked[0]["chunk_id"] == "c1"
