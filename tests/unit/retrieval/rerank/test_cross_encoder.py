"""Tests for cross_encoder_rerank in agrag.retrieval.rerank.cross_encoder.

Simulates the ``sentence_transformers`` extra by patching ``sys.modules``: a
bare ``ModuleType`` stand-in models the extra being present but unusable, and
a fake module exposing a working ``CrossEncoder`` class models a real model
being available. Covers falling back to unchanged results when no usable
model is available, an empty input list, that min_score filtering is skipped
without a model, and that it actually drops low-scoring results when a model
is present.
"""

import asyncio
import sys
import threading
import time
from types import ModuleType
from unittest.mock import patch
from uuid import uuid4

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.community import Community
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.relation import Relation
from agrag.common.data_models.search_result import SearchResult
from agrag.retrieval.rerank.cross_encoder import cross_encoder_rerank


def _make_result(score: float = 1.0, name: str = "Test Entity") -> SearchResult:
    return SearchResult(
        item=Entity(id=uuid4(), label="Person", name=name),
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
        """A present model scores each result, drops low ones, and sorts."""
        r1 = _make_result(name="Entity A")
        r2 = _make_result(name="Entity B")
        r3 = _make_result(name="Entity C")
        # r1 is filtered out; r2 and r3 survive but arrive in ascending score
        # order, so only a real descending sort puts r3 ahead of r2.
        fake_module = _fake_cross_encoder_module([0.3, 0.6, 0.9])
        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            reranked = await cross_encoder_rerank("query", [r1, r2, r3], min_score=0.5)
        assert len(reranked) == 2
        assert reranked[0].item.name == "Entity C"
        assert reranked[0].score == 0.9
        assert reranked[1].item.name == "Entity B"
        assert reranked[1].score == 0.6

    async def test_reranks_chunk_relation_and_community_items(self) -> None:
        """_text_of extracts display text for every non-entity item type."""
        chunk = SearchResult(
            item=Chunk(
                id=uuid4(),
                document_id=uuid4(),
                index=0,
                text="chunk body",
                provenance=TextProvenance(char_start=0, char_end=10),
            ),
            score=0.1,
            method="test",
        )
        relation = SearchResult(
            item=Relation(
                id=uuid4(),
                type="KNOWS",
                source_id=uuid4(),
                target_id=uuid4(),
            ),
            score=0.1,
            method="test",
        )
        community = SearchResult(
            item=Community(
                id=uuid4(),
                title="T",
                summary="S",
                rating=5,
                rating_explanation="e",
            ),
            score=0.1,
            method="test",
        )
        captured_pairs: list[tuple[str, str]] = []

        class RecordingCrossEncoder:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
                captured_pairs.extend(pairs)
                return [0.5 for _ in pairs]

        module = ModuleType("fake")
        module.CrossEncoder = RecordingCrossEncoder

        with patch.dict(sys.modules, {"sentence_transformers": module}):
            reranked = await cross_encoder_rerank(
                "query",
                [chunk, relation, community],
                model=f"text-of-model-{uuid4().hex}",
            )

        assert len(reranked) == 3
        texts = {text for _, text in captured_pairs}
        assert "chunk body" in texts
        assert any("KNOWS" in text for text in texts)
        assert community.item.embedding_text in texts

    async def test_cached_model_is_reused_across_calls(self) -> None:
        """A second call with the same model name reuses the cached instance.

        Regression test: only the predict() call was offloaded via
        asyncio.to_thread; without caching, every call reconstructs the
        CrossEncoder, which is the expensive part this cache exists to avoid.
        """
        r1 = _make_result()
        construction_count = 0

        class CountingCrossEncoder:
            def __init__(self, *args: object, **kwargs: object) -> None:
                nonlocal construction_count
                construction_count += 1

            def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
                return [0.5 for _ in pairs]

        module = ModuleType("fake")
        module.CrossEncoder = CountingCrossEncoder
        model_name = f"cache-hit-model-{uuid4().hex}"

        with patch.dict(sys.modules, {"sentence_transformers": module}):
            await cross_encoder_rerank("query", [r1], model=model_name)
            await cross_encoder_rerank("query", [r1], model=model_name)

        assert construction_count == 1

    async def test_model_construction_runs_off_the_event_loop(self) -> None:
        """A cache-miss CrossEncoder() construction does not block the loop.

        Regression test: only predict() was offloaded via asyncio.to_thread;
        the constructor ran synchronously on a cache miss, which can block
        every concurrent search() call while a larger model's weights load.
        Uses a unique model name so this never touches the shared
        _MODEL_CACHE key other tests rely on.
        """
        r1 = _make_result()
        construction_thread: threading.Thread | None = None

        class RecordingCrossEncoder:
            def __init__(self, *args: object, **kwargs: object) -> None:
                nonlocal construction_thread
                construction_thread = threading.current_thread()

            def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
                return [0.5 for _ in pairs]

        module = ModuleType("fake")
        module.CrossEncoder = RecordingCrossEncoder

        with patch.dict(sys.modules, {"sentence_transformers": module}):
            await cross_encoder_rerank("query", [r1], model=f"test-model-{uuid4().hex}")

        assert construction_thread is not None
        assert construction_thread is not threading.main_thread()

    async def test_concurrent_first_loads_construct_model_once(self) -> None:
        """Concurrent first calls with the same model construct one instance.

        Regression test: without per-model locking, a second caller could
        pass the cache check while the first construction is still running
        in its worker thread, building a duplicate CrossEncoder (and a
        duplicate weight download) for the same name.
        """
        r1 = _make_result()
        construction_count = 0

        class CountingCrossEncoder:
            def __init__(self, *args: object, **kwargs: object) -> None:
                nonlocal construction_count
                construction_count += 1
                # Keep the first construction in flight long enough that a
                # second caller can reach the cache check before it lands.
                time.sleep(0.05)

            def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
                return [0.5 for _ in pairs]

        module = ModuleType("fake")
        module.CrossEncoder = CountingCrossEncoder
        model_name = f"concurrent-model-{uuid4().hex}"

        with patch.dict(sys.modules, {"sentence_transformers": module}):
            first, second = await asyncio.gather(
                cross_encoder_rerank("query", [r1], model=model_name),
                cross_encoder_rerank("query", [r1], model=model_name),
            )

        assert construction_count == 1
        assert len(first) == 1
        assert len(second) == 1
