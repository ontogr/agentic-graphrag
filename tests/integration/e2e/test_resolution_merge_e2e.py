"""E2E entity resolution and merge as a user runs them, on real Neo4j.

Three documents mention the same organization and person under different
surface names, with conflicting property values and descriptions. A fake
embedder decides which names mean the same thing, so no LLM runs: same-thing
pairs score 1.0 and every other pair scores 0.5 or lower, and no pair sits in
the band that needs LLM review. The tests prove that:

- raw entities survive resolution, each linked by ``RESOLVED_AS`` to one
  resolved entity that carries the merged properties;
- the resolved embedding is refreshed when a cluster grows, and the node of
  the replaced cluster is removed;
- a search by any alias returns the resolved entity, never its raw members,
  and a similar but different organization stays separate;
- ``consolidate()`` dry-run writes nothing and ``consolidate(apply=True)``
  writes exactly the matches the dry-run reported;
- user-chosen ``PropertyRules`` give the documented merge results;
- a failed embedding write leaves the cluster hidden from search until a retry.

Every label and document key carries a per-run suffix, and the
fixture removes only what this run created. Each test also writes a JSON
artifact under ``reports/e2e/`` with names and counts only.
"""

import contextlib
import importlib.util
import itertools
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
from agrag.common.data_models.graph_schema import EntityType, GraphSchema, PropertySpec
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.ingestion.merge import (
    PropertyRules,
    PropertyStrategy,
    compute_merge,
)
from agrag.retrieval.recipes import ENTITY
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings
from tests.integration._schema_cleanup import drop_schema_for
from tests.integration.e2e._artifact import write_artifact


pytestmark = [
    pytest.mark.skipif(
        importlib.util.find_spec("neo4j") is None, reason="neo4j extra not installed"
    ),
]

ORG_SURFACES = ["Northwind Trading Company", "NWT Holdings", "Northwind Ltd"]
ORG_SEEDED_SURFACE = "Northwind Group"
SEEDED_DESCRIPTION = "Parent group of the grain trader."
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
    fail_containing: str | None = None

    def __init__(self) -> None:
        self.embedded_texts: list[str] = []

    async def dimensions(self) -> int:
        """Return 4, the size of the shared instance's vector indexes."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return the vector for each text's leading name.

        Raises:
            RuntimeError: A text contains ``fail_containing``, which a test sets
                to make one resolved entity's embedding write fail.
        """
        if self.fail_containing is not None and any(
            self.fail_containing in text for text in texts
        ):
            raise RuntimeError("embedding service unavailable")
        self.embedded_texts.extend(texts)
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


@dataclass
class _World:
    """Handles to one run's isolated graph, stores, and names."""

    store: GraphStore
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
    """Return this run's resolved-entity nodes that hold an embedding, by id.

    The database is shared with other runs, so only this run's labels count.
    """
    rows = await _rows(
        w.store,
        "MATCH (r:ResolvedEntity) WHERE r.embedding IS NOT NULL "
        "AND r.label IN $labels "
        "RETURN r.id AS id, r.name AS name, r.member_ids AS member_ids, "
        "properties(r) AS props",
        labels=[w.org_label, w.person_label],
    )
    return {
        str(row["id"]): {
            "name": row["name"],
            "description": row["props"].get("description"),
            "member_ids": row["member_ids"],
        }
        for row in rows
    }


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
    return state


async def _search_names(w: _World, query: str) -> list[dict[str, Any]]:
    """Search this run's entities and describe each result by kind and name.

    Results of other labels come from other runs sharing the database and are
    left out.
    """
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
        and result.item.label in (w.org_label, w.person_label)
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
            "description": SEEDED_DESCRIPTION,
        },
        embedding=list(_ORG_VECTOR),
    )
    await w.store.upsert_nodes(w.org_label, [seeded.to_node_record()])
    return seeded


async def _cleanup(
    store: GraphStore,
    *,
    labels: list[str],
    document_keys: list[str],
) -> None:
    """Remove only what this run created, ignoring individual failures."""
    steps: list[tuple[str, dict[str, Any]]] = [
        (
            "MATCH (r:ResolvedEntity) WHERE r.label IN $labels DETACH DELETE r",
            {"labels": labels},
        ),
        (
            "MATCH (d:Document) WHERE d.document_key IN $keys "
            "OPTIONAL MATCH (d)-[:HAS_PART]->(c:Chunk) DETACH DELETE d, c",
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
            "MATCH (a:_MergeAlias) WHERE any(l IN $labels "
            "WHERE a.merge_key STARTS WITH l + ':') DETACH DELETE a",
            {"labels": labels},
        ),
    ]
    for query, params in steps:
        with contextlib.suppress(Exception):
            await store.execute_write(query, params)
    with contextlib.suppress(Exception):
        await drop_schema_for(store, *labels)
    with contextlib.suppress(Exception):
        await store.close()


@pytest.fixture
async def world() -> AsyncGenerator[_World, None]:
    """Ingest three documents into an isolated graph."""
    suffix = uuid4().hex[:8]
    org_label = validate_identifier(f"Org_{suffix}")
    person_label = validate_identifier(f"Person_{suffix}")
    settings = RetrievalSettings()
    schema = GraphSchema(
        name="resolution_merge",
        version="1",
        entities=[
            EntityType(
                label=org_label,
                description="An organization.",
                properties={
                    "description": PropertySpec(type="string"),
                    "hq": PropertySpec(type="string"),
                    "revenue": PropertySpec(type="integer"),
                    "employees": PropertySpec(type="integer"),
                },
            ),
            EntityType(
                label=person_label,
                description="A person.",
                properties={"title": PropertySpec(type="string")},
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
    embedder = _ConceptEmbedder()
    keys = [f"resolution-merge://{suffix}/{n}" for n in ("one", "two", "three")]
    try:
        graph = await Graph.open(
            schema=schema,
            graph_store=store,
            embedder=embedder,
            extractor=_DocumentExtractor(org_mentions),
        )
        engine = SearchEngine(
            graph_store=store,
            embedder=embedder,
            settings=settings,
            graph_schema=schema,
        )
        partial = _World(
            store=store,
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
            labels=[org_label, person_label],
            document_keys=keys,
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
        stale resolved node left in the graph after the cluster grew; a
        refreshed embedding built from the old cluster text; search returning a
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
        assert org_payload["description"] == props["description"]
        assert (
            f"{org_cluster['name']}: {props['description']}"
            in w.embedder.embedded_texts
        )
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
        grown_description = final_vectors[grown["id"]]["description"]
        assert seeded.properties["description"] in grown_description

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

        _, broken_failures = await merge(None, client=_BrokenSummarizer())
        broken_plan, _ = await merge(None, client=_BrokenSummarizer())
        assert sorted(broken_plan.survivor.properties["description"].split(" | ")) == (
            sorted(ORG_DESCRIPTIONS.values())
        )
        assert [f.error_message for f in broken_failures] == ["summarizer down"]

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
            },
        )
        assert artifact["keep_first"] == ["Northwind Trading Company", "Oslo"]
        assert artifact["merge_all_revenue"] == [5, 7]

    async def test_failed_embedding_hides_cluster_until_retry(
        self, resolved_world: _World
    ) -> None:
        """A failed resolved-entity embedding is reported, hidden, and retried.

        Failure modes covered: an embedding failure that is not reported
        under the skip policy; a cluster whose failed status or embedding is
        not recorded, so it looks searchable; raw members that disappear from
        search while the cluster has no embedding; a retry that does not
        restore the embedding, status, and search result.
        """
        w = resolved_world
        seeded = await _seed_unresolved_surface(w)
        old_cluster = (await _clusters(w, w.org_label))[frozenset(ORG_SURFACES)]
        w.embedder.fail_containing = SEEDED_DESCRIPTION

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

        w.embedder.fail_containing = None
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
            "resolution_merge_embedding_failure",
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

    async def test_leftover_resolved_entities_stay_out_of_this_run(
        self, resolved_world: _World
    ) -> None:
        """A resolved entity another run left in the database is not reported.

        The e2e database is shared by every suite, and a run removes only its
        own nodes. A resolved entity left under another label, with this run's
        embedding, must not change the resolved entities this run reports or
        the ones a search returns.
        """
        w = resolved_world
        expected = {
            row["id"]
            for label in (w.org_label, w.person_label)
            for row in (await _clusters(w, label)).values()
        }
        leftover_id = str(uuid4())
        await w.store.execute_write(
            "CREATE (r:ResolvedEntity {id: $id, label: $label, name: 'NWT Holdings', "
            "member_ids: [], vector_sync_status: 'synced', embedding: $vector})",
            {
                "id": leftover_id,
                "label": f"Leftover_{uuid4().hex[:8]}",
                "vector": list(_ORG_VECTOR),
            },
        )
        try:
            vectors = await _resolved_vectors(w)
            hits = await _search_names(w, "NWT Holdings")
        finally:
            await w.store.execute_write(
                "MATCH (r:ResolvedEntity {id: $id}) DETACH DELETE r",
                {"id": leftover_id},
            )

        assert set(vectors) == expected
        assert leftover_id not in {hit["id"] for hit in hits}


class TestKnownDefects:
    """Defects the scenario exposed; each test flips to pass when fixed."""

    async def test_growing_cluster_replaces_previous_resolved_entity(
        self, world: _World
    ) -> None:
        """After three add() calls, one resolved entity covers the organization."""
        clusters = await _clusters(world, world.org_label)

        assert set(clusters) == {frozenset(ORG_SURFACES)}

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
