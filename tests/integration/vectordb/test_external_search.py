"""Integration coverage for joining external vector hits to live graph nodes."""

from uuid import UUID, uuid4

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.vector_record import Distance, VectorKind, VectorRecord
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.recipes import Recipe
from agrag.retrieval.search_engine import SearchEngine
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS
from tests.integration._fake_vector_store import FakeVectorStore
from tests.integration.retrieval.evidence._corpus import (
    HARBOR_TEXT_V2,
    BagOfWordsEmbedder,
    sha256_of,
)
from tests.integration.retrieval.evidence.conftest import EvidenceEnv


async def _populate_chunks(env: EvidenceEnv, vector_store: FakeVectorStore) -> None:
    """Copy this fixture's chunks into the external test collection."""
    await vector_store.ensure_collection(
        VectorKind.CHUNK,
        dimensions=FAKE_EMBEDDING_DIMENSIONS,
        distance=Distance.COSINE,
    )
    rows = await env.store.execute_read(
        "MATCH (document:Document)-[:HAS_PART]->(chunk:Chunk) "
        "WHERE document.document_key STARTS WITH $prefix "
        "AND chunk.embedding IS NOT NULL "
        "RETURN chunk.id AS id, chunk.embedding AS vector, chunk.text AS text",
        {"prefix": env.key("")},
    )
    await vector_store.upsert(
        VectorKind.CHUNK,
        [
            VectorRecord(
                id=UUID(str(row["id"])),
                vector=list(row["vector"]),
                labels=["Chunk"],
                text=row["text"],
            )
            for row in rows
        ],
    )


class TestExternalSearch:
    """External search filters stale vector ids and fetches beyond orphans."""

    async def test_find_entity_uses_external_vector_store(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Named entity lookup uses external placement without native indexes."""
        vector_store = FakeVectorStore(collection_prefix=uuid4().hex[:8])
        embedder = BagOfWordsEmbedder()
        label = f"ExternalEntity{uuid4().hex[:8]}"
        entity = Entity(id=uuid4(), label=label, name="Lighthouse Keeper")
        try:
            await vector_store.ensure_collection(
                VectorKind.ENTITY,
                dimensions=FAKE_EMBEDDING_DIMENSIONS,
                distance=Distance.COSINE,
            )
            await evidence_env.store.upsert_nodes(label, [entity.to_node_record()])
            await vector_store.upsert(
                VectorKind.ENTITY,
                [
                    VectorRecord(
                        id=entity.id,
                        vector=await embedder.embed_one(entity.embedding_text),
                        labels=[label],
                        text=entity.embedding_text,
                    )
                ],
            )
            engine = SearchEngine(
                graph_store=evidence_env.store,
                embedder=embedder,
                graph_schema=GraphSchema(
                    name="external-search",
                    version="1",
                    entities=[EntityType(label=label, description="A test entity.")],
                    relations=[],
                ),
                vector_store=vector_store,
            )

            result = await engine.find_entity("Lighthouse Keeper")

            assert result is not None
            assert isinstance(result.item, Entity)
            assert result.item.id == entity.id
            assert result.item.name == "Lighthouse Keeper"
        finally:
            await evidence_env.store.execute_write(
                "MATCH (entity:_Node {id: $id}) DETACH DELETE entity",
                {"id": str(entity.id)},
            )
            await vector_store.close()

    async def test_retired_chunks_do_not_consume_the_external_fetch_limit(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Current chunks fill the result after retired hits are filtered."""
        vector_store = FakeVectorStore(collection_prefix=uuid4().hex[:8])
        embedder = BagOfWordsEmbedder()
        try:
            await _populate_chunks(evidence_env, vector_store)
            old_rows = await evidence_env.store.execute_read(
                "MATCH (document:Document {document_key: $key})"
                "-[part:HAS_PART]->(chunk:Chunk) "
                "WHERE part.invalid_at IS NULL "
                "RETURN chunk.id AS id, chunk.text AS text",
                {"key": evidence_env.harbor},
            )
            assert len(old_rows) >= 4

            await evidence_env.graph.update(evidence_env.harbor, text=HARBOR_TEXT_V2)
            await _populate_chunks(evidence_env, vector_store)
            retirement_probe = [0.01] * FAKE_EMBEDDING_DIMENSIONS
            await vector_store.upsert(
                VectorKind.CHUNK,
                [
                    VectorRecord(
                        id=UUID(str(row["id"])),
                        vector=retirement_probe,
                        labels=["Chunk"],
                        text="retirement probe",
                    )
                    for row in old_rows
                ],
            )
            document_rows = await evidence_env.store.execute_read(
                "MATCH (document:Document {document_key: $key}) "
                "RETURN document.id AS id",
                {"key": evidence_env.harbor},
            )
            document_id = str(document_rows[0]["id"])
            engine = SearchEngine(
                graph_store=evidence_env.store,
                embedder=embedder,
                vector_store=vector_store,
            )

            results = await engine.search(
                "retirement probe",
                Recipe(methods=["chunk"], limit=1),
                filters=SearchFilters(document_ids=[document_id]),
            )

            assert len(results) == 1
            assert results[0].item.content_hash == sha256_of(HARBOR_TEXT_V2)
        finally:
            await vector_store.close()

    async def test_document_filter_survives_orphan_overfetch(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Fifty top-ranked orphans do not hide in-scope chunks."""
        vector_store = FakeVectorStore(collection_prefix=uuid4().hex[:8])
        embedder = BagOfWordsEmbedder()
        try:
            await _populate_chunks(evidence_env, vector_store)
            query_vector = await embedder.embed_one("keep upload activity database")
            for _ in range(50):
                vector_store.inject_orphan(
                    VectorKind.CHUNK, uuid4(), list(query_vector)
                )
            document_rows = await evidence_env.store.execute_read(
                "MATCH (document:Document {document_key: $key}) "
                "RETURN document.id AS id",
                {"key": evidence_env.keep},
            )
            assert document_rows
            document_id = str(document_rows[0]["id"])

            engine = SearchEngine(
                graph_store=evidence_env.store,
                embedder=embedder,
                vector_store=vector_store,
            )
            results = await engine.search(
                "keep upload activity database",
                Recipe(methods=["chunk"], limit=5),
                filters=SearchFilters(document_ids=[document_id]),
            )

            assert results
            assert len(results) <= 5
            assert all(isinstance(result.item, Chunk) for result in results)
            assert all(
                result.item.document_id == UUID(document_id) for result in results
            )
        finally:
            await vector_store.close()
