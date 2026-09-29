"""End-to-end retrieval tracing against a real Neo4j.

One real tracer is given to the graph store, the embedder and the engine, so
every exported span shares one trace id and no adapter span is an orphan. The
span tree is written to the test output directory as JSON, like the other
tracing suites. Run against the Docker Compose Neo4j from
``docker/docker-compose.ci.yml`` (``make dev-services-up``).
"""

import importlib.util
import json
import os
from collections.abc import AsyncGenerator, Sequence
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.methods.traversal import (
    find_entity,
    list_relationship_types,
    traverse,
)
from agrag.retrieval.recipes import HYBRID
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings


neo4j_missing = importlib.util.find_spec("neo4j") is None

_OUTPUT_DIR = Path(os.environ.get("AGRAG_TRACING_OUTPUT_DIR", "test-output"))


def _span_tree(spans: tuple[ReadableSpan, ...]) -> dict:
    """Serialize exported spans as one parent-pointer tree."""
    by_id = {span.context.span_id: span for span in spans}
    nodes = []
    for span in spans:
        parent = span.parent
        nodes.append(
            {
                "name": span.name,
                "trace_id": f"{span.context.trace_id:032x}",
                "span_id": f"{span.context.span_id:016x}",
                "parent_span_id": (
                    f"{parent.span_id:016x}" if parent is not None else None
                ),
                "parent_name": (
                    by_id[parent.span_id].name
                    if parent is not None and parent.span_id in by_id
                    else None
                ),
                "attributes": dict(span.attributes or {}),
            }
        )
    return {"spans": nodes}


class _OrthogonalEmbedder(Embedder):
    """Embedder giving each distinct text its own orthogonal unit vector."""

    model = "orthogonal"
    _DIMENSIONS = 64

    def __init__(self) -> None:
        """Start with an empty text-to-slot map."""
        self._slots: dict[str, int] = {}

    async def dimensions(self) -> int:
        """Return the vector size."""
        return self._DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return the one-hot vector assigned to each text."""
        vectors: list[list[float]] = []
        for text in texts:
            slot = self._slots.setdefault(text, len(self._slots))
            vector = [0.0] * self._DIMENSIONS
            vector[slot] = 1.0
            vectors.append(vector)
        return vectors


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestSearchTracingEndToEnd:
    """One tracer across store, embedder and engine yields one tree."""

    @pytest.fixture(autouse=True)
    async def setup_traced_engine(self) -> AsyncGenerator[None, None]:
        """Build a traced store, embedder and engine sharing one tracer."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        self.exporter = exporter
        self.tracer = provider.get_tracer("test")

        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        self.chunk_ids: list[UUID] = []
        self.embedder = _OrthogonalEmbedder()
        self.settings = RetrievalSettings(entity_top_k=10, chunk_top_k=10)
        self.schema = GraphSchema(
            name="search_tracing",
            version="1",
            entities=[EntityType(label=self.label, description="A test entity.")],
            relations=[],
        )
        self.engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
            graph_schema=self.schema,
            tracer=self.tracer,
        )
        yield
        await self.store.execute_write(f"MATCH (n:{self.label}) DETACH DELETE n")
        if self.chunk_ids:
            await self.store.execute_write(
                f"MATCH (n:{CHUNK_LABEL}) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [str(chunk_id) for chunk_id in self.chunk_ids]},
            )
        await self.store.close()
        provider.shutdown()

    async def _seed_entities(self, names: list[str]) -> list[Entity]:
        """Write entities with embeddings to the store."""
        entities: list[Entity] = []
        for name in names:
            entity = Entity(id=uuid4(), label=self.label, name=name)
            entity.embedding = await self.embedder.embed_one(name)
            entities.append(entity)
        await self.store.upsert_nodes(
            self.label,
            [
                NodeRecord(
                    id=entity.id,
                    labels=[self.label],
                    properties={
                        "name": entity.name,
                        "merge_key": entity.merge_key,
                        "merged_from": [],
                        "merge_count": 1,
                        "source_chunk_ids": [],
                        "embedding": entity.embedding,
                        "created_at": entity.created_at.isoformat(),
                    },
                )
                for entity in entities
            ],
        )
        await self.store.ensure_vector_index(
            label=self.label,
            vector_property="embedding",
            dimensions=await self.embedder.dimensions(),
            distance=Distance.COSINE,
        )
        return entities

    async def _seed_chunks(self, texts: list[str]) -> list[Chunk]:
        """Write chunks with embeddings to the store."""
        chunks: list[Chunk] = []
        for text in texts:
            chunk = Chunk(
                document_id=uuid4(),
                index=0,
                text=text,
                provenance=TextProvenance(char_start=0, char_end=len(text)),
            )
            chunk.embedding = await self.embedder.embed_one(text)
            chunks.append(chunk)
        self.chunk_ids.extend(chunk.id for chunk in chunks)
        await self.store.upsert_nodes(
            CHUNK_LABEL,
            [
                NodeRecord(
                    id=chunk.id,
                    labels=[CHUNK_LABEL],
                    properties={
                        "document_id": str(chunk.document_id),
                        "index": chunk.index,
                        "text": chunk.text,
                        "provenance": json.dumps(
                            {
                                "kind": "text",
                                "char_start": 0,
                                "char_end": len(chunk.text),
                            }
                        ),
                        "heading_path": [],
                        "content_kind": "text",
                        "embedding": chunk.embedding,
                        "created_at": chunk.created_at.isoformat(),
                    },
                )
                for chunk in chunks
            ],
        )
        await self.store.ensure_vector_index(
            label=CHUNK_LABEL,
            vector_property="embedding",
            dimensions=await self.embedder.dimensions(),
            distance=Distance.COSINE,
        )
        return chunks

    def _write_tree(self, spans: tuple[ReadableSpan, ...], name: str) -> None:
        """Write the span tree to the test output directory."""
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = _OUTPUT_DIR / f"{name}.json"
        path.write_text(json.dumps(_span_tree(spans), indent=2))

    def _one_tree(self, spans: tuple[ReadableSpan, ...]) -> ReadableSpan:
        """Assert one trace id and one root, and return the root."""
        trace_ids = {span.context.trace_id for span in spans}
        assert len(trace_ids) == 1, f"expected one trace, got {len(trace_ids)}"
        roots = [span for span in spans if span.parent is None]
        assert len(roots) == 1, f"expected one root, got {len(roots)}"
        return roots[0]

    def _has_retrieval_ancestor(
        self, span: ReadableSpan, by_id: dict[int, ReadableSpan]
    ) -> bool:
        """Walk parents looking for an agrag.retrieval.* span."""
        seen: set[int] = set()
        parent = span.parent
        while parent is not None and parent.span_id not in seen:
            seen.add(parent.span_id)
            holder = by_id.get(parent.span_id)
            if holder is None:
                return False
            if holder.name.startswith("agrag.retrieval."):
                return True
            parent = holder.parent
        return False

    async def test_hybrid_search_is_one_connected_trace(self) -> None:
        """Every exported span shares one trace with no orphan adapters."""
        await self._seed_entities(["Alice", "Bob"])
        await self._seed_chunks(["Alice works at Acme Corp"])

        results = await self.engine.search("Alice", HYBRID)

        assert results, "expected results from the hybrid search"
        spans = self.exporter.get_finished_spans()
        self._write_tree(spans, "hybrid_search_tracing")
        root = self._one_tree(spans)
        assert root.name == "agrag.retrieval.search"
        attributes = root.attributes
        assert attributes is not None
        assert list(attributes["agrag.result_ids"]) == [
            str(result.item.id) for result in results
        ]
        assert len(attributes["agrag.result_texts"]) == len(results)
        result_texts = attributes["agrag.result_texts"]
        assert isinstance(result_texts, list)
        assert str(result_texts[0]) == results[0].item.embedding_text

        by_id = {span.context.span_id: span for span in spans}
        # The three sibling retrievers ran (entity, chunk, and any others the
        # recipe asked for); HYBRID names entity and chunk.
        for name in ("agrag.retrieval.entity", "agrag.retrieval.chunk"):
            retrievers = [span for span in spans if span.name == name]
            assert retrievers, f"missing {name} span"
        # No adapter span is an orphan: every graphdb, vectordb and embedding
        # span sits under an agrag.retrieval.* span.
        adapters = [
            span
            for span in spans
            if span.name.startswith(
                ("agrag.graphdb.", "agrag.vectordb.", "agrag.embedding.")
            )
        ]
        assert adapters, "expected adapter spans from the real store"
        for adapter in adapters:
            assert self._has_retrieval_ancestor(adapter, by_id), (
                f"{adapter.name} is an orphan"
            )

    async def test_flattened_documents_carry_results(self) -> None:
        """The root records the first 20 results under the OI names too."""
        await self._seed_entities(["Alice"])
        await self._seed_chunks(["Alice works at Acme Corp"])

        results = await self.engine.search("Alice", HYBRID)

        spans = self.exporter.get_finished_spans()
        root = self._one_tree(spans)
        attributes = root.attributes
        assert attributes is not None
        count = min(len(results), 20)
        for index in range(count):
            assert f"retrieval.documents.{index}.document.id" in attributes
            assert f"retrieval.documents.{index}.document.content" in attributes
        if len(results) < 20:
            assert f"retrieval.documents.{count}.document.id" not in attributes

    async def test_scoped_search_projects_filters_onto_retrievers(self) -> None:
        """A scoped search records the filters on the root and retrievers."""
        await self._seed_entities(["Alice"])
        await self._seed_chunks(["Alice works at Acme Corp"])

        await self.engine.search(
            "Alice", HYBRID, filters=SearchFilters(document_ids=["doc-1"])
        )

        spans = self.exporter.get_finished_spans()
        self._write_tree(spans, "scoped_search_tracing")
        self._one_tree(spans)
        root = next(span for span in spans if span.name == "agrag.retrieval.search")
        root_attributes = root.attributes
        assert root_attributes is not None
        assert '"document_ids": ["doc-1"]' in str(root_attributes["agrag.filters"])
        for name in ("agrag.retrieval.entity", "agrag.retrieval.chunk"):
            retriever = next(span for span in spans if span.name == name)
            retriever_attributes = retriever.attributes
            assert retriever_attributes is not None
            assert '"document_ids"' in str(retriever_attributes["agrag.filters"])

    async def test_traversal_entry_points_are_connected_trees(self) -> None:
        """find_entity, traverse and list_relationship_types each connect."""
        entities = await self._seed_entities(["Ada", "Grace"])
        ada, grace = entities[0], entities[1]
        await self.store.upsert_relations(
            [
                RelationRecord(
                    id=uuid4(),
                    type="KNOWS",
                    start_id=ada.id,
                    end_id=grace.id,
                    properties={},
                )
            ]
        )
        resolved = await find_entity(
            "Ada",
            graph_store=self.store,
            embedder=self.embedder,
            vector_store=None,
            settings=self.settings,
            entity_labels=[self.label],
            tracer=self.tracer,
        )
        assert resolved is not None

        neighbours = await traverse(
            resolved,
            graph_store=self.store,
            settings=self.settings,
            tracer=self.tracer,
        )
        types = await list_relationship_types(
            resolved, graph_store=self.store, tracer=self.tracer
        )

        assert isinstance(neighbours, list)
        assert isinstance(types, list)
        spans = self.exporter.get_finished_spans()
        self._write_tree(spans, "traversal_tracing")
        self._one_tree(spans)
        for name in (
            "agrag.retrieval.find_entity",
            "agrag.retrieval.traverse",
            "agrag.retrieval.list_relationship_types",
        ):
            assert [span for span in spans if span.name == name], name

    async def test_untraced_engine_produces_no_spans(self) -> None:
        """tracer=None everywhere exports nothing and matches results."""
        untraced_engine = SearchEngine(
            graph_store=self.store,
            embedder=self.embedder,
            settings=self.settings,
            graph_schema=self.schema,
        )
        await self._seed_entities(["Alice"])
        await self._seed_chunks(["Alice works at Acme Corp"])

        untraced_results = await untraced_engine.search("Alice", HYBRID)
        assert self.exporter.get_finished_spans() == ()

        traced_results = await self.engine.search("Alice", HYBRID)

        assert [str(r.item.id) for r in untraced_results] == [
            str(r.item.id) for r in traced_results
        ]
