"""Integration coverage for evidence search over external vector hits."""

from collections.abc import Sequence
from uuid import UUID, uuid4

from agrag.common.data_models.evidence import (
    EvidenceSearchLeg,
    EvidenceSearchMode,
    EvidenceSearchStatus,
)
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.vector_record import (
    Distance,
    VectorHit,
    VectorKind,
    VectorRecord,
)
from agrag.evidence import entity_search, search_evidence
from tests.conftest import FAKE_EMBEDDING_DIMENSIONS
from tests.integration._fake_vector_store import FakeVectorStore
from tests.integration.retrieval.evidence._corpus import BagOfWordsEmbedder
from tests.integration.retrieval.evidence.conftest import EvidenceEnv


class _NormalizedHybridStore(FakeVectorStore):
    """Normalize hybrid scores against the selected candidate population."""

    async def hybrid_search(
        self,
        kind: VectorKind,
        vector: Sequence[float],
        text: str,
        *,
        limit: int,
        alpha: float,
        labels: Sequence[str] | None = None,
    ) -> list[VectorHit]:
        hits = await super().hybrid_search(
            kind, vector, text, limit=limit, alpha=alpha, labels=labels
        )
        maximum = max((hit.score for hit in hits), default=1.0)
        return [hit.model_copy(update={"score": hit.score / maximum}) for hit in hits]


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

    async def test_hybrid_entity_search_overfetches_across_selected_labels(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Scoped entities retain globally comparable scores across labels."""
        vector_store = _NormalizedHybridStore(collection_prefix=uuid4().hex[:8])
        embedder = BagOfWordsEmbedder()
        labels = [f"Person{uuid4().hex[:8]}", f"Place{uuid4().hex[:8]}"]
        entity_ids: list[UUID] = []
        try:
            await vector_store.ensure_collection(
                VectorKind.ENTITY,
                dimensions=FAKE_EMBEDDING_DIMENSIONS,
                distance=Distance.COSINE,
            )
            chunk_rows = await evidence_env.store.execute_read(
                "MATCH (document:Document {document_key: $key})"
                "-[part:HAS_PART]->(chunk:Chunk) "
                "WHERE part.invalid_at IS NULL "
                "RETURN chunk.id AS id LIMIT 1",
                {"key": evidence_env.keep},
            )
            [scoped_chunk_id] = [UUID(str(row["id"])) for row in chunk_rows]
            chunk_rows = await evidence_env.store.execute_read(
                "MATCH (document:Document {document_key: $key})"
                "-[part:HAS_PART]->(chunk:Chunk) "
                "WHERE part.invalid_at IS NULL "
                "RETURN chunk.id AS id LIMIT 1",
                {"key": evidence_env.viber},
            )
            [out_of_scope_chunk_id] = [UUID(str(row["id"])) for row in chunk_rows]

            nodes_by_label: dict[str, list[NodeRecord]] = {
                label: [] for label in labels
            }
            mentions: list[RelationRecord] = []
            records: list[VectorRecord] = []
            query_vector = await embedder.embed_one("lighthouse")
            entity_rows = [
                (labels[0], False),
                (labels[0], False),
                (labels[0], False),
                (labels[0], False),
                (labels[0], False),
                (labels[0], True),
                (labels[1], True),
            ]
            for index, (label, in_scope) in enumerate(entity_rows):
                entity_id = uuid4()
                entity_ids.append(entity_id)
                name = (
                    ("Scoped target" if label == labels[0] else "Scoped rival")
                    if in_scope
                    else f"Out of scope {index}"
                )
                nodes_by_label[label].append(
                    NodeRecord(
                        id=entity_id,
                        labels=[label],
                        properties={"name": name},
                    )
                )
                mentions.append(
                    RelationRecord(
                        id=uuid4(),
                        type="MENTIONED_IN",
                        start_id=scoped_chunk_id if in_scope else out_of_scope_chunk_id,
                        end_id=entity_id,
                        properties={},
                    )
                )
                records.append(
                    VectorRecord(
                        id=entity_id,
                        vector=(
                            query_vector
                            if not in_scope
                            else [0.01, 0.01, 0.01, 1.0]
                            if label == labels[0]
                            else [0.0, 0.0, 0.0, 1.0]
                        ),
                        labels=[label],
                        text="lighthouse" if not in_scope else "unrelated",
                    )
                )
            for label, nodes in nodes_by_label.items():
                await evidence_env.store.upsert_nodes(label, nodes)
            await evidence_env.store.upsert_relations(mentions)
            await vector_store.upsert(VectorKind.ENTITY, records)

            result = await entity_search(
                evidence_env.store,
                embedder,
                "lighthouse",
                scope=frozenset({evidence_env.keep}),
                labels=labels,
                limit=1,
                mode=EvidenceSearchMode.HYBRID,
                vector_store=vector_store,
            )

            assert result.status is EvidenceSearchStatus.OK
            assert [hit.name for hit in result.hits] == ["Scoped target"]
            assert result.hits[0].label == labels[0]
            assert result.hits[0].support[0].document_key == evidence_env.keep
        finally:
            if entity_ids:
                await evidence_env.store.execute_write(
                    "MATCH (entity:_Node) WHERE entity.id IN $ids DETACH DELETE entity",
                    {"ids": [str(entity_id) for entity_id in entity_ids]},
                )
            await vector_store.close()

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
