"""Tests for build_embedder and EmbeddingSettings."""

import pytest

from agrag.embedding import build_embedder
from agrag.embedding.sentence_transformers import SentenceTransformerEmbedder
from agrag.embedding.settings import EmbeddingSettings


class TestBuildEmbedder:
    """build_embedder turns a name into an embedder, or passes one through."""

    def test_build_from_model_name(self) -> None:
        """A model name builds a SentenceTransformerEmbedder."""
        embedder = build_embedder("BAAI/bge-small-en-v1.5")
        assert isinstance(embedder, SentenceTransformerEmbedder)
        assert embedder.model == "BAAI/bge-small-en-v1.5"

    def test_passthrough_embedder_instance(self) -> None:
        """An existing Embedder is returned unchanged."""
        embedder = SentenceTransformerEmbedder(model=object())
        assert build_embedder(embedder) is embedder


class TestEmbeddingSettings:
    """EmbeddingSettings carries the planned defaults."""

    def test_default_model(self) -> None:
        """The default model is the planned granite embedding."""
        assert (
            EmbeddingSettings().model
            == "ibm-granite/granite-embedding-small-english-r2"
        )

    def test_defaults(self) -> None:
        """The other defaults match the plan."""
        settings = EmbeddingSettings()
        assert settings.normalize is True
        assert settings.batch_size == 32
        assert settings.device is None
        assert settings.cache_folder is None

    def test_env_override(self) -> None:
        """The EMBEDDING_ prefix overrides fields from the environment."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("EMBEDDING_MODEL", "custom/model")
            mp.setenv("EMBEDDING_BATCH_SIZE", "64")
            settings = EmbeddingSettings()
        assert settings.model == "custom/model"
        assert settings.batch_size == 64
