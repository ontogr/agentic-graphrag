"""Exercise external placement through ingestion, retrieval, evidence, and repair.

Runs only when a real vector backend is explicitly selected. The serial CI
suite owns its graph database; collections use a unique prefix per test.
"""

import hashlib
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

import pytest
from mcp import Client, StdioServerParameters

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.evidence import (
    EvidenceSearchMode,
    EvidenceSearchResult,
    EvidenceSearchStatus,
)
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.vector_record import VectorKind
from agrag.embedding import FastEmbedEmbedder
from agrag.embedding.base import Embedder
from agrag.evidence import search_evidence
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.loaders.common import text_sections
from agrag.retrieval import CHUNK, SearchEngine
from tests.integration._backend import build_test_store
from tests.integration._vector_backend import build_vector_store, selected_vector_stores
from tests.integration.e2e._artifact import write_artifact


_BACKENDS = [name for name in selected_vector_stores() if name != "fake"]


class _TopicEmbedder(Embedder):
    """Keep semantic ranking deterministic without model downloads."""

    model = "external-placement-topics"

    async def dimensions(self) -> int:
        """Use the same four dimensions as graph integration fixtures."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Assign separate directions to three known fixture topics."""
        if any("rollbackmarker" in text for text in texts):
            raise RuntimeError("requested embedding failure")
        return [
            [
                float("orbit" in text.lower()),
                float("forest" in text.lower()),
                float("ocean" in text.lower()),
                0.01,
            ]
            for text in texts
        ]


class _Extractor(Extractor):
    """Keep the lifecycle corpus independent of extraction models."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return no entities for the passage-only corpus."""
        return ExtractionResult(
            entities=[], relations=[], extractor_name="external-e2e"
        )


def _document(key: str, text: str) -> Document:
    """Build a prose document with an explicit stable source key."""
    return Document(
        text=text,
        title=key,
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(text),
        line_count=1,
        sections=text_sections(text),
    )


@pytest.mark.neo4j_only
class TestExternalPlacementE2E:
    """A real external index tracks committed graph data without graph embeddings."""

    @pytest.mark.parametrize("backend", _BACKENDS)
    async def test_mcp_subprocess_searches_external_placement(
        self, backend: str
    ) -> None:
        """The configured CLI opens, searches and closes a real external index."""
        store = build_test_store()
        prefix = f"mcp_{uuid4().hex[:12]}"
        vectors = build_vector_store(backend, collection_prefix=prefix)
        key = "external://mcp"
        schema = GraphSchema(
            name="external_mcp",
            version="1",
            entities=[EntityType(label="ExternalTopic", description="A topic.")],
            relations=[],
        )
        await store.connect()
        await store.execute_write("MATCH (node) DETACH DELETE node")
        try:
            graph = await Graph.open(
                schema=schema,
                graph_store=store,
                embedder=FastEmbedEmbedder(),
                extractor=_Extractor(),
                vector_store=vectors,
            )
            await graph.add(
                documents=[_document(key, "Orbit mechanics describe satellite motion.")]
            )
            args = ["-m", "agrag.mcp_server"]
            if os.environ.get("COVERAGE_FILE"):
                args = ["-m", "coverage", "run", "--parallel-mode", *args]
            parameters = StdioServerParameters(
                command=sys.executable,
                args=args,
                env={
                    **os.environ,
                    "MCP_GRAPH_STORE": "neo4j",
                    "MCP_VECTOR_STORE": backend,
                    "MCP_SCOPE_DOCUMENT_KEYS": key,
                    f"{backend.upper()}_COLLECTION_PREFIX": prefix,
                },
                cwd=str(Path(__file__).resolve().parents[3]),
            )
            async with Client(parameters, raise_exceptions=True) as client:
                listing = await client.list_tools()
                result = await client.call_tool(
                    "search_evidence", {"query": "orbit", "mode": "hybrid"}
                )
                evidence = EvidenceSearchResult.model_validate(
                    result.structured_content
                )
            assert "search_evidence" in [tool.name for tool in listing.tools]
            assert evidence.status == EvidenceSearchStatus.OK
            assert [hit.document_key for hit in evidence.hits] == [key]
            assert "Orbit mechanics" in evidence.hits[0].snippet
            artifact = write_artifact(
                f"external_mcp_{backend}",
                {"backend": backend, "hit": evidence.hits[0].snippet},
            )
            assert artifact["hit"] == "Orbit mechanics describe satellite motion."
        finally:
            for kind in VectorKind:
                await vectors.delete_collection(kind)
            await vectors.close()
            await store.execute_write("MATCH (node) DETACH DELETE node")
            await store.close()

    @pytest.mark.parametrize("backend", _BACKENDS)
    async def test_document_lifecycle_and_repair(self, backend: str) -> None:  # noqa: PLR0915
        """Search stays current across updates, retirement, rollback, and repair."""
        store = build_test_store()
        vectors = build_vector_store(
            backend, collection_prefix=f"e2e_{uuid4().hex[:12]}"
        )
        embedder = _TopicEmbedder()
        schema = GraphSchema(
            name="external",
            version="1",
            entities=[EntityType(label="ExternalTopic", description="A topic.")],
            relations=[],
        )
        keys = ("external://orbit", "external://forest")
        scope = frozenset(keys)
        await store.connect()
        await store.execute_write("MATCH (node) DETACH DELETE node")
        try:
            graph = await Graph.open(
                schema=schema,
                graph_store=store,
                embedder=embedder,
                extractor=_Extractor(),
                vector_store=vectors,
            )
            await graph.add(
                documents=[
                    _document(keys[0], "Orbit mechanics describe satellite motion."),
                    _document(keys[1], "Forest ecology describes trees and wildlife."),
                ]
            )
            rows = await store.execute_read(
                "MATCH (node) WHERE node.embedding IS NOT NULL "
                "RETURN count(node) AS count"
            )
            assert rows == [{"count": 0}]
            engine = SearchEngine(
                graph_store=store,
                embedder=embedder,
                graph_schema=schema,
                vector_store=vectors,
            )
            retrieved = await engine.search("orbit", CHUNK)
            assert retrieved
            assert isinstance(retrieved[0].item, Chunk)
            assert "Orbit mechanics" in retrieved[0].item.text
            modes = (EvidenceSearchMode.SEMANTIC, EvidenceSearchMode.HYBRID)
            for mode in modes:
                evidence = await search_evidence(
                    store,
                    embedder,
                    "orbit",
                    mode=mode,
                    limit=5,
                    scope=scope,
                    vector_store=vectors,
                )
                assert evidence.status == EvidenceSearchStatus.OK
                assert evidence.hits[0].document_key == keys[0]

            await graph.update(
                keys[0], text="Ocean currents carry heat around the planet."
            )
            await graph.delete_document(keys[1])
            for mode in modes:
                evidence = await search_evidence(
                    store,
                    embedder,
                    "ocean",
                    mode=mode,
                    limit=5,
                    scope=scope,
                    vector_store=vectors,
                )
                assert evidence.status == EvidenceSearchStatus.OK
                assert [hit.document_key for hit in evidence.hits] == [keys[0]]
                assert "Ocean currents" in evidence.hits[0].snippet

            before_rollback = await vectors.list_ids(VectorKind.CHUNK)
            with pytest.raises(RuntimeError, match="requested embedding failure"):
                await graph.add(
                    documents=[_document("external://failed", "orbit rollbackmarker")]
                )
            assert await vectors.list_ids(VectorKind.CHUNK) == before_rollback
            failed_nodes = await store.execute_read(
                "MATCH (node:Chunk) WHERE node.text CONTAINS $marker "
                "RETURN count(node) AS count",
                {"marker": "rollbackmarker"},
            )
            assert failed_nodes == [{"count": 0}]

            await vectors.delete(VectorKind.CHUNK, before_rollback)
            empty = await search_evidence(
                store,
                embedder,
                "ocean",
                mode=EvidenceSearchMode.SEMANTIC,
                limit=5,
                scope=scope,
                vector_store=vectors,
            )
            assert empty.status == EvidenceSearchStatus.NO_MATCH
            repaired = await graph.repair_vectors()
            assert repaired.kinds[VectorKind.CHUNK].upserted > 0
            assert repaired.kinds[VectorKind.CHUNK].failures == []
            restored = await search_evidence(
                store,
                embedder,
                "ocean",
                mode=EvidenceSearchMode.HYBRID,
                limit=5,
                scope=scope,
                vector_store=vectors,
            )
            assert [hit.document_key for hit in restored.hits] == [keys[0]]
            artifact = write_artifact(
                f"external_placement_{backend}",
                {
                    "backend": backend,
                    "graph_embedding_count": 0,
                    "updated_hit": restored.hits[0].snippet,
                    "rollback_vectors_unchanged": True,
                    "repair_upserted": repaired.kinds[VectorKind.CHUNK].upserted,
                },
            )
            assert (
                artifact["updated_hit"]
                == "Ocean currents carry heat around the planet."
            )
        finally:
            for kind in VectorKind:
                await vectors.delete_collection(kind)
            await vectors.close()
            await store.execute_write("MATCH (node) DETACH DELETE node")
            await store.close()
