"""Integration tests for Graph.reevaluate() and deletion-triggered pruning.

reevaluate() gains a MATCHES edge between two similar persisted
entities on a real Neo4j instance. The deletion test depends on
Graph.delete_document's lexical-backbone lifecycle closing PART_OF
edges: removing a document orphans its entities, which prunes their
nodes and shrunken clusters while an entity with surviving evidence
from another document stays.
"""

import hashlib
import importlib.util
import unicodedata
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import GENERIC, GraphSchema
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.ingestion.materialize import MatchDecision, write_matches_and_materialize


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _FixedEmbedder(Embedder):
    """Deterministic embedder returning one constant vector."""

    model = "fixed"

    async def dimensions(self) -> int:
        """Return a small fixed dimension."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a constant vector for every text."""
        return [[0.1] * 4 for _ in texts]


class _HashEmbedder(Embedder):
    """Embedder mapping each distinct text to its own one-hot vector."""

    model = "hash"

    async def dimensions(self) -> int:
        """Return the one-hot dimension."""
        return 16

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a stable one-hot vector per distinct text."""
        vectors = []
        for text in texts:
            index = int(hashlib.sha256(text.encode()).hexdigest(), 16) % 16
            vectors.append([1.0 if i == index else 0.0 for i in range(16)])
        return vectors


class _NoopExtractor(Extractor):
    """Extractor emitting no entities."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return no entities or relations for any chunk."""
        return ExtractionResult(entities=[], relations=[], extractor_name="noop")


class _ProbeExtractor(Extractor):
    """Extractor emitting fixed Person mentions keyed by chunk keyword."""

    def __init__(self, probe_names: list[str], survivor_name: str) -> None:
        """Remember which names each keyword's chunks mention."""
        self._probe_names = probe_names
        self._survivor_name = survivor_name

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Mention the probe names matching the chunk's keyword."""
        lowered = chunk.text.lower()
        if "pruneprobe" in lowered:
            names = self._probe_names
        elif "keepprobe" in lowered:
            names = [self._survivor_name]
        else:
            names = []
        mentions = [
            ExtractedEntity(
                chunk_id=chunk.id,  # type: ignore[arg-type]
                label="Person",
                text=name,
                char_start=0,
                char_end=len(name),
            )
            for name in names
        ]
        return ExtractionResult(entities=mentions, relations=[], extractor_name="probe")


def _content_hash(text: str) -> str:
    """Hash text the same way the inline walk and update() do."""
    return hashlib.sha256(
        unicodedata.normalize("NFKC", text).encode("utf-8")
    ).hexdigest()


def _document(key: str, text: str) -> Document:
    """Build a prose Document carrying an explicit stable key."""
    normalized = unicodedata.normalize("NFKC", text)
    return Document(
        text=normalized,
        title="reevaluate",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=_content_hash(normalized),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(normalized),
        line_count=normalized.count("\n") + 1,
    )


async def _entity_ids_by_name(store: GraphStore, names: list[str]) -> dict[str, UUID]:
    """Return persisted Person ids keyed by name."""
    rows = await store.execute_read(
        "MATCH (e:Person) WHERE e.name IN $names RETURN e.id AS id, e.name AS name",
        {"names": names},
    )
    return {row["name"]: UUID(str(row["id"])) for row in rows}


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestReevaluateIntegration:
    """reevaluate() on a real database gains a missing match edge."""

    async def test_reevaluate_gains_new_edge(self) -> None:
        """Two similar entities with no edge gain one plus a cluster."""
        store = build_graph_store("neo4j")
        await store.connect()
        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=_FixedEmbedder(),
            extractor=_NoopExtractor(),
        )
        suffix = uuid4().hex[:8]
        first_name, second_name = f"Reeval Quasar {suffix}", f"Reeval Nebula {suffix}"
        first = Entity(id=uuid4(), label="Person", name=first_name)
        second = Entity(id=uuid4(), label="Person", name=second_name)
        try:
            await store.upsert_nodes(
                "Person", [first.to_node_record(), second.to_node_record()]
            )

            report = await graph.reevaluate([first.id, second.id])

            assert report.entities_reevaluated == [first.id, second.id]
            assert len(report.matches_added) == 1
            assert {
                report.matches_added[0].entity_a_id,
                report.matches_added[0].entity_b_id,
            } == {first.id, second.id}
            assert report.matches_removed == []
            assert report.unchanged_count == 0
            rows = await store.execute_read(
                "MATCH (a:Person)-[match:MATCHES]->(b:Person) "
                "WHERE a.id IN $ids AND b.id IN $ids "
                "MATCH (a)-[:RESOLVED_AS]->(resolved:ResolvedEntity) "
                "MATCH (b)-[:RESOLVED_AS]->(resolved) "
                "RETURN resolved.id AS resolved_id",
                {"ids": [str(first.id), str(second.id)]},
            )
            assert len(rows) == 1
        finally:
            await store.execute_write(
                "MATCH (e:Person) WHERE e.id IN $ids DETACH DELETE e",
                {"ids": [str(first.id), str(second.id)]},
            )
            await store.execute_write(
                "MATCH (node:ResolvedEntity) "
                "WHERE any(member_id IN node.member_ids WHERE member_id IN $ids) "
                "DETACH DELETE node",
                {"ids": [str(first.id), str(second.id)]},
            )
            await store.close()


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestDeletionPruningIntegration:
    """delete_document() prunes entities left with no open evidence."""

    async def test_delete_document_prunes_orphaned_cluster(self) -> None:
        """A 3-member cluster collapses while another document's member lives."""
        store = build_graph_store("neo4j")
        await store.connect()
        suffix = uuid4().hex[:8]
        probe_names = [
            f"Pruneprobe Quasar {suffix}",
            f"Pruneprobe Nebula {suffix}",
            f"Pruneprobe Pulsar {suffix}",
        ]
        survivor_name = f"Keepprobe Galaxy {suffix}"
        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=_HashEmbedder(),
            extractor=_ProbeExtractor(probe_names, survivor_name),
        )
        doc_key = f"pruneprobe://{suffix}-doc"
        keep_key = f"pruneprobe://{suffix}-keep"
        try:
            await graph.add(
                documents=[
                    _document(doc_key, "pruneprobe orphan collapse. " * 60),
                    _document(keep_key, "keepprobe survivor stays. " * 60),
                ]
            )
            by_name = await _entity_ids_by_name(store, [*probe_names, survivor_name])
            assert set(by_name) == {*probe_names, survivor_name}
            members = [
                Entity(id=by_name[name], label="Person", name=name)
                for name in probe_names
            ]
            now = datetime.now(UTC)
            await write_matches_and_materialize(
                [
                    MatchDecision(
                        entity_a_id=members[0].id,
                        entity_b_id=members[1].id,
                        comparator="FuzzyMatch",
                        decided_at=now,
                    ),
                    MatchDecision(
                        entity_a_id=members[1].id,
                        entity_b_id=members[2].id,
                        comparator="FuzzyMatch",
                        decided_at=now,
                    ),
                ],
                graph_store=store,
                schema=GENERIC,
                members=members,
            )

            deleted = await graph.delete_document(doc_key)

            assert deleted.no_op is False
            assert deleted.chunks_closed >= 1
            rows = await store.execute_read(
                "MATCH (e:Person) WHERE e.id IN $ids RETURN count(e) AS n",
                {"ids": [str(member.id) for member in members]},
            )
            assert rows == [{"n": 0}]
            rows = await store.execute_read(
                "MATCH (node:ResolvedEntity) "
                "WHERE any(member_id IN node.member_ids WHERE member_id IN $ids) "
                "RETURN count(node) AS n",
                {"ids": [str(member.id) for member in members]},
            )
            assert rows == [{"n": 0}]
            rows = await store.execute_read(
                "MATCH (e:Person) WHERE e.id = $id RETURN count(e) AS n",
                {"id": str(by_name[survivor_name])},
            )
            assert rows == [{"n": 1}]
            rows = await store.execute_read(
                "MATCH (:Document {document_key: $key})-[r:PART_OF]->(:Chunk) "
                "WHERE r.invalid_at IS NULL RETURN count(r) AS open_edges",
                {"key": keep_key},
            )
            assert rows[0]["open_edges"] >= 1
        finally:
            await store.execute_write(
                "MATCH (d:Document) WHERE d.document_key IN $keys "
                "OPTIONAL MATCH (d)-[:PART_OF]->(c:Chunk) "
                "DETACH DELETE d, c",
                {"keys": [doc_key, keep_key]},
            )
            await store.execute_write(
                "MATCH (e:Person) WHERE e.name IN $names DETACH DELETE e",
                {"names": [*probe_names, survivor_name]},
            )
            await store.execute_write(
                "MATCH (a:_AgragMergeAlias) WHERE a.merge_key IN $merge_keys "
                "DETACH DELETE a",
                {
                    "merge_keys": [
                        f"Person:{name.strip().casefold()}"
                        for name in [*probe_names, survivor_name]
                    ]
                },
            )
            await store.close()
