"""Tests for the retrieval helper spans.

Pins the span names, attributes and swallow-site behavior of the shared
helpers: ``vector_search``, ``resolve_entity``, ``hydrate_resolved_entities``,
``fuse``, the community helpers and both rerankers. Runs real spans through an
in-memory exporter; stores are mocks at the driver boundary.
"""

import asyncio
import contextlib
import json
import sys
from types import ModuleType
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult
from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.fusion import fuse
from agrag.retrieval.identity import resolve_entity
from agrag.retrieval.methods.vector import vector_search
from agrag.retrieval.rerank.cross_encoder import cross_encoder_rerank
from agrag.retrieval.rerank.node_distance import node_distance_rerank
from agrag.retrieval.settings import RetrievalSettings


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a provider and exporter pair backed by one in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _by_name(spans: tuple[ReadableSpan, ...]) -> list[ReadableSpan]:
    """Return the exported spans in export order."""
    return list(spans)


def _named(spans: tuple[ReadableSpan, ...], name: str) -> list[ReadableSpan]:
    """Return the exported spans whose name matches."""
    return [span for span in spans if span.name == name]


def _entity_result(score: float = 1.0) -> SearchResult:
    """Return one entity result."""
    return SearchResult(
        item=Entity(id=uuid4(), label="Person", name="Alice"),
        score=score,
        method="entity",
    )


class _MockEmbedder:
    """Mock embedder for vector search tests."""

    async def embed_one(self, text: str) -> list[float]:
        """Return a fixed vector."""
        return [0.1, 0.2, 0.3]


class TestVectorSearchSpan:
    """vector_search records the store path and its hits."""

    async def test_native_path_records_graph_native_and_hits(self) -> None:
        """The native path sets agrag.store=graph_native with hit ids."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        hit_a = VectorHit(id=uuid4(), score=0.9, payload={})
        hit_b = VectorHit(id=uuid4(), score=0.4, payload={})
        gs = AsyncMock()
        gs.vector_search.side_effect = [[hit_b], [hit_a]]

        hits = await vector_search(
            "q",
            embedder=_MockEmbedder(),
            graph_store=gs,
            vector_store=None,
            collection="agrag_entities",
            labels=["Person", "Drug"],
            limit=10,
            filters=None,
            settings=RetrievalSettings(),
            tracer=tracer,
        )

        spans = _named(exporter.get_finished_spans(), "agrag.retrieval.vector_search")
        assert len(spans) == 1
        attributes = spans[0].attributes
        assert attributes is not None
        assert attributes["agrag.store"] == "graph_native"
        assert attributes["agrag.collection"] == "agrag_entities"
        assert list(attributes["agrag.labels"]) == ["Person", "Drug"]
        assert attributes["agrag.limit"] == 10
        assert json.loads(attributes["agrag.filters"]) == {
            "labels": [],
            "relation_types": [],
            "document_ids": [],
            "properties": {},
        }
        assert attributes["agrag.hit_count"] == 2
        assert list(attributes["agrag.hit_ids"]) == [str(hits[0].id), str(hits[1].id)]
        assert list(attributes["agrag.hit_scores"]) == [0.9, 0.4]

    async def test_vector_store_path_records_vector_store(self) -> None:
        """The VectorStore path sets agrag.store=vector_store."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        vs = AsyncMock()
        vs.hybrid_search.return_value = []

        await vector_search(
            "q",
            embedder=_MockEmbedder(),
            graph_store=AsyncMock(),
            vector_store=vs,
            collection="agrag_entities",
            labels=["Person"],
            limit=5,
            filters=None,
            settings=RetrievalSettings(),
            tracer=tracer,
        )

        attributes = _named(
            exporter.get_finished_spans(), "agrag.retrieval.vector_search"
        )[0].attributes
        assert attributes is not None
        assert attributes["agrag.store"] == "vector_store"
        assert attributes["agrag.hit_count"] == 0
        assert "agrag.hit_ids" not in attributes
        assert "agrag.hit_scores" not in attributes

    async def test_native_search_without_labels_marks_the_span_error(self) -> None:
        """The ValueError a misconfiguration raises marks the span ERROR."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")

        with pytest_raises_value_error():
            await vector_search(
                "q",
                embedder=_MockEmbedder(),
                graph_store=AsyncMock(),
                vector_store=None,
                collection="agrag_entities",
                labels=[],
                limit=5,
                filters=None,
                settings=RetrievalSettings(),
                tracer=tracer,
            )

        span = _named(exporter.get_finished_spans(), "agrag.retrieval.vector_search")[0]
        assert span.status.status_code.name == "ERROR"


def pytest_raises_value_error():
    """Return the context manager the misconfiguration test uses."""
    return contextlib.suppress(ValueError)


def _resolve_row(entity_id, merged_into=None) -> dict:
    """Build a resolve_merged_into_query row for one node."""
    return {
        "node": {
            "id": str(entity_id),
            "labels": ["Person"],
            "properties": {
                "name": "Alice",
                "merge_key": "Person:alice",
                "merged_from": [],
                "merge_count": 1,
                "source_chunk_ids": [],
            },
        },
        "merged_into": str(merged_into) if merged_into else None,
    }


class TestResolveEntitySpan:
    """resolve_entity records hops and the resolved id."""

    async def test_two_hop_chain_records_hops_of_two(self) -> None:
        """A two-hop merged_into chain records agrag.hops=2."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        first = uuid4()
        second = uuid4()
        survivor = uuid4()
        gs = AsyncMock()
        gs.execute_read.side_effect = [
            [_resolve_row(first, merged_into=second)],
            [_resolve_row(second, merged_into=survivor)],
            [_resolve_row(survivor)],
        ]

        entity = await resolve_entity(gs, first, tracer=tracer)

        attributes = _named(
            exporter.get_finished_spans(), "agrag.retrieval.resolve_entity"
        )[0].attributes
        assert attributes is not None
        assert attributes["agrag.hops"] == 2
        assert attributes["agrag.resolved_id"] == str(entity.id)
        assert attributes["agrag.entity_id"] == str(first)

    async def test_missing_entity_marks_the_span_error(self) -> None:
        """A chain pointing at a missing node marks the span ERROR."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        first = uuid4()
        gs = AsyncMock()
        gs.execute_read.side_effect = [
            [_resolve_row(first, merged_into=uuid4())],
            [],
        ]

        with contextlib.suppress(ValueError):
            await resolve_entity(gs, first, tracer=tracer)

        span = _named(exporter.get_finished_spans(), "agrag.retrieval.resolve_entity")[
            0
        ]
        assert span.status.status_code.name == "ERROR"


class TestFuseSpan:
    """Fuse records per-method counts and results."""

    def test_records_method_counts_in_dict_order(self) -> None:
        """The method arrays follow the dict's order."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        results = [_entity_result(), _entity_result()]

        fused = fuse({"entity": results, "chunk": []}, rrf_k=60, tracer=tracer)

        span = _named(exporter.get_finished_spans(), "agrag.retrieval.fuse")[0]
        attributes = span.attributes
        assert attributes is not None
        assert list(attributes["agrag.fuse.methods"]) == ["entity", "chunk"]
        assert list(attributes["agrag.fuse.method_counts"]) == [2, 0]
        assert attributes["agrag.rrf_k"] == 60
        assert attributes["agrag.result_count"] == len(fused)
        assert list(attributes["agrag.result_ids"]) == [str(r.item.id) for r in fused]


class TestCrossEncoderSpan:
    """The cross-encoder reranker's spans."""

    async def test_import_error_fallback_records_and_skips(self) -> None:
        """Without the extra: event recorded, skipped set, status UNSET.

        A unique model name keeps this clear of the module-level model
        cache other test modules populate with fakes under the default
        name.
        """
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        results = [_entity_result()]
        with patch.dict(sys.modules, {"sentence_transformers": ModuleType("fake")}):
            reranked = await cross_encoder_rerank(
                "query", results, model=f"missing-extra-{uuid4().hex}", tracer=tracer
            )

        assert reranked == results
        span = _named(
            exporter.get_finished_spans(), "agrag.retrieval.rerank.cross_encoder"
        )[0]
        assert span.status.status_code.name != "ERROR"
        assert [e for e in span.events if e.name == "exception"]
        assert span.attributes is not None
        assert span.attributes["agrag.skipped"] is True
        assert span.attributes["agrag.result_count"] == 1

    async def test_concurrent_first_loads_export_one_model_load(self) -> None:
        """Two concurrent first calls export exactly one model_load span."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        results = [_entity_result()]

        class _FakeCrossEncoder:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
                return [0.5 for _ in pairs]

        module = ModuleType("fake")
        module.CrossEncoder = _FakeCrossEncoder
        model_name = f"span-model-{uuid4().hex}"

        with patch.dict(sys.modules, {"sentence_transformers": module}):
            await asyncio.gather(
                cross_encoder_rerank("q", results, model=model_name, tracer=tracer),
                cross_encoder_rerank("q", results, model=model_name, tracer=tracer),
            )

        loads = _named(
            exporter.get_finished_spans(), "agrag.retrieval.rerank.model_load"
        )
        assert len(loads) == 1
        assert loads[0].attributes is not None
        assert loads[0].attributes["agrag.model"] == model_name

    async def test_rerank_span_records_results(self) -> None:
        """A successful rerank records the model and the reranked results."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        results = [_entity_result()]

        class _FakeCrossEncoder:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
                return [0.75]

        module = ModuleType("fake")
        module.CrossEncoder = _FakeCrossEncoder

        with patch.dict(sys.modules, {"sentence_transformers": module}):
            await cross_encoder_rerank(
                "query",
                results,
                model=f"span-rerank-{uuid4().hex}",
                min_score=0.5,
                tracer=tracer,
            )

        span = _named(
            exporter.get_finished_spans(), "agrag.retrieval.rerank.cross_encoder"
        )[0]
        attributes = span.attributes
        assert attributes is not None
        assert attributes["agrag.input_count"] == 1
        assert attributes["agrag.min_score"] == 0.5
        assert attributes["agrag.result_count"] == 1
        assert "agrag.skipped" not in attributes


class TestNodeDistanceSpan:
    """The node-distance reranker's span counts its path queries."""

    async def test_path_query_count_equals_non_seed_candidates(self) -> None:
        """Every non-seed entity candidate runs exactly one path query."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        seed_id = uuid4()
        candidates = [_entity_result() for _ in range(3)]
        candidates.append(
            SearchResult(item=seed_entity(seed_id), score=1.0, method="bfs")
        )
        gs = AsyncMock()
        gs.execute_read.return_value = [{"dist": 2}]

        await node_distance_rerank(
            candidates, graph_store=gs, seed_ids=[seed_id], tracer=tracer
        )

        span = _named(
            exporter.get_finished_spans(), "agrag.retrieval.rerank.node_distance"
        )[0]
        attributes = span.attributes
        assert attributes is not None
        assert attributes["agrag.seed_count"] == 1
        assert attributes["agrag.input_count"] == 4
        assert attributes["agrag.path_query_count"] == 3


def seed_entity(seed_id):
    """Return the entity the seed id names."""
    return Entity(id=seed_id, label="Person", name="Seed")


class TestNoTracerLeavesHostSpanUntouched:
    """Every helper with tracer=None leaves a host span unmarked."""

    async def test_vector_search(self) -> None:
        """vector_search adds no exception event to the host span."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        gs = AsyncMock()
        gs.vector_search.return_value = [VectorHit(id=uuid4(), score=0.5, payload={})]

        with tracer.start_as_current_span("host"):
            await vector_search(
                "q",
                embedder=_MockEmbedder(),
                graph_store=gs,
                vector_store=None,
                collection="c",
                labels=["Person"],
                limit=5,
                filters=None,
                settings=RetrievalSettings(),
            )

        host = _named(exporter.get_finished_spans(), "host")[0]
        assert host.status.status_code.name != "ERROR"
        assert not [e for e in host.events if e.name == "exception"]

    async def test_resolve_entity(self) -> None:
        """resolve_entity adds no exception event to the host span."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        gs = AsyncMock()
        gs.execute_read.return_value = [_resolve_row(uuid4())]

        with tracer.start_as_current_span("host"):
            await resolve_entity(gs, uuid4())

        host = _named(exporter.get_finished_spans(), "host")[0]
        assert host.status.status_code.name != "ERROR"
        assert not [e for e in host.events if e.name == "exception"]

    async def test_fuse(self) -> None:
        """Fuse adds no exception event to the host span."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")

        with tracer.start_as_current_span("host"):
            fuse({"entity": [_entity_result()]})

        host = _named(exporter.get_finished_spans(), "host")[0]
        assert host.status.status_code.name != "ERROR"
        assert not [e for e in host.events if e.name == "exception"]

    async def test_rerankers(self) -> None:
        """Both rerankers add no exception event to the host span."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        results = [_entity_result()]

        class _FakeCrossEncoder:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
                return [0.5 for _ in pairs]

        module = ModuleType("fake")
        module.CrossEncoder = _FakeCrossEncoder
        gs = AsyncMock()
        gs.execute_read.return_value = [{"dist": 1}]

        with tracer.start_as_current_span("host"):
            with patch.dict(sys.modules, {"sentence_transformers": module}):
                await cross_encoder_rerank(
                    "q", results, model=f"host-model-{uuid4().hex}"
                )
            await node_distance_rerank(results, graph_store=gs, seed_ids=[uuid4()])

        host = _named(exporter.get_finished_spans(), "host")[0]
        assert host.status.status_code.name != "ERROR"
        assert not [e for e in host.events if e.name == "exception"]
