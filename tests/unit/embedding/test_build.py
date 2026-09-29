"""Tests for build_embedder.

Covers passthrough of an existing Embedder instance.
"""

import pytest
from opentelemetry import trace

from agrag.embedding import build_embedder
from agrag.embedding.sentence_transformers import SentenceTransformerEmbedder


class TestBuildEmbedder:
    """build_embedder turns a name into an embedder, or passes one through."""

    def test_passthrough_embedder_instance(self) -> None:
        """An existing Embedder is returned unchanged."""
        embedder = SentenceTransformerEmbedder(model=object())
        assert build_embedder(embedder) is embedder

    def test_tracer_with_instance_raises(self) -> None:
        """Passing tracer with an already-built embedder raises ValueError."""
        embedder = SentenceTransformerEmbedder(model=object())
        with pytest.raises(ValueError, match="tracer has no effect"):
            build_embedder(embedder, tracer=trace.get_tracer("test"))
