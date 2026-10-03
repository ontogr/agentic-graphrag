"""Tests for the SearchEngine and traversal root spans.

Pins the span tree a search exports: concurrent retriever siblings under the
root, fuse between and after them, conditional BFS, community and rerank
spans, partial-failure recording, and the three traversal entry points. The
engine's stores are mocks; the retrievers and helpers are the real ones.
"""

import json
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult
from agrag.common.data_models.vector_record import VectorHit
from agrag.retrieval.errors import AllRetrievalMethodsFailedError, ScopeDeniedError
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.methods.traversal import (
    find_entity,
    list_relationship_types,
    traverse,
)
from agrag.retrieval.recipes import HYBRID
from agrag.retrieval.retrievers.bfs import BFSRetriever
from agrag.retrieval.retrievers.chunk import ChunkRetriever
from agrag.retrieval.retrievers.community import CommunityRetriever
from agrag.retrieval.retrievers.entity import EntityRetriever
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a provider and exporter pair backed by one in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _named(spans: tuple[ReadableSpan, ...], name: str) -> list[ReadableSpan]:
    """Return the exported spans whose name matches."""
    return [span for span in spans if span.name == name]


def _entity_node(entity_id) -> dict:
    """Return one stored entity node."""
    return {
        "id": str(entity_id),
        "name": "Alice",
        "merge_key": "Person:alice",
        "merge_count": 1,
        "source_chunk_ids": [],
    }


def _entity_rows(entity_id) -> list[dict]:
    """Return one load_entities row."""
    return [{"n": _entity_node(entity_id)}]


def _chunk_rows(chunk_id) -> list[dict]:
    """Return one load_chunks row."""
    return [
        {
            "n": {
                "id": str(chunk_id),
                "labels": ["Chunk"],
                "properties": {
                    "document_id": str(uuid4()),
                    "index": 0,
                    "text": "a passage",
                    "provenance": json.dumps(
                        {"kind": "text", "char_start": 0, "char_end": 9}
                    ),
                },
            }
        }
    ]


class _MockEmbedder:
    """Mock embedder returning a fixed vector."""

    async def embed_one(self, text: str) -> list[float]:
        """Return a fixed vector."""
        return [0.1, 0.2, 0.3]


def _routed_store() -> AsyncMock:
    """Return a store whose reads route by query text and echo hit ids.

    Entity, chunk and resolved loading rebuild their rows from the ids
    the query asked for, so a loaded item's id always matches the hit
    that requested it.
    """
    store = AsyncMock()

    async def _read(query, params=None, **kwargs):
        params = params or {}
        if "Document" in query:
            return [{"id": value} for value in params.get("document_ids", [])]
        if "ResolvedEntity" in query:
            ids = params.get("ids", [])
            return [
                {
                    "resolved": {
                        "id": value,
                        "name": "Alice",
                        "label": "Person",
                        "member_ids": [value],
                    }
                }
                for value in ids
            ]
        if "PART_OF" in query:
            return _chunk_rows(UUID(params["ids"][0]))
        if "UNWIND $ids" in query:
            return _entity_rows(UUID(params["ids"][0]))
        return []

    store.execute_read.side_effect = _read
    return store


def _hybrid_store() -> tuple[AsyncMock, list[VectorHit]]:
    """Return a store serving one entity hit and one chunk hit."""
    entity_hit = VectorHit(id=uuid4(), score=0.9, payload={})
    chunk_hit = VectorHit(id=uuid4(), score=0.8, payload={})
    hits = [entity_hit, chunk_hit]
    store = _routed_store()

    async def _vector_search(*, label, **kwargs):
        """Serve one hit per label; resolved entities have none."""
        return {"Person": [entity_hit], "Chunk": [chunk_hit]}.get(label, [])

    store.vector_search.side_effect = _vector_search
    return store, hits


def _engine(store: AsyncMock, tracer) -> SearchEngine:
    """Return a SearchEngine over ``store`` with entity labels set."""
    return SearchEngine(
        graph_store=store,
        embedder=_MockEmbedder(),
        settings=RetrievalSettings(),
        entity_labels=["Person"],
        tracer=tracer,
    )


class TestSearchSpanTree:
    """The span tree one HYBRID search exports."""

    async def test_hybrid_exports_root_retrievers_and_fuse(self) -> None:
        """Entity and chunk are concurrent siblings under the root, then fuse."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        store, hits = _hybrid_store()
        engine = _engine(store, tracer)

        results = await engine.search("who is alice", HYBRID)

        spans = exporter.get_finished_spans()
        roots = _named(spans, "agrag.retrieval.search")
        assert len(roots) == 1
        root = roots[0]
        attributes = root.attributes
        assert attributes is not None
        assert attributes["openinference.span.kind"] == "RETRIEVER"
        assert attributes["input.value"] == "who is alice"
        assert list(attributes["agrag.recipe.methods"]) == ["entity", "chunk"]
        assert list(attributes["agrag.result_ids"]) == [
            str(result.item.id) for result in results
        ]
        # Every retriever and fuse span is a direct child of the root.
        child_names = {
            span.name
            for span in spans
            if span.parent is not None and span.parent.span_id == root.context.span_id
        }
        assert child_names == {
            "agrag.retrieval.entity",
            "agrag.retrieval.chunk",
            "agrag.retrieval.fuse",
        }
        # The retrievers saw the two hits the store returned.
        assert {str(hit.id) for hit in hits} >= {
            str(result.item.id) for result in results
        }

    async def test_conditional_stages_appear_only_when_the_recipe_asks(self) -> None:
        """No bfs, community_expand or rerank spans for a plain HYBRID."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        store, _ = _hybrid_store()
        engine = _engine(store, tracer)

        await engine.search("who is alice", HYBRID)

        names = {span.name for span in exporter.get_finished_spans()}
        assert "agrag.retrieval.bfs" not in names
        assert "agrag.retrieval.community_expand" not in names
        assert "agrag.retrieval.rerank.cross_encoder" not in names
        assert "agrag.retrieval.rerank.node_distance" not in names

    async def test_tracer_none_leaves_the_host_span_untouched(self) -> None:
        """An untraced engine opens nothing and marks no host span."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        store, _ = _hybrid_store()
        engine = _engine(store, None)

        with tracer.start_as_current_span("host"):
            await engine.search("who is alice", HYBRID)

        host = _named(exporter.get_finished_spans(), "host")[0]
        assert host.status.status_code.name != "ERROR"
        assert not [e for e in host.events if e.name == "exception"]


class TestSearchFailureRecording:
    """Partial method failures record on the root without erroring it."""

    async def test_one_failing_method_leaves_the_root_unset(self) -> None:
        """A failing method among succeeding ones records and stays UNSET."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")

        entity_hit = VectorHit(id=uuid4(), score=0.9, payload={})
        store = _routed_store()

        async def _vector_search(*, label, **kwargs):
            """Serve the entity hit; the chunk search fails."""
            if label == "Chunk":
                raise RuntimeError("boom")
            return [entity_hit] if label == "Person" else []

        store.vector_search.side_effect = _vector_search
        engine = _engine(store, tracer)

        results = await engine.search("who is alice", HYBRID)

        assert len(results) == 1
        spans = exporter.get_finished_spans()
        root = _named(spans, "agrag.retrieval.search")[0]
        assert root.status.status_code.name != "ERROR"
        attributes = root.attributes
        assert attributes is not None
        assert list(attributes["agrag.failed_methods"]) == ["chunk"]
        exception_events = [
            span
            for span in spans
            if span.name == "agrag.retrieval.search"
            and any(e.name == "exception" for e in span.events)
        ]
        assert len(exception_events) == 1

    async def test_all_methods_failing_marks_the_root_error(self) -> None:
        """Every method failing raises and marks the root ERROR."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        store = AsyncMock()
        store.vector_search.side_effect = RuntimeError("down")
        engine = _engine(store, tracer)

        with pytest.raises(AllRetrievalMethodsFailedError):
            await engine.search("who is alice", HYBRID)

        root = _named(exporter.get_finished_spans(), "agrag.retrieval.search")[0]
        assert root.status.status_code.name == "ERROR"


class TestTraversalRootSpans:
    """find_entity, traverse and list_relationship_types export roots."""

    async def test_find_entity_exports_a_root_span(self) -> None:
        """A direct find_entity call exports the find_entity span."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        entity_hit = VectorHit(id=uuid4(), score=0.9, payload={})
        store = _routed_store()
        store.vector_search.return_value = [entity_hit]

        result = await find_entity(
            "alice",
            graph_store=store,
            embedder=_MockEmbedder(),
            vector_store=None,
            settings=RetrievalSettings(),
            entity_labels=["Person"],
            tracer=tracer,
        )

        spans = exporter.get_finished_spans()
        roots = _named(spans, "agrag.retrieval.find_entity")
        assert len(roots) == 1
        attributes = roots[0].attributes
        assert attributes is not None
        assert attributes["openinference.span.kind"] == "RETRIEVER"
        assert attributes["input.value"] == "alice"
        assert result is not None
        assert list(attributes["agrag.result_ids"]) == [str(result.item.id)]

    async def test_traverse_exports_a_root_span(self) -> None:
        """A direct traverse call exports the traverse span with seeds."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        seed_id = uuid4()
        neighbor_id = uuid4()
        seed = SearchResult(
            item=Entity(id=seed_id, label="Person", name="Alice"),
            score=1.0,
            method="entity",
        )
        store = AsyncMock()
        store.execute_read.return_value = [
            {"neighbor": _entity_node(neighbor_id), "id": str(neighbor_id)}
        ]

        results = await traverse(
            seed,
            graph_store=store,
            settings=RetrievalSettings(),
            depth=1,
            limit=5,
            tracer=tracer,
        )

        spans = exporter.get_finished_spans()
        roots = _named(spans, "agrag.retrieval.traverse")
        assert len(roots) == 1
        attributes = roots[0].attributes
        assert attributes is not None
        assert attributes["openinference.span.kind"] == "RETRIEVER"
        assert attributes["input.value"] == seed.item.embedding_text
        assert list(attributes["agrag.seed_ids"]) == [str(seed_id)]
        assert list(attributes["agrag.result_ids"]) == [
            str(result.item.id) for result in results
        ]

    async def test_list_relationship_types_exports_a_root_span(self) -> None:
        """A direct call exports the untyped list_relationship_types span."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        seed = SearchResult(
            item=Entity(id=uuid4(), label="Person", name="Alice"),
            score=1.0,
            method="entity",
        )
        store = AsyncMock()
        store.execute_read.return_value = [{"rel_type": "TREATS"}]

        types = await list_relationship_types(seed, graph_store=store, tracer=tracer)

        spans = exporter.get_finished_spans()
        roots = _named(spans, "agrag.retrieval.list_relationship_types")
        assert len(roots) == 1
        attributes = roots[0].attributes
        assert attributes is not None
        assert "openinference.span.kind" not in attributes
        assert list(attributes["agrag.result_types"]) == types
        assert attributes["agrag.result_count"] == len(types)

    async def test_a_denied_traverse_marks_the_span_error(self) -> None:
        """A ScopeDeniedError propagates and marks the traverse span."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")
        seed = SearchResult(
            item=Entity(id=uuid4(), label="Person", name="Alice"),
            score=1.0,
            method="entity",
        )

        with pytest.raises(ScopeDeniedError):
            await traverse(
                seed,
                graph_store=AsyncMock(),
                settings=RetrievalSettings(),
                relation_type="TREATS",
                filters=SearchFilters(relation_types=["PRESCRIBES"]),
                tracer=tracer,
            )

        root = _named(exporter.get_finished_spans(), "agrag.retrieval.traverse")[0]
        assert root.status.status_code.name == "ERROR"


class TestEngineWiring:
    """The engine passes its tracer to everything it builds."""

    async def test_engine_constructs_retrievers_of_the_right_types(self) -> None:
        """The retriever map holds the four retriever classes."""
        store, _ = _hybrid_store()
        engine = _engine(store, None)

        retrievers = engine._build_retrievers()

        assert isinstance(retrievers["entity"], EntityRetriever)
        assert isinstance(retrievers["chunk"], ChunkRetriever)
        assert isinstance(retrievers["community"], CommunityRetriever)
        assert "text2cypher" in retrievers

    async def test_bfs_retriever_construction_takes_a_tracer(self) -> None:
        """BFSRetriever accepts the engine's tracer (used by recipe.bfs)."""
        retriever = BFSRetriever(
            graph_store=AsyncMock(), settings=RetrievalSettings(), tracer=None
        )
        assert retriever.name == "bfs"
