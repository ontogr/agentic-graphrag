"""E2E community detection: ingest -> detect -> both query paths."""

import importlib.util
import os
from collections.abc import Sequence
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.community import COMMUNITY_LABEL, Community
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_record import RelationRecord
from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import upsert_merge_alias_query, validate_identifier
from agrag.embedding.base import Embedder
from agrag.evidence import entity_search, search_themes
from agrag.graphdb.base import GraphStore
from agrag.ingestion.community import required_member_ids
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from tests.integration._backend import await_indexes, build_test_store
from tests.integration._schema_cleanup import delete_resolved_entities, drop_schema_for
from tests.integration.e2e._artifact import write_artifact
from tests.integration.retrieval.evidence._corpus import make_document


neo4j_missing = importlib.util.find_spec("neo4j") is None
graspologic_missing = importlib.util.find_spec("graspologic_native") is None


def _llm_endpoint_configured() -> bool:
    """Return True when the shared LLM endpoint configuration is available."""
    load_dotenv()
    return bool(os.getenv("LLM_BASE_URL") and os.getenv("LLM_MODEL_ID"))


class _FixedEmbedder(Embedder):
    """Deterministic embedder for e2e tests.

    Args:
        dim: Vector dimension.
        vector: Vector returned for every text. Tests that search the shared
            Community index pass a vector unique to the run, so their own
            communities rank first among communities left by other suites.
    """

    model = "fixed"

    def __init__(self, dim: int = 4, vector: list[float] | None = None) -> None:
        """Set the embedding dimension and the optional fixed vector."""
        self._dim = dim
        self._vector = vector

    async def dimensions(self) -> int:
        """Return the configured dimension."""
        return self._dim

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a constant vector for every text."""
        vector = self._vector or [0.1] * self._dim
        return [list(vector) for _ in texts]


def _run_vector(suffix: str, dim: int) -> list[float]:
    """Return a vector derived from the run suffix, distinct from ``[0.1] * dim``."""
    return [(int(char, 16) + 1) / 16 for char in suffix[:dim]]


def _fake_reports(communities: Sequence[object], **_: object) -> list[MagicMock]:
    """Return one fake LLM report per requested community."""
    return [
        MagicMock(
            title="LLM Title",
            summary="LLM summary.",
            rating=7.0,
            rating_explanation="ok",
            findings=["f1"],
        )
        for _ in communities
    ]


async def _entity_names(store: GraphStore, labels: list[str]) -> dict[str, str]:
    """Return ``{entity id: name}`` for every node carrying one of ``labels``."""
    rows = await store.execute_read(
        "MATCH (n) WHERE any(l IN labels(n) WHERE l IN $labels) "
        "RETURN n.id AS id, n.name AS name",
        {"labels": labels},
    )
    return {str(row["id"]): row["name"] for row in rows}


def _own_communities(
    communities: Sequence[Community], names_by_id: dict[str, str]
) -> list[Community]:
    """Keep the communities that contain at least one entity of this run."""
    return [c for c in communities if any(str(m) in names_by_id for m in c.member_ids)]


def _member_names(community: Community, names_by_id: dict[str, str]) -> list[str]:
    """Return the sorted member names of one community."""
    return sorted(names_by_id[str(m)] for m in community.member_ids)


class _FakeWorksAtExtractor(Extractor):
    """Extract Person/Organization/WORKS_AT from known keywords."""

    def __init__(self, person_label: str, org_label: str) -> None:
        """Remember the labels to emit."""
        self._person_label = person_label
        self._org_label = org_label
        self._persons = ["alice", "bob", "carol", "dave", "eve", "frank"]
        self._orgs = ["acme", "globex"]
        self._person_to_org = {
            "alice": "acme",
            "bob": "acme",
            "eve": "acme",
            "carol": "globex",
            "dave": "globex",
        }

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Extract known persons, orgs, and WORKS_AT relations."""
        text_lower = chunk.text.lower()
        entities: list[ExtractedEntity] = []
        name_to_index: dict[str, int] = {}
        for name in self._persons:
            idx = text_lower.find(name)
            if idx >= 0:
                ent = ExtractedEntity(
                    chunk_id=chunk.id,
                    label=self._person_label,
                    text=name.capitalize(),
                    char_start=idx,
                    char_end=idx + len(name),
                )
                name_to_index[name] = len(entities)
                entities.append(ent)
        org_to_index: dict[str, int] = {}
        for org in self._orgs:
            idx = text_lower.find(org)
            if idx >= 0:
                ent = ExtractedEntity(
                    chunk_id=chunk.id,
                    label=self._org_label,
                    text=org.capitalize(),
                    char_start=idx,
                    char_end=idx + len(org),
                )
                org_to_index[org] = len(entities)
                entities.append(ent)
        relations: list[ExtractedRelation] = []
        for person, org in self._person_to_org.items():
            if person in name_to_index and org in org_to_index:
                relations.append(
                    ExtractedRelation(
                        chunk_id=chunk.id,
                        label="WORKS_AT",
                        source_index=name_to_index[person],
                        target_index=org_to_index[org],
                    )
                )
        return ExtractionResult(
            entities=entities, relations=relations, extractor_name="fake"
        )


async def _cleanup_community_test_data(
    store: GraphStore, person_label: str, org_label: str
) -> None:
    """Remove only entities and dependent data created by one E2E test."""
    await delete_resolved_entities(store, person_label, org_label)
    await store.execute_write(
        "MATCH (a:_MergeAlias) WHERE any(label IN $labels "
        "WHERE a.merge_key STARTS WITH label + ':') DETACH DELETE a",
        {"labels": [person_label, org_label]},
    )
    rows = await store.execute_read(
        "MATCH (n) WHERE $person_label IN labels(n) "
        "OR $org_label IN labels(n) RETURN collect(n.id) AS ids",
        {"person_label": person_label, "org_label": org_label},
    )
    entity_ids = [str(entity_id) for entity_id in (rows[0].get("ids") or [])]
    if not entity_ids:
        return
    await store.execute_write(
        "MATCH (chunk:Chunk)-[]-(entity) WHERE entity.id IN $entity_ids "
        "DETACH DELETE chunk",
        {"entity_ids": entity_ids},
    )
    await store.execute_write(
        "MATCH (community:Community) WHERE any(member_id IN "
        "community.member_ids WHERE member_id IN $entity_ids) DETACH DELETE community",
        {"entity_ids": entity_ids},
    )
    await store.execute_write(
        "MATCH (entity) WHERE entity.id IN $entity_ids DETACH DELETE entity",
        {"entity_ids": entity_ids},
    )


async def _cleanup_support_document(store: GraphStore, document_key: str) -> None:
    """Delete the support document and its chunks of one e2e test."""
    await store.execute_write(
        "MATCH (d:Document) WHERE d.document_key = $key "
        "MATCH (d)-[:HAS_PART]->(c:Chunk) DETACH DELETE c",
        {"key": document_key},
    )
    await store.execute_write(
        "MATCH (d:Document) WHERE d.document_key = $key DETACH DELETE d",
        {"key": document_key},
    )


@pytest.mark.enable_socket
@pytest.mark.xdist_group(name="community_label")
@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
@pytest.mark.skipif(graspologic_missing, reason="graspologic-native missing")
async def test_community_via_store_e2e() -> None:  # noqa: PLR0915
    """Store-seeded seam: upsert -> detect -> entity search + themes."""
    store = build_test_store()
    await store.connect()
    suffix = uuid4().hex[:8]
    person_label = validate_identifier(f"Person_{suffix}")
    org_label = validate_identifier(f"Org_{suffix}")
    support_key = f"e2e-comm://{suffix}/support"
    dim = 4
    embedder = _FixedEmbedder(dim=dim, vector=_run_vector(suffix, dim))
    schema = GraphSchema(
        name="e2e_comm",
        version="1",
        entities=[
            EntityType(label=person_label, description="A person."),
            EntityType(label=org_label, description="An organization."),
        ],
        relations=[
            RelationType(
                label="WORKS_AT",
                description="Person works at org.",
                patterns=[(person_label, org_label)],
            )
        ],
    )
    # Provision indexes and constraints like Graph.open does.
    await store.register_labels([person_label, org_label, COMMUNITY_LABEL, CHUNK_LABEL])
    await store.register_relation_types(["WORKS_AT", "MEMBER_OF", "MENTIONED_IN"])
    await store.setup_constraints()
    await store.setup_indexes()
    for lbl in (person_label, org_label, COMMUNITY_LABEL, CHUNK_LABEL):
        await store.ensure_vector_index(
            label=lbl,
            vector_property="embedding",
            dimensions=dim,
            distance=Distance.COSINE,
        )
    for lbl in (person_label, org_label):
        await store.ensure_fulltext_index(label=lbl, properties=["name"])
    await store.ensure_fulltext_index(label=CHUNK_LABEL, properties=["text"])
    await await_indexes(store)
    # Seed two 3-node stars (2 persons + 1 org each), 4 relations.
    p1 = Entity(id=uuid4(), label=person_label, name="Alice")
    p2 = Entity(id=uuid4(), label=person_label, name="Bob")
    o1 = Entity(id=uuid4(), label=org_label, name="Acme")
    p3 = Entity(id=uuid4(), label=person_label, name="Carol")
    p4 = Entity(id=uuid4(), label=person_label, name="Dave")
    o2 = Entity(id=uuid4(), label=org_label, name="Globex")
    for ent in (p1, p2, o1, p3, p4, o2):
        ent.embedding = _run_vector(suffix, dim)
    try:
        await store.upsert_nodes(
            person_label, [e.to_node_record() for e in (p1, p2, p3, p4)]
        )
        await store.upsert_nodes(org_label, [e.to_node_record() for e in (o1, o2)])
        for entity in (p1, p2, p3, p4, o1, o2):
            await store.execute_write(
                upsert_merge_alias_query(),
                {
                    "merge_keys": [entity.merge_key],
                    "entity_id": str(entity.id),
                    "pending_job_id": None,
                },
            )
        # Heavy clique (Acme star) gets weight 3 per edge, light gets 1.
        c1 = uuid4()
        c2 = uuid4()
        c3 = uuid4()
        await store.upsert_relations(
            [
                RelationRecord(
                    id=uuid4(),
                    type="WORKS_AT",
                    start_id=p1.id,
                    end_id=o1.id,
                    properties={
                        "source_chunk_ids": [str(c1), str(c2), str(c3)],
                        "created_at": "2020-01-01T00:00:00",
                    },
                ),
                RelationRecord(
                    id=uuid4(),
                    type="WORKS_AT",
                    start_id=p2.id,
                    end_id=o1.id,
                    properties={
                        "source_chunk_ids": [str(c1), str(c2), str(c3)],
                        "created_at": "2020-01-01T00:00:00",
                    },
                ),
                RelationRecord(
                    id=uuid4(),
                    type="WORKS_AT",
                    start_id=p3.id,
                    end_id=o2.id,
                    properties={
                        "source_chunk_ids": [str(c1)],
                        "created_at": "2020-01-01T00:00:00",
                    },
                ),
                RelationRecord(
                    id=uuid4(),
                    type="WORKS_AT",
                    start_id=p4.id,
                    end_id=o2.id,
                    properties={
                        "source_chunk_ids": [str(c1)],
                        "created_at": "2020-01-01T00:00:00",
                    },
                ),
            ]
        )
        graph = Graph(
            schema=schema,
            graph_store=store,
            embedder=embedder,
            extractor=_FakeWorksAtExtractor(person_label, org_label),
        )
        with patch(
            "agrag.llm.baml_client.b.SummarizeCommunities",
            new_callable=AsyncMock,
            side_effect=_fake_reports,
        ):
            report = await graph.detect_communities(apply=True)
            names_by_id = await _entity_names(store, [person_label, org_label])
            own = _own_communities(report.communities, names_by_id)
            member_sets = sorted(_member_names(c, names_by_id) for c in own)
            assert member_sets == [
                ["Acme", "Alice", "Bob"],
                ["Carol", "Dave", "Globex"],
            ]
            # The Acme star has weight 6, above the LLM floor; Globex has 2.
            titles = {tuple(_member_names(c, names_by_id)): c.title for c in own}
            assert titles[("Acme", "Alice", "Bob")] == "LLM Title"
            assert titles[("Carol", "Dave", "Globex")] != "LLM Title"
            for comm in own:
                assert comm.summary
                assert comm.embedding is not None
                assert len(comm.embedding) == dim
            own_ids = {c.id for c in own}
            # A committed document whose passages mention the seeded entities
            # gives the evidence tools an in-scope passage to return.
            await graph.add(
                documents=[
                    make_document(
                        support_key,
                        "Alice works at Acme. Bob works at Acme. "
                        "Carol works at Globex. Dave works at Globex.",
                    )
                ]
            )
            scope = frozenset({support_key})
            found_entities = await entity_search(
                store,
                embedder,
                "Acme works",
                scope=scope,
                labels=[person_label, org_label],
            )
            assert any(
                hit.name in set(names_by_id.values()) for hit in found_entities.hits
            )
            thematic = await search_themes(
                store, embedder, "Acme community", scope=scope
            )
            thematic_own = {theme.theme_id for theme in thematic.themes} & {
                str(community_id) for community_id in own_ids
            }
            assert thematic_own
            artifact = write_artifact(
                "community_store_seeded",
                {
                    "communities": member_sets,
                    "llm_titled": sorted(
                        m for k, t in titles.items() if t == "LLM Title" for m in k
                    ),
                    "embedding_dim": dim,
                    "entity_search_finds_entity": True,
                    "thematic_finds_own_community": True,
                },
            )
        assert artifact["communities"] == [
            ["Acme", "Alice", "Bob"],
            ["Carol", "Dave", "Globex"],
        ]
        assert artifact["thematic_finds_own_community"] is True
    finally:
        await _cleanup_support_document(store, support_key)
        await _cleanup_community_test_data(store, person_label, org_label)
        await drop_schema_for(store, person_label, org_label)
        await store.close()


@pytest.mark.enable_socket
@pytest.mark.xdist_group(name="community_label")
@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
@pytest.mark.skipif(graspologic_missing, reason="graspologic-native missing")
async def test_community_via_graph_add_e2e() -> None:  # noqa: PLR0915
    """Exclude unrelated graph entities from schema-scoped communities.

    The test leaves a connected star under other labels in the graph while it
    creates communities from its own graph schema.
    """
    # Unique labels keep this test from touching other tests' data.
    suffix = uuid4().hex[:8]
    person_label = validate_identifier(f"Person_{suffix}")
    org_label = validate_identifier(f"Org_{suffix}")
    other_person = validate_identifier(f"Person_{uuid4().hex[:8]}")
    other_org = validate_identifier(f"Org_{uuid4().hex[:8]}")
    support_key = f"e2e-comm://{suffix}/support"
    schema = GraphSchema(
        name="e2e",
        version="1",
        entities=[
            EntityType(label=person_label, description="A person."),
            EntityType(label=org_label, description="An org."),
        ],
        relations=[
            RelationType(
                label="WORKS_AT",
                description="Person works at org.",
                patterns=[(person_label, org_label)],
            )
        ],
    )
    dim = 4
    embedder = _FixedEmbedder(dim=dim, vector=_run_vector(suffix, dim))
    extractor = _FakeWorksAtExtractor(person_label, org_label)
    store = build_test_store()
    graph = await Graph.open(
        schema=schema, graph_store=store, embedder=embedder, extractor=extractor
    )
    try:
        # Unrelated residue: a connected star under other labels.
        await store.register_labels([other_person, other_org])
        residue = [
            Entity(id=uuid4(), label=other_person, name=f"R{i}") for i in range(3)
        ]
        hub = Entity(id=uuid4(), label=other_org, name="ResidueHub")
        for ent in (*residue, hub):
            ent.embedding = [0.1] * dim
        await store.upsert_nodes(other_person, [e.to_node_record() for e in residue])
        await store.upsert_nodes(other_org, [hub.to_node_record()])
        await store.upsert_relations(
            [
                RelationRecord(
                    id=uuid4(),
                    type="WORKS_AT",
                    start_id=e.id,
                    end_id=hub.id,
                    properties={
                        "source_chunk_ids": [str(uuid4())],
                        "created_at": "2020-01-01T00:00:00",
                    },
                )
                for e in residue
            ]
        )
        text = (
            "Alice works at Acme. Bob works at Acme. "
            "Carol works at Globex. Dave works at Globex. "
            "Eve works at Acme. Frank is isolated."
        )
        await graph.add(documents=[make_document(support_key, text)])
        # An entity with no edge must not be loaded.
        isolated = Entity(id=uuid4(), label=person_label, name="Isolated")
        isolated.embedding = [0.1] * dim
        await store.upsert_nodes(person_label, [isolated.to_node_record()])
        names_by_id = await _entity_names(store, [person_label, org_label])
        # Spy loading: capture every id set requested via the "ids"
        # parameter while detect_communities runs. The spy is removed right
        # after, so the chunk reads in engine.search do not fold into it.
        captured_ids: set[str] = set()
        orig_read = store.execute_read

        async def spy_read(query: str, parameters=None, **kw):  # type: ignore[no-untyped-def]
            if parameters and "ids" in parameters:
                captured_ids.update(parameters["ids"])
            return await orig_read(query, parameters, **kw)

        with patch(
            "agrag.llm.baml_client.b.SummarizeCommunities",
            new_callable=AsyncMock,
            side_effect=_fake_reports,
        ):
            store.execute_read = spy_read  # type: ignore[method-assign]
            try:
                report = await graph.detect_communities(apply=True)
            finally:
                store.execute_read = orig_read  # type: ignore[method-assign]
            own = _own_communities(report.communities, names_by_id)
            member_sets = sorted(_member_names(c, names_by_id) for c in own)
            assert member_sets == [
                ["Acme", "Alice", "Bob", "Eve"],
                ["Carol", "Dave", "Globex"],
            ]
            residue_ids = {str(e.id) for e in (*residue, hub)}
            report_member_ids = {
                str(member_id)
                for community in report.communities
                for member_id in community.member_ids
            }
            assert {names_by_id[member_id] for member_id in report_member_ids} == {
                "Acme",
                "Alice",
                "Bob",
                "Carol",
                "Dave",
                "Eve",
                "Globex",
            }
            assert report_member_ids.isdisjoint(residue_ids)
            assert captured_ids.isdisjoint(residue_ids)
            own_needed = {str(i) for i in required_member_ids(own)}
            assert captured_ids & set(names_by_id) == own_needed
            assert str(isolated.id) not in captured_ids
            own_ids = {c.id for c in own}
            scope = frozenset({support_key})
            found_entities = await entity_search(
                store,
                embedder,
                "Acme works",
                scope=scope,
                labels=[person_label, org_label],
            )
            assert any(
                hit.name in set(names_by_id.values()) for hit in found_entities.hits
            )
            thematic = await search_themes(store, embedder, "community", scope=scope)
            thematic_own = {theme.theme_id for theme in thematic.themes} & {
                str(community_id) for community_id in own_ids
            }
            assert thematic_own
            artifact = write_artifact(
                "community_graph_add_respects_schema_scope",
                {
                    "communities": member_sets,
                    "loaded_count": len(captured_ids & set(names_by_id)),
                    "isolated_loaded": False,
                    "unrelated_community_excluded": True,
                    "entity_search_finds_entity": True,
                    "thematic_finds_own_community": True,
                },
            )
        assert artifact["loaded_count"] == len(own_needed)
    finally:
        await _cleanup_support_document(store, support_key)
        await _cleanup_community_test_data(store, person_label, org_label)
        await _cleanup_community_test_data(store, other_person, other_org)
        await drop_schema_for(store, person_label, org_label, other_person, other_org)
        await store.close()


@pytest.mark.enable_socket
@pytest.mark.xdist_group(name="community_label")
@pytest.mark.slow
@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
@pytest.mark.skipif(graspologic_missing, reason="graspologic-native missing")
@pytest.mark.skipif(
    not _llm_endpoint_configured(), reason="LLM endpoint not configured"
)
async def test_community_real_baml() -> None:
    """Real BAML: title non-empty, rating 0-10, findings list, embedding length."""
    store = build_test_store()
    await store.connect()
    suffix = uuid4().hex[:8]
    person_label = validate_identifier(f"Person_{suffix}")
    org_label = validate_identifier(f"Org_{suffix}")
    dim = 4
    embedder = _FixedEmbedder(dim=dim)
    schema = GraphSchema(
        name="e2e_comm_real",
        version="1",
        entities=[
            EntityType(label=person_label, description="A person."),
            EntityType(label=org_label, description="An org."),
        ],
        relations=[
            RelationType(
                label="WORKS_AT",
                description="Person works at org.",
                patterns=[(person_label, org_label)],
            )
        ],
    )
    await store.register_labels([person_label, org_label, COMMUNITY_LABEL, CHUNK_LABEL])
    await store.register_relation_types(["WORKS_AT", "MEMBER_OF", "MENTIONED_IN"])
    await store.setup_constraints()
    await store.setup_indexes()
    for lbl in (person_label, org_label, COMMUNITY_LABEL):
        await store.ensure_vector_index(
            label=lbl,
            vector_property="embedding",
            dimensions=dim,
            distance=Distance.COSINE,
        )
    p1 = Entity(id=uuid4(), label=person_label, name="Alice")
    p2 = Entity(id=uuid4(), label=person_label, name="Bob")
    o1 = Entity(id=uuid4(), label=org_label, name="Acme")
    for ent in (p1, p2, o1):
        ent.embedding = [0.1] * dim
    try:
        await store.upsert_nodes(person_label, [e.to_node_record() for e in (p1, p2)])
        await store.upsert_nodes(org_label, [o1.to_node_record()])
        # Give high weight so BAML path is taken (internal_weight >=5).
        await store.upsert_relations(
            [
                RelationRecord(
                    id=uuid4(),
                    type="WORKS_AT",
                    start_id=p1.id,
                    end_id=o1.id,
                    properties={
                        "source_chunk_ids": [str(uuid4()) for _ in range(3)],
                        "created_at": "2020-01-01T00:00:00",
                    },
                ),
                RelationRecord(
                    id=uuid4(),
                    type="WORKS_AT",
                    start_id=p2.id,
                    end_id=o1.id,
                    properties={
                        "source_chunk_ids": [str(uuid4()) for _ in range(3)],
                        "created_at": "2020-01-01T00:00:00",
                    },
                ),
            ]
        )
        graph = Graph(
            schema=schema,
            graph_store=store,
            embedder=embedder,
            extractor=MagicMock(spec=Extractor),
        )
        report = await graph.detect_communities(apply=True)
        assert len(report.communities) >= 1
        for comm in report.communities:
            assert comm.title.strip() != ""
            assert 0 <= comm.rating <= 10
            assert isinstance(comm.findings, list)
            assert comm.embedding is not None
            assert len(comm.embedding) == dim
    finally:
        await _cleanup_community_test_data(store, person_label, org_label)
        await drop_schema_for(store, person_label, org_label)
        await store.close()
