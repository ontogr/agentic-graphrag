"""Tests for build_embedder.

Covers that a model name builds a FastEmbed embedder, and passthrough of an
existing Embedder instance.
"""

import pytest
from opentelemetry import trace

from agrag.embedding import build_embedder
from agrag.embedding.fastembed_dense import FastEmbedEmbedder
from agrag.embedding.sentence_transformers import SentenceTransformerEmbedder


class TestBuildEmbedder:
    """build_embedder turns a name into an embedder, or passes one through."""

    def test_model_name_builds_a_fastembed_embedder(self) -> None:
        """A model name gives a FastEmbed embedder for that model."""
        embedder = build_embedder("BAAI/bge-small-en-v1.5")
        assert isinstance(embedder, FastEmbedEmbedder)
        assert embedder.model == "BAAI/bge-small-en-v1.5"

    def test_passthrough_embedder_instance(self) -> None:
        """An existing Embedder is returned unchanged."""
        embedder = SentenceTransformerEmbedder(model=object())
        assert build_embedder(embedder) is embedder

    def test_tracer_with_instance_raises(self) -> None:
        """Passing tracer with an already-built embedder raises ValueError."""
        embedder = SentenceTransformerEmbedder(model=object())
        with pytest.raises(ValueError, match="tracer has no effect"):
            build_embedder(embedder, tracer=trace.get_tracer("test"))
