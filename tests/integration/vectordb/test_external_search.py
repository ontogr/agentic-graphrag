"""Integration coverage for joining external vector hits to live graph nodes."""

from uuid import UUID, uuid4

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.vector_record import Distance, VectorKind, VectorRecord
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.recipes import Recipe
from agrag.retrieval.search_engine import SearchEngine
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS
from tests.integration._fake_vector_store import FakeVectorStore
from tests.integration.retrieval.evidence._corpus import BagOfWordsEmbedder
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
