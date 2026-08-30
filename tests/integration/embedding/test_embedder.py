"""Integration tests for the sentence-transformers embedder.

These tests download a real model from the network on first use. They require
the ``embed-local`` extra (installed by ``make sync``) and network access.
They skip when sentence-transformers is not installed.
"""

import asyncio
import importlib.util
import math

import pytest

from agrag.embedding import build_embedder
from agrag.embedding.sentence_transformers import SentenceTransformerEmbedder
from agrag.embedding.settings import EmbeddingSettings


embed_local_missing = importlib.util.find_spec("sentence_transformers") is None


@pytest.mark.skipif(embed_local_missing, reason="embed-local extra not installed")
class TestSentenceTransformerEmbedderIntegration:
    """A real embedder produces dimension-matched, normalized vectors."""

    def test_embed_returns_dimension_matched_vectors(self) -> None:
        """Every vector has the length the embedder reports as its dimension."""
        embedder = SentenceTransformerEmbedder()
        texts = ["first passage", "second passage", "third passage"]
        vectors = asyncio.run(embedder.embed(texts))
        dimensions = asyncio.run(embedder.dimensions())
        assert len(vectors) == len(texts)
        assert dimensions > 0
        for vector in vectors:
            assert len(vector) == dimensions

    def test_embed_is_deterministic(self) -> None:
        """The same text always yields the same vector."""
        embedder = SentenceTransformerEmbedder()
        first = asyncio.run(embedder.embed(["a stable sentence"]))[0]
        second = asyncio.run(embedder.embed(["a stable sentence"]))[0]
        assert first == second

    def test_embed_one_returns_single_vector(self) -> None:
        """embed_one returns one vector of the embedder's dimension."""
        embedder = SentenceTransformerEmbedder()
        vector = asyncio.run(embedder.embed_one("a single passage"))
        assert len(vector) == asyncio.run(embedder.dimensions())

    def test_normalize_setting_changes_magnitude(self) -> None:
        """normalize=True yields near-unit vectors and differs from False."""
        normalized = SentenceTransformerEmbedder()
        raw = SentenceTransformerEmbedder(settings=EmbeddingSettings(normalize=False))
        nv = asyncio.run(normalized.embed(["a passage"]))[0]
        rv = asyncio.run(raw.embed(["a passage"]))[0]
        nv_norm = math.sqrt(sum(component * component for component in nv))
        rv_norm = math.sqrt(sum(component * component for component in rv))
        # sentence-transformers' normalize_embeddings yields vectors whose norm
        # is very close to 1.0; cosine search is scale-invariant, so the exact
        # scale is not load-bearing.
        assert abs(nv_norm - 1.0) < 0.05
        assert rv_norm > 5 * nv_norm

    def test_build_embedder_from_name(self) -> None:
        """build_embedder builds a working embedder from a model name."""
        embedder = build_embedder("ibm-granite/granite-embedding-small-english-r2")
        vector = asyncio.run(embedder.embed_one("configured by name"))
        assert len(vector) == asyncio.run(embedder.dimensions())
