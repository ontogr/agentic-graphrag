"""Unit tests for cross-encoder dependency handling."""

import pytest

from agrag.embedding.errors import EmbeddingMissingExtraError
from agrag.evidence import rerank
from agrag.retrieval.settings import RetrievalSettings


class TestCrossEncoderReranker:
    """A missing local embedding extra has an actionable domain error."""

    def test_direct_construction_names_the_missing_extra(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Direct construction identifies the extra and its install command."""

        def missing_module(_module_name: str) -> None:
            return None

        monkeypatch.setattr(rerank.importlib.util, "find_spec", missing_module)

        with pytest.raises(
            EmbeddingMissingExtraError,
            match=r"agentic-graphrag\[embed-local\]",
        ) as error:
            rerank.CrossEncoderReranker("cross-encoder/model")

        assert error.value.extra == "embed-local"

    def test_settings_factory_keeps_rerank_optional(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Configured rerank falls back to no reranker when the extra is absent."""

        def missing_module(_module_name: str) -> None:
            return None

        monkeypatch.setattr(rerank.importlib.util, "find_spec", missing_module)
        settings = RetrievalSettings(rerank_enabled=True, _env_file=None)

        assert rerank.reranker_from_settings(settings) is None
