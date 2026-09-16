"""E2E community detection: ingest -> detect -> both query paths."""

import importlib.util
import os
from collections.abc import Sequence
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from agrag.agents.ledger import Ledger
from agrag.agents.tools import make_tools
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
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.ingestion.community import required_member_ids
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.retrieval.recipes import HYBRID_RERANKED, THEMATIC
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings


neo4j_missing = importlib.util.find_spec("neo4j") is None
graspologic_missing = importlib.util.find_spec("graspologic_native") is None


class _FixedEmbedder(Embedder):
    """Deterministic embedder for e2e tests."""

    model = "fixed"

    def __init__(self, dim: int = 4) -> None:
        """Set the embedding dimension."""
        self._dim = dim

    async def dimensions(self) -> int:
        """Return the configured dimension."""
        return self._dim

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a constant vector for every text."""
        return [[0.1] * self._dim for _ in texts]


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


@pytest.mark.enable_socket
@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
@pytest.mark.skipif(graspologic_missing, reason="graspologic-native missing")
async def test_community_via_store_e2e() -> None:  # noqa: PLR0915
    """Store-seeded seam: upsert -> detect -> HYBRID_RERANKED + THEMATIC."""
    store = build_graph_store("neo4j")
    await store.connect()
    suffix = uuid4().hex[:8]
    person_label = validate_identifier(f"Person_{suffix}")
    org_label = validate_identifier(f"Org_{suffix}")
    dim = 4
    embedder = _FixedEmbedder(dim=dim)
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
    # Seed two 3-node stars (2 persons + 1 org each), 4 relations.
    p1 = Entity(id=uuid4(), label=person_label, name="Alice")
    p2 = Entity(id=uuid4(), label=person_label, name="Bob")
    o1 = Entity(id=uuid4(), label=org_label, name="Acme")
    p3 = Entity(id=uuid4(), label=person_label, name="Carol")
    p4 = Entity(id=uuid4(), label=person_label, name="Dave")
    o2 = Entity(id=uuid4(), label=org_label, name="Globex")
    for ent in (p1, p2, o1, p3, p4, o2):
        ent.embedding = [0.1] * dim
    try:
        await store.upsert_nodes(
            person_label, [e.to_node_record() for e in (p1, p2, p3, p4)]
        )
        await store.upsert_nodes(org_label, [e.to_node_record() for e in (o1, o2)])
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
        fake_report = MagicMock(
            title="LLM Title",
            summary="LLM summary of Acme community.",
            rating=8.5,
            rating_explanation="LLM rated.",
            findings=["finding 1", "finding 2"],
        )
        with (
            patch(
                "agrag.llm.baml_client.b.SummarizeCommunities",
                new_callable=AsyncMock,
                return_value=[fake_report],
            ),
            patch(
                "agrag.retrieval.search_engine.cross_encoder_rerank",
                new_callable=AsyncMock,
                side_effect=lambda q, results, **kw: results,
            ),
        ):
            report = await graph.detect_communities(apply=True)
            assert len(report.communities) == 2
            titles = [c.title for c in report.communities]
            assert "LLM Title" in titles
            # One heuristic, one LLM.
            heuristic = [c for c in report.communities if c.title != "LLM Title"]
            assert len(heuristic) == 1
            assert heuristic[0].summary
            for comm in report.communities:
                assert comm.embedding is not None
                assert len(comm.embedding) == dim
            settings = RetrievalSettings(entity_labels=[person_label, org_label])
            engine = SearchEngine(
                graph_store=store, embedder=embedder, settings=settings
            )
            hybrid = await engine.search("Acme works", HYBRID_RERANKED)
            assert any(isinstance(r.item, Entity) for r in hybrid)
            assert any(isinstance(r.item, Community) for r in hybrid)
            thematic = await engine.search("Acme community", THEMATIC)
            assert any(isinstance(r.item, Community) for r in thematic)
            ledger = Ledger()
            for result in hybrid:
                ledger.cite(result)
            g1 = ledger.resolve("G1")
            assert g1 is not None
            assert isinstance(g1.item, Community)
            # make_tools reuses same engine/ledger.
            tools = make_tools(engine, ledger)
            assert len(tools) == 6
    finally:
        for lbl in (person_label, org_label, COMMUNITY_LABEL):
            await store.execute_write(f"MATCH (n:{lbl}) DETACH DELETE n")
        await store.execute_write(f"MATCH (n:{CHUNK_LABEL}) DETACH DELETE n")
        await store.close()


@pytest.mark.enable_socket
@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
@pytest.mark.skipif(graspologic_missing, reason="graspologic-native missing")
async def test_community_via_graph_add_e2e(e2e_schema: GraphSchema) -> None:
    """Graph.add-seeded seam: hydrate spy equals required_member_ids."""
    # Use unique labels to keep parallelism safe, even though fixture is shared.
    suffix = uuid4().hex[:8]
    person_label = validate_identifier(f"Person_{suffix}")
    org_label = validate_identifier(f"Org_{suffix}")
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
    _ = e2e_schema  # consume fixture to keep pattern, not used for labels
    dim = 4
    embedder = _FixedEmbedder(dim=dim)
    extractor = _FakeWorksAtExtractor(person_label, org_label)
    store = build_graph_store("neo4j")
    graph = await Graph.open(
        schema=schema, graph_store=store, embedder=embedder, extractor=extractor
    )
    try:
        text = (
            "Alice works at Acme. Bob works at Acme. "
            "Carol works at Globex. Dave works at Globex. "
            "Eve works at Acme. Frank is isolated."
        )
        await graph.add(text=text, error_policy="skip")
        # Add an isolated entity that no edge mentions, to prove it is not
        # hydrated. It shares the person label but has no WORKS_AT edge.
        isolated = Entity(id=uuid4(), label=person_label, name="Isolated")
        isolated.embedding = [0.1] * dim
        await store.upsert_nodes(person_label, [isolated.to_node_record()])
        # Spy hydration: capture every id set requested via the "ids"
        # parameter while detect_communities runs, to prove it only reads
        # what required_member_ids says is needed (the public contract),
        # not the whole entity graph. The spy is uninstalled again right
        # after detect_communities finishes so the later chunk-hydration
        # reads in engine.search (also keyed by "ids") do not fold into
        # the same capture.
        captured_ids: set[str] = set()
        orig_read = store.execute_read

        async def spy_read(query: str, parameters=None, **kw):  # type: ignore[no-untyped-def]
            if parameters and "ids" in parameters:
                captured_ids.update(parameters["ids"])
            return await orig_read(query, parameters, **kw)

        fake_report = MagicMock(
            title="LLM Title",
            summary="LLM summary.",
            rating=7.0,
            rating_explanation="ok",
            findings=["f1"],
        )
        with (
            patch(
                "agrag.llm.baml_client.b.SummarizeCommunities",
                new_callable=AsyncMock,
                return_value=[fake_report],
            ),
            patch(
                "agrag.retrieval.search_engine.cross_encoder_rerank",
                new_callable=AsyncMock,
                side_effect=lambda q, results, **kw: results,
            ),
        ):
            store.execute_read = spy_read  # type: ignore[method-assign]
            try:
                report = await graph.detect_communities(apply=True)
            finally:
                store.execute_read = orig_read  # type: ignore[method-assign]
            assert len(report.communities) >= 1
            needed = {str(i) for i in required_member_ids(report.communities)}
            assert captured_ids == needed
            assert str(isolated.id) not in captured_ids
            # Both query paths.
            settings = RetrievalSettings(entity_labels=[person_label, org_label])
            engine = SearchEngine(
                graph_store=store, embedder=embedder, settings=settings
            )
            hybrid = await engine.search("Acme works", HYBRID_RERANKED)
            assert any(isinstance(r.item, Entity) for r in hybrid)
            assert any(isinstance(r.item, Community) for r in hybrid)
            thematic = await engine.search("community", THEMATIC)
            assert any(isinstance(r.item, Community) for r in thematic)
            ledger = Ledger()
            for result in hybrid:
                ledger.cite(result)
            assert ledger.resolve("G1") is not None
    finally:
        for lbl in (person_label, org_label, COMMUNITY_LABEL):
            await store.execute_write(f"MATCH (n:{lbl}) DETACH DELETE n")
        await store.execute_write(f"MATCH (n:{CHUNK_LABEL}) DETACH DELETE n")
        await store.close()


@pytest.mark.enable_socket
@pytest.mark.slow
@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
@pytest.mark.skipif(graspologic_missing, reason="graspologic-native missing")
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
async def test_community_real_baml() -> None:
    """Real BAML: title non-empty, rating 0-10, findings list, embedding length."""
    store = build_graph_store("neo4j")
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
        for lbl in (person_label, org_label, COMMUNITY_LABEL):
            await store.execute_write(f"MATCH (n:{lbl}) DETACH DELETE n")
        await store.execute_write(f"MATCH (n:{CHUNK_LABEL}) DETACH DELETE n")
        await store.close()
