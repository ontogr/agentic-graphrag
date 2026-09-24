"""E2E entity resolution and merge as a user runs them, on real Neo4j and Qdrant.

Three documents mention the same organization and person under different
surface names, with conflicting property values and descriptions. A fake
embedder decides which names mean the same thing, so no LLM runs: same-thing
pairs score 1.0 and every other pair scores 0.5 or lower, and no pair sits in
the band that needs LLM review. The tests prove that:

- raw entities survive resolution, each linked by ``RESOLVED_AS`` to one
  resolved entity that carries the merged properties;
- the resolved vector in Qdrant is refreshed when a cluster grows, and the
  vector of the replaced cluster is removed;
- a search by any alias returns the resolved entity, never its raw members,
  and a similar but different organization stays separate;
- ``consolidate()`` dry-run writes nothing and ``consolidate(apply=True)``
  writes exactly the matches the dry-run reported;
- user-chosen ``PropertyRules`` give the documented merge results;
- a failed vector write leaves the cluster hidden from search until a retry.

Every label, collection, and document key carries a per-run suffix, and the
fixture removes only what this run created. Each test also writes a JSON
artifact under ``reports/e2e/`` with names and counts only.
"""

import contextlib
import importlib.util
import itertools
import os
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest

from agrag.agents.ledger import Ledger
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.vector_record import VectorRecord
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.ingestion.merge import (
    PropertyRules,
    PropertyStrategy,
    apply_merge,
    compute_merge,
)
from agrag.retrieval.recipes import ENTITY
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.qdrant import QdrantVectorStore
from agrag.vectordb.settings import QdrantSettings
from tests.integration.e2e._artifact import write_artifact


pytestmark = [
    pytest.mark.skipif(
        importlib.util.find_spec("neo4j") is None, reason="neo4j extra not installed"
    ),
    pytest.mark.skipif(
        not os.environ.get("QDRANT_URL"), reason="QDRANT_URL is not configured"
    ),
]

ORG_SURFACES = ["Northwind Trading Company", "NWT Holdings", "Northwind Ltd"]
ORG_SEEDED_SURFACE = "Northwind Group"
ORG_OTHER = "Northwind Traders Union"
PERSON_SURFACES = ["Dr. Elena Vasquez", "Vasquez, Elena", "E. Vasquez"]

ORG_DESCRIPTIONS = {
    "Northwind Trading Company": "Grain trader founded in 1890.",
    "NWT Holdings": "Holding company for a grain trader.",
    "Northwind Ltd": "UK arm of the grain trader.",
}
ORG_HQ = {
    "Northwind Trading Company": "Oslo",
    "NWT Holdings": "Bergen",
    "Northwind Ltd": "Oslo",
}
ORG_REVENUE = {"Northwind Trading Company": 5, "Northwind Ltd": 7}

# Vector per exact name. Names of one real-world thing share a vector.
_ORG_VECTOR = [1.0, 0.0, 0.0, 0.0]
_UNION_VECTOR = [0.0, 1.0, 0.0, 0.0]
_PERSON_VECTOR = [0.0, 0.0, 1.0, 0.0]
_UNKNOWN_VECTOR = [0.5, 0.5, 0.5, 0.5]
_VECTOR_BY_NAME = {
    **dict.fromkeys([*ORG_SURFACES, ORG_SEEDED_SURFACE], _ORG_VECTOR),
    ORG_OTHER: _UNION_VECTOR,
    **dict.fromkeys(PERSON_SURFACES, _PERSON_VECTOR),
}


class _ConceptEmbedder(Embedder):
    """Embedder that knows which names mean the same thing.

    Stored text is ``"Name: description"`` for entities, so the vector comes
    from the text before the first colon. Text with no known name, such as a
    chunk, scores 0.5 against every known vector.
    """

    model = "concept"

    async def dimensions(self) -> int:
        """Return 4, the size of the shared instance's vector indexes."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return the vector for each text's leading name."""
        return [
            list(_VECTOR_BY_NAME.get(text.split(":", 1)[0].strip(), _UNKNOWN_VECTOR))
            for text in texts
        ]


class _DocumentExtractor(Extractor):
    """Extractor emitting fixed mentions for the document keyword in a chunk."""

    def __init__(self, mentions_by_keyword: dict[str, list[tuple[str, str, dict]]]):
        """Remember the ``(label, name, properties)`` mentions per keyword."""
        self._mentions_by_keyword = mentions_by_keyword

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Emit the mentions of every keyword the chunk contains."""
        entities = [
            ExtractedEntity(
                chunk_id=chunk.id,  # type: ignore[arg-type]
                label=label,
                text=name,
                char_start=0,
                char_end=len(name),
                properties=properties,
            )
            for keyword, mentions in self._mentions_by_keyword.items()
            if keyword in chunk.text
            for label, name, properties in mentions
        ]
        return ExtractionResult(
            entities=entities, relations=[], extractor_name="resolution_merge"
        )


class _FlakyVectorStore(QdrantVectorStore):
    """Qdrant store whose writes to one collection fail on demand."""

    def __init__(self) -> None:
        """Connect with the environment's Qdrant settings."""
        super().__init__(settings=QdrantSettings())
        self.failing_collection: str | None = None

    async def upsert(
        self,
        collection: str,
        records: Sequence[VectorRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Write records, or raise when this collection is set to fail."""
        if collection == self.failing_collection:
            raise RuntimeError("vector store unavailable")
        await super().upsert(collection, records, batch_size=batch_size)


@dataclass
class _World:
    """Handles to one run's isolated graph, stores, and names."""

    store: GraphStore
    vector_store: _FlakyVectorStore
    graph: Graph
    engine: SearchEngine
    settings: RetrievalSettings
    embedder: _ConceptEmbedder
    schema: GraphSchema
    org_label: str
    person_label: str
    org_cluster_after_second_document: str


def _document(key: str, text: str) -> Document:
    """Build a prose Document with an explicit stable key."""
    return Document(
        text=text,
        title="resolution_merge",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=key,
        loader_name="inline",
        encoding="utf-8",
        char_count=len(text),
        line_count=1,
    )


async def _rows(store: GraphStore, query: str, **params: Any) -> list[dict[str, Any]]:
    """Run a read query and return its rows."""
    return await store.execute_read(query, params)


async def _clusters(w: _World, label: str) -> dict[frozenset[str], dict[str, Any]]:
    """Return resolved-entity nodes for a label, keyed by member names."""
    rows = await _rows(
        w.store,
        "MATCH (r:ResolvedEntity) WHERE r.label = $label "
        "OPTIONAL MATCH (e)-[:RESOLVED_AS]->(r) "
        "RETURN r.id AS id, r.name AS name, r.member_ids AS member_ids, "
        "r.vector_sync_status AS status, r.embedding IS NOT NULL AS has_embedding, "
        "collect(e.name) AS members, properties(r) AS props",
        label=label,
    )
    return {frozenset(row["members"]): row for row in rows}


async def _raw_ids(w: _World, label: str) -> dict[str, str]:
    """Return raw entity ids keyed by name."""
    rows = await _rows(w.store, f"MATCH (e:{label}) RETURN e.id AS id, e.name AS name")
    return {row["name"]: row["id"] for row in rows}


async def _active_matches(w: _World, label: str) -> dict[frozenset[str], str | None]:
    """Return active MATCHES edges as name pairs mapped to their comparator."""
    rows = await _rows(
        w.store,
        f"MATCH (a:{label})-[m:MATCHES]->(b:{label}) WHERE m.active = true "
        "RETURN a.name AS a, b.name AS b, m.comparator AS comparator",
    )
    return {frozenset((row["a"], row["b"])): row["comparator"] for row in rows}


async def _resolved_vectors(w: _World) -> dict[str, dict[str, Any]]:
    """Return every record in this run's resolved-entity collection by id."""
    records: dict[str, dict[str, Any]] = {}
    offset: str | None = None
    while True:
        page, offset = await w.vector_store.scroll(
            w.settings.resolved_entity_collection, limit=100, page_offset=offset
        )
        records.update({str(record.id): record.payload for record in page})
        if offset is None:
            return records


async def _snapshot(w: _World) -> dict[str, Any]:
    """Capture everything a resolution pass could change, for comparison."""
    state: dict[str, Any] = {"vectors": sorted(await _resolved_vectors(w))}
    for label in (w.org_label, w.person_label):
        state[label] = {
            "raw": await _raw_ids(w, label),
            "matches": sorted(sorted(pair) for pair in await _active_matches(w, label)),
            "clusters": {
                tuple(sorted(members)): (row["id"], row["status"])
                for members, row in (await _clusters(w, label)).items()
            },
        }
    state["entity_vectors"] = await w.vector_store.count(w.settings.entity_collection)
    return state


async def _search_names(w: _World, query: str) -> list[dict[str, Any]]:
    """Search entities and describe each result by kind and name."""
    results = await w.engine.search(query, ENTITY)
    return [
        {
            "kind": type(result.item).__name__,
            "name": result.item.name,
            "id": str(result.item.id),
            "result": result,
        }
        for result in results
        if isinstance(result.item, (Entity, ResolvedEntity))
    ]


async def _seed_unresolved_surface(w: _World) -> Entity:
    """Write a fourth org surface straight to the graph, unseen by add()."""
    seeded = Entity(
        id=uuid4(),
        label=w.org_label,
        name=ORG_SEEDED_SURFACE,
        properties={
            "hq": "Stavanger",
            "revenue": 9,
            "description": "Parent group of the grain trader.",
        },
        embedding=list(_ORG_VECTOR),
    )
    await w.store.upsert_nodes(w.org_label, [seeded.to_node_record()])
    return seeded


async def _cleanup(
    store: GraphStore,
    vector_store: _FlakyVectorStore,
    *,
    labels: list[str],
    document_keys: list[str],
    collections: list[str],
) -> None:
    """Remove only what this run created, ignoring individual failures."""
    steps: list[tuple[str, dict[str, Any]]] = [
        (
            "MATCH (r:ResolvedEntity) WHERE r.label IN $labels DETACH DELETE r",
            {"labels": labels},
        ),
        (
            "MATCH (d:Document) WHERE d.document_key IN $keys "
            "OPTIONAL MATCH (d)-[:PART_OF]->(c:Chunk) DETACH DELETE d, c",
            {"keys": document_keys},
        ),
        (
            "MATCH (e) WHERE any(l IN labels(e) WHERE l IN $labels) DETACH DELETE e",
            {"labels": labels},
        ),
        (
            "MATCH (j:CutoverJob) WHERE j.document_key IN $keys DETACH DELETE j",
            {"keys": document_keys},
        ),
        (
            "MATCH (a:_AgragMergeAlias) WHERE any(l IN $labels "
            "WHERE a.merge_key STARTS WITH l + ':') DETACH DELETE a",
            {"labels": labels},
        ),
        (
            "MATCH (p:ResolvedEntityVectorDeletion) WHERE p.collection IN $collections "
            "DETACH DELETE p",
            {"collections": collections},
        ),
    ]
    for query, params in steps:
        with contextlib.suppress(Exception):
            await store.execute_write(query, params)
    with contextlib.suppress(Exception):
        for kind, drop in (("INDEXES", "INDEX"), ("CONSTRAINTS", "CONSTRAINT")):
            names = await store.execute_read(
                f"SHOW {kind} YIELD name, labelsOrTypes "
                "WHERE any(l IN labelsOrTypes WHERE l IN $labels) RETURN name",
                {"labels": labels},
            )
            for row in names:
                await store.execute_write(f"DROP {drop} `{row['name']}` IF EXISTS")
    for collection in collections:
        with contextlib.suppress(Exception):
            await vector_store.delete_collection(collection)
    with contextlib.suppress(Exception):
        await vector_store.close()
    with contextlib.suppress(Exception):
        await store.close()


@pytest.fixture
async def world() -> AsyncGenerator[_World, None]:
    """Ingest three documents into an isolated graph and vector collections."""
    suffix = uuid4().hex[:8]
    org_label = validate_identifier(f"Org_{suffix}")
    person_label = validate_identifier(f"Person_{suffix}")
    settings = RetrievalSettings(
        entity_collection=f"rm_entities_{suffix}",
        chunk_collection=f"rm_chunks_{suffix}",
        community_collection=f"rm_communities_{suffix}",
        resolved_entity_collection=f"rm_resolved_{suffix}",
    )
    schema = GraphSchema(
        name="resolution_merge",
        version="1",
        entities=[
            EntityType(
                label=org_label,
                description="An organization.",
                properties={
                    "description": "str",
                    "hq": "str",
                    "revenue": "int",
                    "employees": "int",
                },
            ),
            EntityType(
                label=person_label,
                description="A person.",
                properties={"title": "str"},
            ),
        ],
        relations=[],
    )
    org_mentions = {
        "docone": [
            (
                org_label,
                "Northwind Trading Company",
                {
                    "description": ORG_DESCRIPTIONS["Northwind Trading Company"],
                    "hq": "Oslo",
                    "revenue": 5,
                },
            ),
            (person_label, "Dr. Elena Vasquez", {"title": "Professor"}),
        ],
        "doctwo": [
            (
                org_label,
                "NWT Holdings",
                {
                    "description": ORG_DESCRIPTIONS["NWT Holdings"],
                    "hq": "Bergen",
                    "employees": 120,
                },
            ),
            (
                org_label,
                ORG_OTHER,
                {"description": "Labour union for dock workers."},
            ),
            (person_label, "Vasquez, Elena", {"title": "Chair"}),
        ],
        "docthree": [
            (
                org_label,
                "Northwind Ltd",
                {
                    "description": ORG_DESCRIPTIONS["Northwind Ltd"],
                    "hq": "Oslo",
                    "revenue": 7,
                },
            ),
            (person_label, "E. Vasquez", {"title": "Professor"}),
        ],
    }
    store = build_graph_store("neo4j")
    vector_store = _FlakyVectorStore()
    embedder = _ConceptEmbedder()
    keys = [f"resolution-merge://{suffix}/{n}" for n in ("one", "two", "three")]
    collections = [
        settings.entity_collection,
        settings.chunk_collection,
        settings.community_collection,
        settings.resolved_entity_collection,
    ]
    try:
        graph = await Graph.open(
            schema=schema,
            graph_store=store,
            embedder=embedder,
            extractor=_DocumentExtractor(org_mentions),
            vector_store=vector_store,
            retrieval_settings=settings,
        )
        engine = SearchEngine(
            graph_store=store,
            embedder=embedder,
            vector_store=vector_store,
            settings=settings,
            graph_schema=schema,
        )
        partial = _World(
            store=store,
            vector_store=vector_store,
            graph=graph,
            engine=engine,
            settings=settings,
            embedder=embedder,
            schema=schema,
            org_label=org_label,
            person_label=person_label,
            org_cluster_after_second_document="",
        )
        for index, (keyword, key) in enumerate(
            zip(("docone", "doctwo", "docthree"), keys, strict=True)
        ):
            await graph.add(documents=[_document(key, f"{keyword} covers grain. " * 3)])
            if index == 1:
                (cluster,) = (await _clusters(partial, org_label)).values()
                partial.org_cluster_after_second_document = cluster["id"]
        yield partial
    finally:
        await _cleanup(
            store,
            vector_store,
            labels=[org_label, person_label],
            document_keys=keys,
            collections=collections,
        )


@pytest.fixture
async def resolved_world(world: _World) -> _World:
    """Return the world after a user-run ``consolidate(apply=True)``."""
    report = await world.graph.consolidate(apply=True)
    assert report.failures == []
    return world


class TestResolutionMerge:
    """Resolution and merge behavior a user sees after ingesting and consolidating."""

    async def test_documents_resolve_and_search_returns_survivor(  # noqa: PLR0915
        self, resolved_world: _World
    ) -> None:
        """Ingest, search, dry-run, and apply resolution end to end.

        Failure modes covered: raw members deleted or left unlinked; a
        similar-named organization pulled into the cluster; merged properties
        that drop a non-conflicting value or keep a value no member has; a
        stale resolved vector left in Qdrant after the cluster grew; a
        refreshed vector built from the old cluster text; search returning a
        raw member of an active cluster, or the cluster under an alias it
        should not answer; unstable citation keys; a dry run that writes; an
        apply that writes matches the dry run did not report.
        """
        w = resolved_world
        org_ids = await _raw_ids(w, w.org_label)
        person_ids = await _raw_ids(w, w.person_label)

        # Raw entities survive resolution: no node was absorbed or deleted.
        assert set(org_ids) == {*ORG_SURFACES, ORG_OTHER}
        assert set(person_ids) == set(PERSON_SURFACES)

        # Add-time resolution matched every pair of the three surfaces.
        matches = await _active_matches(w, w.org_label)
        assert matches == {
            frozenset(pair): "embedding"
            for pair in (
                (ORG_SURFACES[0], ORG_SURFACES[1]),
                (ORG_SURFACES[0], ORG_SURFACES[2]),
                (ORG_SURFACES[1], ORG_SURFACES[2]),
            )
        }

        # One resolved entity per real-world thing; the similar name stays out.
        org_clusters = await _clusters(w, w.org_label)
        assert set(org_clusters) == {frozenset(ORG_SURFACES)}
        org_cluster = org_clusters[frozenset(ORG_SURFACES)]
        person_cluster = (await _clusters(w, w.person_label))[
            frozenset(PERSON_SURFACES)
        ]
        assert {UUID(m) for m in org_cluster["member_ids"]} == {
            UUID(org_ids[name]) for name in ORG_SURFACES
        }
        union_edges = await _rows(
            w.store,
            f"MATCH (u:{w.org_label} {{name: $name}}) "
            "OPTIONAL MATCH (u)-[m:MATCHES]-() "
            "OPTIONAL MATCH (u)-[r:RESOLVED_AS]->() "
            "RETURN count(m) AS matches, count(r) AS resolved_as",
            name=ORG_OTHER,
        )
        assert union_edges == [{"matches": 0, "resolved_as": 0}]

        # Merged properties: conflicts keep one candidate, lone values survive.
        props = org_cluster["props"]
        assert org_cluster["name"] in ORG_SURFACES
        assert props["hq"] in set(ORG_HQ.values())
        assert props["revenue"] in set(ORG_REVENUE.values())
        assert props["employees"] == 120
        assert sorted(props["description"].split(" | ")) == sorted(
            ORG_DESCRIPTIONS.values()
        )
        assert person_cluster["props"]["title"] in {"Professor", "Chair"}

        # Embeddings: synced, refreshed with all three descriptions, and the
        # cluster replaced by the third document has no vector left behind.
        assert org_cluster["status"] == "synced"
        assert org_cluster["has_embedding"] is True
        assert w.org_cluster_after_second_document != org_cluster["id"]
        vectors = await _resolved_vectors(w)
        assert set(vectors) == {org_cluster["id"], person_cluster["id"]}
        assert w.org_cluster_after_second_document not in vectors
        org_payload = vectors[org_cluster["id"]]
        assert org_payload["text"] == f"{org_cluster['name']}: {props['description']}"
        assert org_payload["resolved"] is True
        assert set(org_payload["member_ids"]) == {org_ids[n] for n in ORG_SURFACES}
        stale_rows = await _rows(
            w.store,
            "MATCH (r:ResolvedEntity {id: $id}) RETURN count(r) AS n",
            id=w.org_cluster_after_second_document,
        )
        assert stale_rows == [{"n": 0}]

        # Search by an alias returns the survivor and none of its raw members.
        member_ids = {org_ids[name] for name in ORG_SURFACES}
        alias_hits = {}
        for alias in ("NWT Holdings", "Northwind Ltd"):
            hits = await _search_names(w, alias)
            assert hits, alias
            assert hits[0]["kind"] == "ResolvedEntity"
            assert hits[0]["id"] == org_cluster["id"]
            assert not member_ids & {
                hit["id"] for hit in hits if hit["kind"] == "Entity"
            }
            alias_hits[alias] = hits
        union_hits = await _search_names(w, ORG_OTHER)
        assert (union_hits[0]["kind"], union_hits[0]["name"]) == ("Entity", ORG_OTHER)
        assert union_hits[0]["id"] == org_ids[ORG_OTHER]

        # Both alias searches cite the survivor under one key.
        ledger = Ledger()
        keys = {
            alias: ledger.cite(hits[0]["result"]) for alias, hits in alias_hits.items()
        }
        assert len(set(keys.values())) == 1
        cited = ledger.resolve(next(iter(keys.values())))
        assert cited is not None
        assert str(cited.item.id) == org_cluster["id"]
        assert ledger.cite(union_hits[0]["result"]) != next(iter(keys.values()))

        # Nothing changed since add(): a no-op apply keeps ids, so a key still
        # resolves to the same survivor in a fresh run.
        before_noop = await _snapshot(w)
        noop = await w.graph.consolidate(apply=True)
        assert noop.failures == []
        assert noop.ambiguous_count == 0
        after_noop = await _snapshot(w)
        assert after_noop == before_noop

        # A fourth surface written directly is invisible to add-time
        # resolution. Dry run reports its matches and writes nothing.
        seeded = await _seed_unresolved_surface(w)
        before_dry = await _snapshot(w)
        dry = await w.graph.consolidate()
        assert dry.applied is False
        assert dry.failures == []
        assert dry.ambiguous_count == 0
        assert await _snapshot(w) == before_dry

        name_of = {UUID(v): k for k, v in {**org_ids, **person_ids}.items()} | {
            seeded.id: seeded.name
        }
        predicted = {
            frozenset((name_of[m.entity_a_id], name_of[m.entity_b_id]))
            for m in dry.would_match
        }
        assert all(m.comparator == "embedding" for m in dry.would_match)
        assert frozenset((ORG_SEEDED_SURFACE, ORG_SURFACES[0])) in predicted
        assert all(ORG_OTHER not in pair for pair in predicted)
        org_names = {*ORG_SURFACES, ORG_SEEDED_SURFACE}
        predicted_org = {pair for pair in predicted if pair <= org_names}
        assert predicted_org == {
            frozenset(pair) for pair in itertools.combinations(sorted(org_names), 2)
        }

        # Apply writes exactly the reported matches and one grown cluster.
        applied = await w.graph.consolidate(apply=True)
        assert applied.applied is True
        assert applied.failures == []
        assert {
            frozenset((name_of[m.entity_a_id], name_of[m.entity_b_id]))
            for m in applied.would_match
        } == predicted
        final_matches = await _active_matches(w, w.org_label)
        assert set(final_matches) == set(matches) | predicted_org
        final_clusters = await _clusters(w, w.org_label)
        full_set = frozenset([*ORG_SURFACES, ORG_SEEDED_SURFACE])
        assert set(final_clusters) == {full_set}
        grown = final_clusters[full_set]
        assert grown["id"] != org_cluster["id"]
        assert grown["status"] == "synced"
        assert grown["has_embedding"] is True
        assert set(await _raw_ids(w, w.org_label)) == {
            *ORG_SURFACES,
            ORG_SEEDED_SURFACE,
            ORG_OTHER,
        }
        final_vectors = await _resolved_vectors(w)
        assert set(final_vectors) == {grown["id"], person_cluster["id"]}
        assert seeded.properties["description"] in grown["props"]["description"]
        assert seeded.properties["description"] in final_vectors[grown["id"]]["text"]

        # The grown cluster answers alias searches; the old survivor is gone.
        after_hits = await _search_names(w, "NWT Holdings")
        assert grown["id"] in {hit["id"] for hit in after_hits}
        assert org_cluster["id"] not in {hit["id"] for hit in after_hits}

        artifact = write_artifact(
            "resolution_merge",
            {
                "raw_entities": sorted([*org_ids, *person_ids]),
                "add_time_matches": sorted(sorted(pair) for pair in matches),
                "org_cluster_members": sorted(ORG_SURFACES),
                "person_cluster_members": sorted(PERSON_SURFACES),
                "unmerged_similar_name": ORG_OTHER,
                "merged_employees": props["employees"],
                "description_parts": sorted(props["description"].split(" | ")),
                "conflict_winners_are_member_values": True,
                "stale_cluster_vector_removed": True,
                "vector_ids_after_add": 2,
                "alias_search_top_kind": "ResolvedEntity",
                "alias_citation_keys_equal": True,
                "noop_apply_changes": False,
                "dry_run_changes": False,
                "dry_run_predicted_pairs": sorted(
                    sorted(p) for p in predicted_org - set(matches)
                ),
                "applied_new_pairs": sorted(
                    sorted(p) for p in set(final_matches) - set(matches)
                ),
                "final_cluster_members": sorted(full_set),
                "final_vector_count": len(final_vectors),
            },
        )
        assert artifact["dry_run_predicted_pairs"] == artifact["applied_new_pairs"]
        assert artifact["final_cluster_members"] == sorted(full_set)
        assert artifact["unmerged_similar_name"] == ORG_OTHER

    async def test_property_rules_choose_merged_values(self, world: _World) -> None:
        """User-chosen rules and strategies give the documented merged values.

        Failure modes covered: a strategy that picks the wrong end of the
        candidates; a rule that is skipped for a conflicting property; a
        conflict reported for a property only one member has; a description
        summary that is dropped or not recorded as a conflict; a failed
        summarizer that loses the descriptions; a multi-entity plan that
        deletes raw nodes instead of being rejected.
        """
        w = world
        rows = await _rows(
            w.store,
            f"MATCH (e:{w.org_label}) WHERE e.name IN $names "
            "RETURN e.id AS id, e.name AS name, properties(e) AS props",
            names=ORG_SURFACES,
        )
        by_name = {row["name"]: row for row in rows}
        members = [
            Entity(
                id=UUID(by_name[name]["id"]),
                label=w.org_label,
                name=name,
                properties={
                    key: by_name[name]["props"][key]
                    for key in ("hq", "revenue", "employees", "description")
                    if key in by_name[name]["props"]
                },
            )
            for name in ORG_SURFACES
        ]

        class _Summarizer:
            async def SummarizeDescriptions(  # noqa: N802
                self, descriptions: list[str], baml_options: dict[str, Any]
            ) -> str:
                return "SUMMARY of " + " + ".join(sorted(descriptions))

        class _BrokenSummarizer:
            async def SummarizeDescriptions(  # noqa: N802
                self, descriptions: list[str], baml_options: dict[str, Any]
            ) -> str:
                raise RuntimeError("summarizer down")

        async def merge(
            rules: PropertyRules | None, client: object = _Summarizer()
        ) -> Any:
            plan, failures = await compute_merge(
                existing_entities=members,
                mentions=[],
                schema=w.schema,
                rules=rules,
                description_client=client,
            )
            return plan, failures

        first, _ = await merge(None)
        last, _ = await merge(PropertyRules(default=PropertyStrategy.KEEP_LAST))
        every, _ = await merge(
            PropertyRules(
                default=PropertyStrategy.MERGE_ALL, rules={"name": lambda vs: vs[0]}
            )
        )
        custom, _ = await merge(PropertyRules(rules={"revenue": max}))  # type: ignore[type-var]
        summed = "SUMMARY of " + " + ".join(sorted(ORG_DESCRIPTIONS.values()))

        assert (first.survivor.name, first.survivor.properties["hq"]) == (
            "Northwind Trading Company",
            "Oslo",
        )
        assert first.survivor.properties["revenue"] == 5
        assert (last.survivor.name, last.survivor.properties["hq"]) == (
            "Northwind Ltd",
            "Bergen",
        )
        assert last.survivor.properties["revenue"] == 7
        assert every.survivor.properties["hq"] == ["Oslo", "Bergen"]
        assert every.survivor.properties["revenue"] == [5, 7]
        assert custom.survivor.properties["revenue"] == 7
        assert custom.survivor.properties["hq"] == "Oslo"
        for plan in (first, last, every, custom):
            assert plan.survivor.properties["employees"] == 120
            assert plan.survivor.properties["description"] == summed
        assert {c.field for c in first.conflicts} == {
            "name",
            "hq",
            "revenue",
            "description",
        }
        assert first.tombstone_ids  # the two absorbed members

        _, broken_failures = await merge(None, client=_BrokenSummarizer())
        broken_plan, _ = await merge(None, client=_BrokenSummarizer())
        assert sorted(broken_plan.survivor.properties["description"].split(" | ")) == (
            sorted(ORG_DESCRIPTIONS.values())
        )
        assert [f.error_message for f in broken_failures] == ["summarizer down"]

        # A multi-entity plan must not delete raw nodes: apply_merge refuses.
        before = await _raw_ids(w, w.org_label)
        with pytest.raises(ValueError, match="Destructive merge is retired"):
            await apply_merge(first, graph_store=w.store, schema=w.schema)
        assert await _raw_ids(w, w.org_label) == before

        artifact = write_artifact(
            "resolution_merge_property_rules",
            {
                "keep_first": [first.survivor.name, first.survivor.properties["hq"]],
                "keep_last": [last.survivor.name, last.survivor.properties["hq"]],
                "merge_all_hq": every.survivor.properties["hq"],
                "merge_all_revenue": every.survivor.properties["revenue"],
                "custom_max_revenue": custom.survivor.properties["revenue"],
                "conflict_fields": sorted(c.field for c in first.conflicts),
                "description": first.survivor.properties["description"],
                "summarizer_failure": [f.error_message for f in broken_failures],
                "apply_multi_entity_plan": "rejected",
                "raw_entities_after_rejection": len(before),
            },
        )
        assert artifact["keep_first"] == ["Northwind Trading Company", "Oslo"]
        assert artifact["merge_all_revenue"] == [5, 7]
        assert artifact["raw_entities_after_rejection"] == 4

    async def test_failed_vector_sync_hides_cluster_until_retry(
        self, resolved_world: _World
    ) -> None:
        """A failed resolved-vector write is reported, hidden, and retried.

        Failure modes covered: a vector-store outage that raises out of
        ``consolidate`` under the skip policy; a cluster whose failed status
        or embedding is not recorded, so it looks searchable; raw members
        that disappear from search while the cluster has no vector; a retry
        that does not restore the vector, status, and search result.
        """
        w = resolved_world
        seeded = await _seed_unresolved_surface(w)
        old_cluster = (await _clusters(w, w.org_label))[frozenset(ORG_SURFACES)]
        w.vector_store.failing_collection = w.settings.resolved_entity_collection

        failed = await w.graph.consolidate(apply=True)

        assert [f.item_id for f in failed.failures] == ["resolved_entity_embeddings"]
        full_set = frozenset([*ORG_SURFACES, ORG_SEEDED_SURFACE])
        cluster = (await _clusters(w, w.org_label))[full_set]
        assert cluster["status"] == "failed"
        assert cluster["has_embedding"] is False
        assert cluster["id"] != old_cluster["id"]
        vectors = await _resolved_vectors(w)
        assert cluster["id"] not in vectors
        assert old_cluster["id"] not in vectors
        hidden = await _search_names(w, "NWT Holdings")
        assert "ResolvedEntity" not in {hit["kind"] for hit in hidden}
        assert "NWT Holdings" in {hit["name"] for hit in hidden}

        w.vector_store.failing_collection = None
        retried = await w.graph.consolidate(apply=True)

        assert retried.failures == []
        recovered = (await _clusters(w, w.org_label))[full_set]
        assert recovered["status"] == "synced"
        assert recovered["has_embedding"] is True
        assert cluster["id"] in await _resolved_vectors(w)
        shown = await _search_names(w, "NWT Holdings")
        assert shown[0]["kind"] == "ResolvedEntity"
        assert recovered["id"] in {
            hit["id"] for hit in shown if hit["kind"] == "ResolvedEntity"
        }
        assert seeded.name in recovered["members"]

        artifact = write_artifact(
            "resolution_merge_vector_failure",
            {
                "failed_pass_failures": [f.item_id for f in failed.failures],
                "status_after_failure": cluster["status"],
                "embedding_kept_after_failure": cluster["has_embedding"],
                "search_after_failure": sorted(
                    {(hit["kind"], hit["name"]) for hit in hidden}
                ),
                "retry_failures": len(retried.failures),
                "status_after_retry": recovered["status"],
                "search_after_retry_top_kind": shown[0]["kind"],
                "cluster_members": sorted(full_set),
            },
        )
        assert artifact["status_after_failure"] == "failed"
        assert artifact["status_after_retry"] == "synced"


class TestKnownDefects:
    """Defects the scenario exposed; each test flips to pass when fixed."""

    async def test_growing_cluster_replaces_previous_resolved_entity(
        self, world: _World
    ) -> None:
        """After three add() calls, one resolved entity covers the organization."""
        clusters = await _clusters(world, world.org_label)

        assert set(clusters) == {frozenset(ORG_SURFACES)}

    async def test_add_mirrors_resolved_vector_to_vector_store(
        self, world: _World
    ) -> None:
        """A committed resolved entity has a vector in the vector store."""
        clusters = await _clusters(world, world.org_label)
        vectors = await _resolved_vectors(world)

        assert {row["id"] for row in clusters.values()} <= set(vectors)

    async def test_merge_all_default_keeps_name_a_string(self, world: _World) -> None:
        """A user who picks MERGE_ALL for every property still gets a named entity."""
        members = [
            Entity(id=uuid4(), label=world.org_label, name=name)
            for name in ORG_SURFACES
        ]

        plan, _ = await compute_merge(
            existing_entities=members,
            mentions=[],
            schema=world.schema,
            rules=PropertyRules(default=PropertyStrategy.MERGE_ALL),
        )

        assert plan.survivor.name in ORG_SURFACES
