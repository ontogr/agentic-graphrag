"""Integration coverage for joining external vector hits to live graph nodes."""

from uuid import UUID, uuid4

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.evidence import EvidenceSearchMode, EvidenceSearchStatus
from agrag.common.data_models.graph_record import RelationRecord
from agrag.common.data_models.vector_record import Distance, VectorKind, VectorRecord
from agrag.evidence import entity_search, search_evidence
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

    async def test_entity_search_uses_external_vector_store(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Entity search joins external hits without native vector indexes."""
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
            chunk_rows = await evidence_env.store.execute_read(
                "MATCH (document:Document {document_key: $key})"
                "-[part:HAS_PART]->(chunk:Chunk) "
                "WHERE part.invalid_at IS NULL AND chunk.text CONTAINS 'keeper' "
                "RETURN chunk.id AS id LIMIT 1",
                {"key": evidence_env.harbor},
            )
            [chunk_id] = [UUID(str(row["id"])) for row in chunk_rows]
            await evidence_env.store.upsert_relations(
                [
                    RelationRecord(
                        id=uuid4(),
                        type="MENTIONED_IN",
                        start_id=chunk_id,
                        end_id=entity.id,
                        properties={},
                    )
                ]
            )

            result = await entity_search(
                evidence_env.store,
                embedder,
                "Lighthouse Keeper",
                scope=frozenset({evidence_env.harbor}),
                labels=[label],
                mode=EvidenceSearchMode.SEMANTIC,
                vector_store=vector_store,
            )

            assert result.status is EvidenceSearchStatus.OK
            assert [hit.entity_id for hit in result.hits] == [str(entity.id)]
            assert result.hits[0].name == "Lighthouse Keeper"
            assert result.hits[0].support[0].document_key == evidence_env.harbor
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

            result = await search_evidence(
                evidence_env.store,
                embedder,
                "retirement probe",
                mode=EvidenceSearchMode.SEMANTIC,
                limit=1,
                scope=frozenset({evidence_env.harbor}),
                vector_store=vector_store,
            )

            assert result.status is EvidenceSearchStatus.OK
            assert len(result.hits) == 1
            assert result.hits[0].document_key == evidence_env.harbor
            assert result.hits[0].content_hash == sha256_of(HARBOR_TEXT_V2)
        finally:
            await vector_store.close()

    async def test_document_scope_survives_orphan_overfetch(
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

            result = await search_evidence(
                evidence_env.store,
                embedder,
                "keep upload activity database",
                mode=EvidenceSearchMode.SEMANTIC,
                limit=5,
                scope=frozenset({evidence_env.keep}),
                vector_store=vector_store,
            )

            assert result.status is EvidenceSearchStatus.OK
            assert result.hits
            assert len(result.hits) <= 5
            assert all(hit.document_key == evidence_env.keep for hit in result.hits)
        finally:
            await vector_store.close()
