"""Tests for cross_encoder_rerank in agrag.retrieval.rerank.cross_encoder.

Simulates the ``sentence_transformers`` extra by patching ``sys.modules``: a
bare ``ModuleType`` stand-in models the extra being present but unusable, and
a fake module exposing a working ``CrossEncoder`` class models a real model
being available. Covers falling back to unchanged results when no usable
model is available, an empty input list, that min_score filtering is skipped
without a model, and that it actually drops low-scoring results when a model
is present.
"""

import sys
from types import ModuleType
from unittest.mock import patch
from uuid import uuid4

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult
from agrag.retrieval.rerank.cross_encoder import cross_encoder_rerank


def _make_result(score: float = 1.0) -> SearchResult:
    return SearchResult(
        item=Entity(id=uuid4(), label="Person", name="Test Entity"),
        score=score,
        method="test",
    )


def _fake_cross_encoder_module(scores: list[float]) -> ModuleType:
    """Build a fake sentence_transformers module with a working CrossEncoder."""

    class FakeCrossEncoder:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
            return scores

    module = ModuleType("fake")
    module.CrossEncoder = FakeCrossEncoder
    return module


class TestCrossEncoderRerank:
    """cross_encoder_rerank reorders by cross-encoder score."""

    async def test_returns_results_when_no_model(self) -> None:
        """Without sentence-transformers, returns results unchanged."""
        r1 = _make_result(score=0.9)
        r2 = _make_result(score=0.8)
        with patch.dict(sys.modules, {"sentence_transformers": ModuleType("fake")}):
            reranked = await cross_encoder_rerank("test query", [r1, r2])
        # Without the extra, results come back unchanged.
        assert len(reranked) == 2

    async def test_empty_list(self) -> None:
        """Empty input returns empty."""
        reranked = await cross_encoder_rerank("query", [])
        assert reranked == []

    async def test_min_score_filters(self) -> None:
        """Results below min_score are dropped when available."""
        r1 = _make_result(score=0.9)
        # Without the model, min_score filtering is not applied.
        with patch.dict(sys.modules, {"sentence_transformers": ModuleType("fake")}):
            reranked = await cross_encoder_rerank("query", [r1], min_score=0.5)
        assert len(reranked) >= 1

    async def test_min_score_filters_when_model_present(self) -> None:
        """A present model drops results below min_score, keeps the rest."""
        r1 = _make_result(score=0.1)
        r2 = _make_result(score=0.1)
        fake_module = _fake_cross_encoder_module([0.9, 0.2])
        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            reranked = await cross_encoder_rerank("query", [r1, r2], min_score=0.5)
        assert len(reranked) == 1
        assert reranked[0].score == 0.9
