"""Tests for RetrievalSettings."""

import os

from agrag.retrieval.settings import RetrievalSettings


class TestRetrievalSettings:
    """RetrievalSettings loads from defaults and env."""

    def test_default_values(self) -> None:
        """Default settings have expected values."""
        s = RetrievalSettings()
        assert s.entity_collection == "agrag_entities"
        assert s.chunk_collection == "agrag_chunks"
        assert s.entity_top_k == 10
        assert s.chunk_top_k == 10
        assert s.hybrid_alpha == 0.5
        assert s.traversal_depth == 2
        assert s.traversal_limit == 50
        assert s.rrf_k == 60
        assert s.reranker_min_score is None
        assert s.text2cypher_max_retries == 3

    def test_custom_values(self) -> None:
        """Custom values override defaults."""
        s = RetrievalSettings(
            entity_top_k=20,
            chunk_top_k=5,
            hybrid_alpha=0.7,
        )
        assert s.entity_top_k == 20
        assert s.chunk_top_k == 5
        assert s.hybrid_alpha == 0.7

    def test_env_prefix(self) -> None:
        """Settings reads from RETRIEVAL_ env prefix."""
        os.environ["RETRIEVAL_ENTITY_TOP_K"] = "42"
        try:
            s = RetrievalSettings()
            assert s.entity_top_k == 42
        finally:
            del os.environ["RETRIEVAL_ENTITY_TOP_K"]
