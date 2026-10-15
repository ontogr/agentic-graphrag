"""Purge a document's content and evidence against a real Neo4j instance.

A purge hard-deletes every version of one document. Afterwards its text is gone
from every node property, its evidence and discovery find nothing, and entities
and relations that lost their last evidence are removed. The Document node and its
activation records remain as a tombstone, and other documents are untouched.
"""

import hashlib
import unicodedata
from uuid import uuid4

from agrag.chunking import Chunker
from agrag.common.data_models.candidate import CandidateRecord
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    DocumentSection,
    SourceFormat,
    Unit,
    UnitKind,
)
from agrag.common.data_models.evidence import DiscoveryMode, FetchStatus
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.provenance import BoundingBox, PageSpan
from agrag.evidence import discover, fetch
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from tests.integration.retrieval.evidence._corpus import BagOfWordsEmbedder


class _ProbeGraphExtractor(Extractor):
    """Mention a person and an organization, linked, in chunks with a trigger word.

    With ``describe`` set, a chunk naming the probe gives its mentions a description
    and proposes a pending candidate, so the purge must clear that text too.
    """

    def __init__(
        self, name: str, triggers: tuple[str, ...], *, describe: bool = False
    ) -> None:
        """Remember the entity names built from ``name`` and the trigger words."""
        self._name = name
        self._person = f"Zzxqy {name}"
        self._organization = f"Zzxqy Harbor {name}"
        self._triggers = triggers
        self._describe = describe

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Mention the person, the organization and their link when triggered."""
        if not any(trigger in chunk.text for trigger in self._triggers):
            return ExtractionResult(entities=[], relations=[], extractor_name="probe")
        properties: dict[str, object] = {}
        candidates: list[CandidateRecord] = []
        if self._describe and self._name in chunk.text:
            properties = {"description": f"{self._name} dredging ledger"}
            candidates = [
                CandidateRecord(
                    kind="entity",
                    label="Person",
                    text=f"{self._name} candidate",
                    confidence=0.5,
                    reason="entity_band",
                    chunk_id=chunk.id,  # type: ignore[arg-type]
                )
            ]
        entities = [
            ExtractedEntity(
                chunk_id=chunk.id,  # type: ignore[arg-type]
                label="Person",
                text=self._person,
                char_start=0,
                char_end=len(self._person),
                properties=properties,
            ),
            ExtractedEntity(
                chunk_id=chunk.id,  # type: ignore[arg-type]
                label="Organization",
                text=self._organization,
                char_start=0,
                char_end=len(self._organization),
                properties=properties,
            ),
        ]
        relations = [
            ExtractedRelation(
                chunk_id=chunk.id,  # type: ignore[arg-type]
                label="WORKS_FOR",
                source_index=0,
                target_index=1,
            )
        ]
        return ExtractionResult(
            entities=entities,
            relations=relations,
            candidates=candidates,
            extractor_name="probe",
        )


def _content_hash(text: str) -> str:
    """Hash text the same way the document loaders do."""
    return hashlib.sha256(
        unicodedata.normalize("NFKC", text).encode("utf-8")
    ).hexdigest()


def _prose_document(key: str, text: str) -> Document:
    """Build a prose document with no sections."""
    normalized = unicodedata.normalize("NFKC", text)
    return Document(
        text=normalized,
        title="purge",
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


def _structured_document(key: str, probe: str) -> Document:
    """Build a document with a heading, a paragraph and a captioned table.

    The section produces Section, Chunk and Table nodes, so a purge must remove
    every structure label.
    """
    span = PageSpan(page_no=1, bbox=BoundingBox(x0=0, y0=0, x1=1, y1=1))
    paragraph = f"The {probe} paragraph records the tide gauge readings."
    caption = f"The {probe} caption lists the pier costs."
    rows = [["item", "cost"], [f"{probe} pier", "12"]]
    text = f"{paragraph}\n\n{caption}"
    section = DocumentSection(
        heading=f"{probe} heading",
        depth=1,
        units=[
            Unit(kind=UnitKind.PARAGRAPH, text=paragraph, pages=[span]),
            Unit(
                kind=UnitKind.TABLE,
                text=caption,
                caption=caption,
                rows=rows,
                header_rows=1,
                pages=[span],
            ),
        ],
    )
    return Document(
        text=text,
        title="structured",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=_content_hash(text),
        loader_name="inline",
        encoding="utf-8",
        char_count=len(text),
        line_count=text.count("\n") + 1,
        sections=[section],
    )


async def _open_graph(
    store: GraphStore,
    name: str,
    triggers: tuple[str, ...],
    *,
    describe: bool = False,
) -> Graph:
    """Open a graph whose extractor links the probe entities in triggered chunks."""
    graph = await Graph.open(
        schema=DEFAULT_SCHEMA,
        graph_store=store,
        embedder=BagOfWordsEmbedder(),
        extractor=_ProbeGraphExtractor(name, triggers, describe=describe),
        chunker=Chunker(size=60),
    )
    await store.execute_read("CALL db.awaitIndexes(60)")
    return graph


_HOLDS_NEEDLE = (
    "any(k IN keys({var}) WHERE "
    "({var}[k] IS :: STRING AND {var}[k] CONTAINS $needle) OR "
    "({var}[k] IS :: LIST<STRING> AND any(x IN {var}[k] WHERE x CONTAINS $needle)))"
)


async def _text_hits(store: GraphStore, needle: str) -> int:
    """Count nodes and relations with a string property, or a list, holding needle."""
    nodes = await store.execute_read(
        f"MATCH (n) WHERE {_HOLDS_NEEDLE.format(var='n')} RETURN count(n) AS hits",
        {"needle": needle},
    )
    relations = await store.execute_read(
        "MATCH ()-[r]->() "
        f"WHERE {_HOLDS_NEEDLE.format(var='r')} RETURN count(r) AS hits",
        {"needle": needle},
    )
    return nodes[0]["hits"] + relations[0]["hits"]


async def _structure_count(store: GraphStore, key: str) -> int:
    """Count the chunk, section, table and figure nodes of every version."""
    rows = await store.execute_read(
        "MATCH (n) WHERE n.document_id = $document_id "
        "AND (n:Chunk OR n:Section OR n:Table OR n:Figure) "
        "RETURN count(n) AS nodes",
        {"document_id": str(Document.node_id_for(document_key=key))},
    )
    return rows[0]["nodes"]


async def _chunk_ids(store: GraphStore, key: str) -> set[str]:
    """Return the ids of every chunk of one document, in any version."""
    rows = await store.execute_read(
        "MATCH (c:Chunk {document_id: $document_id}) RETURN c.id AS id",
        {"document_id": str(Document.node_id_for(document_key=key))},
    )
    return {str(row["id"]) for row in rows}


async def _works_for_sources(store: GraphStore, name: str) -> list[set[str]]:
    """Return the source chunk ids of each WORKS_FOR relation the probe names."""
    rows = await store.execute_read(
        "MATCH (:Person {name: $person})-[r:WORKS_FOR]->"
        "(:Organization {name: $organization}) "
        "RETURN r.source_chunk_ids AS sources",
        {"person": f"Zzxqy {name}", "organization": f"Zzxqy Harbor {name}"},
    )
    return [set(row["sources"]) for row in rows]


async def _discovered_ids(store: GraphStore, key: str, probe: str) -> list[str]:
    """Return the evidence ids that lexical discovery finds for the probe."""
    found = await discover(
        store,
        BagOfWordsEmbedder(),
        probe,
        mode=DiscoveryMode.LEXICAL,
        limit=10,
        scope=frozenset({key}),
    )
    return [hit.evidence_id for hit in found.hits]


async def _purge_activations(store: GraphStore, key: str) -> int:
    """Count the purge activation records of one document."""
    rows = await store.execute_read(
        "MATCH (:Document {document_key: $key})-[:HAS_ACTIVATION]->"
        "(a:DocumentActivation {verb: 'purge'}) RETURN count(a) AS purges",
        {"key": key},
    )
    return rows[0]["purges"]


async def _cleanup(store: GraphStore, keys: list[str], name: str) -> None:
    """Delete the nodes one test wrote under its document keys and probe name."""
    await store.execute_write(
        "MATCH (d:Document) WHERE d.document_key IN $keys "
        "OPTIONAL MATCH (d)-[:HAS_ACTIVATION]->(a) "
        "OPTIONAL MATCH (d)-[:HAS_PART]->(c) "
        "DETACH DELETE a, c, d",
        {"keys": keys},
    )
    await store.execute_write(
        "MATCH (e) WHERE (e:Person OR e:Organization) "
        "AND e.name STARTS WITH 'Zzxqy ' AND e.name CONTAINS $name "
        "DETACH DELETE e",
        {"name": name},
    )
    await store.execute_write(
        "MATCH (a:_MergeAlias) WHERE a.merge_key CONTAINS $name DETACH DELETE a",
        {"name": name.casefold()},
    )


class TestDocumentPurge:
    """Purge removes every version's content and evidence and nothing else."""

    async def test_oversized_purge_is_rejected_before_cutover(self) -> None:
        """Oversized stored content is rejected without creating a purge record."""
        store = build_graph_store("neo4j")
        await store.connect()
        probe = f"purgeprobe{uuid4().hex[:8]}"
        key = f"purge://{uuid4().hex}"
        graph = await _open_graph(store, probe, (probe,))
        try:
            await graph.add(documents=[_prose_document(key, f"{probe} record.")])
            document_id = str(Document.node_id_for(document_key=key))
            await store.execute_write(
                "UNWIND range(1, 10001) AS index "
                "CREATE (:_Node:Chunk {id: $prefix + toString(index), "
                "document_id: $document_id})",
                {"prefix": f"oversized-{uuid4().hex}-", "document_id": document_id},
            )

            try:
                await graph.purge_document(key)
            except ValueError as error:
                assert "10000" in str(error)
            else:
                raise AssertionError("oversized purge was not rejected")

            assert await _purge_activations(store, key) == 0
            jobs = await store.execute_read(
                "MATCH (job:CutoverJob {document_key: $key, verb: 'purge_document'}) "
                "RETURN count(job) AS count",
                {"key": key},
            )
            assert jobs[0]["count"] == 0
        finally:
            await store.execute_write(
                "MATCH (n:Chunk {document_id: $document_id}) "
                "WHERE n.id STARTS WITH 'oversized-' DETACH DELETE n",
                {"document_id": str(Document.node_id_for(document_key=key))},
            )
            await _cleanup(store, [key], probe)
            await store.close()

    async def test_purge_removes_every_version_text_and_evidence(self) -> None:
        """No stored text survives, linked entities go, and evidence is gone."""
        store = build_graph_store("neo4j")
        await store.connect()
        probe = f"purgeprobe{uuid4().hex[:8]}"
        key = f"purge://{uuid4().hex}"
        graph = await _open_graph(store, probe, (probe,))
        try:
            await graph.add(documents=[_structured_document(key, probe)])
            first_ids = await _discovered_ids(store, key, probe)
            assert await _works_for_sources(store, probe)
            await graph.add(
                documents=[_prose_document(key, f"{probe} revised tide gauge record.")]
            )
            second_ids = await _discovered_ids(store, key, probe)
            assert first_ids and second_ids
            assert await _structure_count(store, key) > 0
            assert await _text_hits(store, probe) > 0
            out_of_scope = await fetch(
                store, first_ids + second_ids, scope=frozenset(), max_chars=500
            )
            assert {outcome.status for outcome in out_of_scope} == {
                FetchStatus.UNAVAILABLE
            }

            purged = await graph.purge_document(key)

            assert purged.no_op is False
            assert await _structure_count(store, key) == 0
            assert await _text_hits(store, probe) == 0
            assert await _works_for_sources(store, probe) == []
            outcomes = await fetch(
                store,
                first_ids + second_ids,
                scope=frozenset({key}),
                max_chars=500,
            )
            assert {outcome.status for outcome in outcomes} == {FetchStatus.UNAVAILABLE}
            assert await _discovered_ids(store, key, probe) == []
            assert await _purge_activations(store, key) == 1
        finally:
            await _cleanup(store, [key], probe)
            await store.close()

    async def test_purge_after_soft_delete_removes_retained_content(self) -> None:
        """A soft-deleted document reads as unavailable, and its purge still runs."""
        store = build_graph_store("neo4j")
        await store.connect()
        probe = f"purgeprobe{uuid4().hex[:8]}"
        key = f"purge://{uuid4().hex}"
        graph = await _open_graph(store, probe, (probe,))
        try:
            await graph.add(documents=[_structured_document(key, probe)])
            evidence_ids = await _discovered_ids(store, key, probe)
            assert evidence_ids
            assert await _structure_count(store, key) > 0

            await graph.delete_document(key)
            after_delete = await fetch(
                store, evidence_ids, scope=frozenset({key}), max_chars=500
            )
            assert {outcome.status for outcome in after_delete} == {
                FetchStatus.UNAVAILABLE
            }
            assert await _structure_count(store, key) > 0

            purged = await graph.purge_document(key)

            assert purged.no_op is False
            assert await _structure_count(store, key) == 0
            assert await _purge_activations(store, key) == 1
        finally:
            await _cleanup(store, [key], probe)
            await store.close()

    async def test_repeat_purge_is_a_no_op(self) -> None:
        """A second purge of the same key changes nothing and writes no record."""
        store = build_graph_store("neo4j")
        await store.connect()
        probe = f"purgeprobe{uuid4().hex[:8]}"
        key = f"purge://{uuid4().hex}"
        graph = await _open_graph(store, probe, (probe,))
        try:
            await graph.add(documents=[_structured_document(key, probe)])
            await graph.purge_document(key)

            again = await graph.purge_document(key)

            assert again.no_op is True
            assert await _purge_activations(store, key) == 1
            assert await _text_hits(store, probe) == 0
        finally:
            await _cleanup(store, [key], probe)
            await store.close()

    async def test_purge_keeps_other_documents_and_their_shared_evidence(self) -> None:
        """Another document keeps its text, its evidence and its relation sources."""
        store = build_graph_store("neo4j")
        await store.connect()
        probe = f"purgeprobe{uuid4().hex[:8]}"
        other_probe = f"keepprobe{uuid4().hex[:8]}"
        key = f"purge://{uuid4().hex}"
        other_key = f"purge://{uuid4().hex}"
        graph = await _open_graph(store, probe, (probe, other_probe))
        try:
            await graph.add(
                documents=[
                    _structured_document(key, probe),
                    _prose_document(other_key, f"{other_probe} harbor log entry."),
                ]
            )
            other_ids = await _discovered_ids(store, other_key, other_probe)
            other_chunks = await _chunk_ids(store, other_key)
            assert other_ids
            assert any(
                other_chunks <= sources
                for sources in await _works_for_sources(store, probe)
            )

            await graph.purge_document(key)

            outcomes = await fetch(
                store, other_ids, scope=frozenset({other_key}), max_chars=500
            )
            assert {outcome.status for outcome in outcomes} == {FetchStatus.OK}
            assert await _discovered_ids(store, other_key, other_probe) == other_ids
            assert await _text_hits(store, other_probe) > 0
            assert await _works_for_sources(store, probe) == [other_chunks]
        finally:
            await _cleanup(store, [key, other_key], probe)
            await store.close()

    async def test_purge_cleans_relation_citing_document_chunks_without_mentions(
        self,
    ) -> None:
        """A relation that cites purged chunks goes even if no chunk mentions its ends.

        The relation's endpoints lost their mention edges from the document, so the
        purge reaches the relation only through its ``source_chunk_ids``. The
        relation goes, and its endpoints, which no open evidence still supports,
        are pruned with it.
        """
        store = build_graph_store("neo4j")
        await store.connect()
        probe = f"purgeprobe{uuid4().hex[:8]}"
        key = f"purge://{uuid4().hex}"
        graph = await _open_graph(store, probe, (probe,))
        try:
            await graph.add(documents=[_structured_document(key, probe)])
            chunk_ids = await _chunk_ids(store, key)
            assert await _works_for_sources(store, probe)
            await store.execute_write(
                "MATCH (c:Chunk {document_id: $document_id})-[m:MENTIONED_IN]->() "
                "DELETE m",
                {"document_id": str(Document.node_id_for(document_key=key))},
            )
            assert await _works_for_sources(store, probe)

            purged = await graph.purge_document(key)

            assert purged.no_op is False
            assert await _works_for_sources(store, probe) == []
            stale = await store.execute_read(
                "MATCH ()-[r]->() WHERE any(cid IN r.source_chunk_ids "
                "WHERE cid IN $chunk_ids) RETURN count(r) AS stale",
                {"chunk_ids": sorted(chunk_ids)},
            )
            assert stale[0]["stale"] == 0
            assert await _text_hits(store, probe) == 0
        finally:
            await _cleanup(store, [key], probe)
            await store.close()

    async def test_purge_leaves_no_document_text_in_any_property(self) -> None:
        """A search over every node and relation property finds none of the text.

        The document's chunk text, section heading, table cell, entity description
        and pending candidate all carry the probe or a distinct phrase. After the
        purge none of them is found on any node or relation.
        """
        store = build_graph_store("neo4j")
        await store.connect()
        probe = f"purgeprobe{uuid4().hex[:8]}"
        phrase = f"{probe} dredging ledger"
        key = f"purge://{uuid4().hex}"
        graph = await _open_graph(store, probe, (probe,), describe=True)
        try:
            await graph.add(documents=[_structured_document(key, probe)])
            assert await _text_hits(store, probe) > 0
            assert await _text_hits(store, phrase) > 0
            pending = await store.execute_read(
                "MATCH (n:Candidate) WHERE n.text CONTAINS $probe RETURN count(n) AS n",
                {"probe": probe},
            )
            assert pending[0]["n"] > 0

            await graph.purge_document(key)

            assert await _text_hits(store, probe) == 0
            assert await _text_hits(store, phrase) == 0
            assert await _text_hits(store, f"{probe} heading") == 0
            assert await _text_hits(store, f"{probe} pier") == 0
        finally:
            await _cleanup(store, [key], probe)
            await store.close()

    async def test_purge_removes_pending_candidates_but_preserves_reviewed_ones(
        self,
    ) -> None:
        """Purge removes pending candidates but retains approved and rejected ones."""
        store = build_graph_store("neo4j")
        await store.connect()
        probe = f"purgeprobe{uuid4().hex[:8]}"
        key = f"purge://{uuid4().hex}"
        graph = await _open_graph(store, probe, (probe,), describe=True)
        try:
            await graph.add(documents=[_structured_document(key, probe)])
            chunk_ids = await _chunk_ids(store, key)
            assert chunk_ids
            chunk_id = next(iter(chunk_ids))
            reviewed = [
                CandidateRecord(
                    kind="entity",
                    label="Person",
                    text=f"{probe} approved",
                    confidence=0.8,
                    reason="entity_band",
                    chunk_id=chunk_id,
                    state="approved",
                ),
                CandidateRecord(
                    kind="entity",
                    label="Person",
                    text=f"{probe} rejected",
                    confidence=0.8,
                    reason="entity_band",
                    chunk_id=chunk_id,
                    state="rejected",
                ),
            ]
            written = await store.upsert_candidates(reviewed)
            assert not written.failures
            candidate_ids = [str(record.id) for record in reviewed]
            pending = await store.execute_read(
                "MATCH (candidate:Candidate) "
                "WHERE candidate.text = $text AND candidate.state = 'pending' "
                "RETURN candidate.id AS id",
                {"text": f"{probe} candidate"},
            )
            assert len(pending) == 1

            await graph.purge_document(key)

            survivors = await store.execute_read(
                "MATCH (candidate:Candidate) WHERE candidate.id IN $ids "
                "RETURN candidate.id AS id, candidate.state AS state",
                {"ids": candidate_ids},
            )
            assert {row["id"]: row["state"] for row in survivors} == {
                str(reviewed[0].id): "approved",
                str(reviewed[1].id): "rejected",
            }
            removed_pending = await store.execute_read(
                "MATCH (candidate:Candidate {id: $id}) RETURN count(candidate) AS n",
                {"id": pending[0]["id"]},
            )
            assert removed_pending[0]["n"] == 0
        finally:
            await _cleanup(store, [key], probe)
            await store.close()

    async def test_purge_clears_description_of_entity_another_document_shares(
        self,
    ) -> None:
        """An entity another document still cites loses the purged description.

        Both documents mention the same person and organization. Only the purged
        document describes them, so the shared entities must keep their evidence
        and drop the description it contributed.
        """
        store = build_graph_store("neo4j")
        await store.connect()
        probe = f"purgeprobe{uuid4().hex[:8]}"
        other_probe = f"keepprobe{uuid4().hex[:8]}"
        phrase = f"{probe} dredging ledger"
        key = f"purge://{uuid4().hex}"
        other_key = f"purge://{uuid4().hex}"
        graph = await _open_graph(store, probe, (probe, other_probe), describe=True)
        try:
            await graph.add(documents=[_structured_document(key, probe)])
            await graph.add(
                documents=[_prose_document(other_key, f"{other_probe} harbor log.")]
            )
            assert await _text_hits(store, phrase) > 0
            assert await _works_for_sources(store, probe)

            await graph.purge_document(key)

            assert await _works_for_sources(store, probe)
            assert await _text_hits(store, phrase) == 0
            assert await _text_hits(store, probe) > 0
        finally:
            await _cleanup(store, [key, other_key], probe)
            await store.close()
