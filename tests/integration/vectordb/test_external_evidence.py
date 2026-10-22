"""Integration coverage for evidence search over external vector hits."""

from uuid import UUID, uuid4

from agrag.common.data_models.evidence import (
    EvidenceSearchLeg,
    EvidenceSearchMode,
    EvidenceSearchStatus,
)
from agrag.common.data_models.vector_record import Distance, VectorKind, VectorRecord
from agrag.evidence import search_evidence
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


class TestExternalEvidence:
    """External semantic and hybrid hits retain graph visibility rules."""

    async def test_hybrid_reports_fused_store_as_semantic_leg(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """The graph join keeps scoped current passages and identifies the fused leg."""
        vector_store = FakeVectorStore(collection_prefix=uuid4().hex[:8])
        embedder = BagOfWordsEmbedder()
        try:
            await _populate_chunks(evidence_env, vector_store)
            result = await search_evidence(
                evidence_env.store,
                embedder,
                "keep upload activity database",
                mode=EvidenceSearchMode.HYBRID,
                limit=5,
                scope=frozenset({evidence_env.keep}),
                vector_store=vector_store,
            )

            assert result.status is EvidenceSearchStatus.OK
            assert result.hits
            assert all(hit.document_key == evidence_env.keep for hit in result.hits)
            assert all(hit.legs == [EvidenceSearchLeg.SEMANTIC] for hit in result.hits)
        finally:
            await vector_store.close()
