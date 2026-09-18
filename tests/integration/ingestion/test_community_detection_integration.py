"""Integration tests for community detection against real Neo4j.

Run against Docker Compose Neo4j from ``docker/docker-compose.ci.yml``
(``make dev-services-up``). ``NEO4J_AUTH=neo4j/ci-test-password``.
"""

import asyncio
import contextlib
import hashlib
import importlib.util
import math
import sys
from collections.abc import Sequence
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.community import COMMUNITY_LABEL, Community
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType
from agrag.common.data_models.relation import Relation
from agrag.cypher.entities import hydrate_entities_by_id_query, validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.ingestion.community import (
    CommunityDetectionMissingExtraError,
    compute_communities,
    delete_all_communities,
    fetch_relation_edges,
    generate_community_reports,
    required_member_ids,
)
from agrag.ingestion.extract import ExtractionResult, Extractor
from agrag.ingestion.graph import Graph, _parse_entity_node
from agrag.ingestion.reports import CommunityDetectionReport
from agrag.ingestion.stats import StageFailure  # noqa: F401


neo4j_missing = importlib.util.find_spec("neo4j") is None
graspologic_native_missing = importlib.util.find_spec("graspologic_native") is None
baml_missing = importlib.util.find_spec("baml_py") is None


class _FixedEmbedder(Embedder):
    """Deterministic embedder for tests."""

    model = "fixed"

    def __init__(self, dim: int = 4) -> None:
        """Store dimension."""
        self._dim = dim

    async def dimensions(self) -> int:
        """Return embedding dimension."""
        return self._dim

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return deterministic vectors per text."""
        vectors: list[list[float]] = []
        for text in texts:
            h = int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big") % 1000
            vectors.append(
                [
                    float(h % 10) / 10.0,
                    float((h // 10) % 10) / 10.0,
                    float((h // 100) % 10) / 10.0,
                    0.5 if self._dim == 4 else 0.0,
                ][: self._dim]
            )
        return vectors


class _NoopExtractor(Extractor):
    """Extractor that returns no entities."""

    async def extract(self, chunk, schema) -> ExtractionResult:  # type: ignore[no-untyped-def]
        """Return empty result."""
        return ExtractionResult(entities=[], relations=[], extractor_name="noop")


def _schema_for(label: str) -> GraphSchema:
    """Return a schema with one entity and one relation."""
    return GraphSchema(
        name="test",
        version="1",
        entities=[EntityType(label=label, description="test entity")],
        relations=[
            RelationType(
                label="RELATED_TO",
                description="test relation",
                patterns=[(label, label)],
            )
        ],
    )


async def _seed_small_graph(
    store, label: str, *, weight: int = 2
) -> tuple[list[Entity], list[Relation]]:
    """Create 6 entities in 2 cliques and 4 relations.

    Each clique has 3 nodes. Clique A: 0-1, 1-2. Clique B: 3-4, 4-5.
    Weight comes from ``source_chunk_ids`` length.

    Args:
        store: The graph store.
        label: Entity label to use.
        weight: Attestation count per relation.

    Returns:
        Entities and relations written.
    """
    entities = [Entity(id=uuid4(), label=label, name=f"N{i}") for i in range(6)]
    await store.upsert_nodes(label, [e.to_node_record() for e in entities])

    def _chunk_ids(n: int) -> list[UUID]:
        return [uuid4() for _ in range(n)]

    relations = [
        Relation(
            id=uuid4(),
            type="RELATED_TO",
            source_id=entities[0].id,
            target_id=entities[1].id,
            source_chunk_ids=_chunk_ids(weight),
        ),
        Relation(
            id=uuid4(),
            type="RELATED_TO",
            source_id=entities[1].id,
            target_id=entities[2].id,
            source_chunk_ids=_chunk_ids(weight),
        ),
        Relation(
            id=uuid4(),
            type="RELATED_TO",
            source_id=entities[3].id,
            target_id=entities[4].id,
            source_chunk_ids=_chunk_ids(weight),
        ),
        Relation(
            id=uuid4(),
            type="RELATED_TO",
            source_id=entities[4].id,
            target_id=entities[5].id,
            source_chunk_ids=_chunk_ids(weight),
        ),
    ]
    await store.upsert_relations([r.to_relation_record() for r in relations])
    # Ensure id constraints for this label (idempotent).
    with contextlib.suppress(Exception):
        await store.setup_constraints()
    return entities, relations


async def _seed_isolated(store, label: str) -> Entity:
    """Create one isolated entity.

    Args:
        store: The graph store.
        label: Entity label.

    Returns:
        The isolated entity.
    """
    ent = Entity(id=uuid4(), label=label, name="Isolated")
    await store.upsert_nodes(label, [ent.to_node_record()])
    with contextlib.suppress(Exception):
        await store.setup_constraints()
    return ent


async def _seed_two_weight_cliques(
    store, label: str
) -> tuple[list[Entity], list[Relation]]:
    """Create 2 cliques with different internal weights.

    Clique A weight 1 per edge (heuristic), clique B weight 6 per edge
    (LLM-qualifying). This yields one community below threshold and one
    above.

    Args:
        store: The graph store.
        label: Entity label.

    Returns:
        Entities and relations.
    """
    entities = [Entity(id=uuid4(), label=label, name=f"W{i}") for i in range(6)]
    await store.upsert_nodes(label, [e.to_node_record() for e in entities])

    def _ids(n: int) -> list[UUID]:
        return [uuid4() for _ in range(n)]

    relations = [
        Relation(
            id=uuid4(),
            type="RELATED_TO",
            source_id=entities[0].id,
            target_id=entities[1].id,
            source_chunk_ids=_ids(1),
        ),
        Relation(
            id=uuid4(),
            type="RELATED_TO",
            source_id=entities[1].id,
            target_id=entities[2].id,
            source_chunk_ids=_ids(1),
        ),
        Relation(
            id=uuid4(),
            type="RELATED_TO",
            source_id=entities[3].id,
            target_id=entities[4].id,
            source_chunk_ids=_ids(6),
        ),
        Relation(
            id=uuid4(),
            type="RELATED_TO",
            source_id=entities[4].id,
            target_id=entities[5].id,
            source_chunk_ids=_ids(6),
        ),
    ]
    await store.upsert_relations([r.to_relation_record() for r in relations])
    with contextlib.suppress(Exception):
        await store.setup_constraints()
    return entities, relations


async def _count_communities(store) -> int:
    """Return count of Community nodes."""
    rows = await store.execute_read(f"MATCH (n:{COMMUNITY_LABEL}) RETURN count(n) AS c")
    return int(rows[0]["c"]) if rows else 0


async def _fetch_community_ids(store) -> set[str]:
    """Return ids of Community nodes."""
    rows = await store.execute_read(f"MATCH (n:{COMMUNITY_LABEL}) RETURN n.id AS id")
    return {str(r["id"]) for r in rows}


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestCommunityDetectionIntegration:
    """Community detection against real Neo4j via Graph.detect_communities."""

    @pytest.fixture(autouse=True)
    async def _setup(self):
        """Set up store and unique labels per test."""
        self.store = build_graph_store("neo4j")
        await self.store.connect()
        self.label = validate_identifier(f"Ent_{uuid4().hex[:8]}")
        self.schema = _schema_for(self.label)
        self.embedder = _FixedEmbedder(dim=4)
        self.graph = Graph(
            schema=self.schema,
            graph_store=self.store,
            embedder=self.embedder,
            extractor=_NoopExtractor(),
        )
        yield
        # Cleanup: entities, communities, aliases.
        with contextlib.suppress(Exception):
            await self.store.execute_write(f"MATCH (n:{self.label}) DETACH DELETE n")
        with contextlib.suppress(Exception):
            await self.store.execute_write(
                f"MATCH (n:{COMMUNITY_LABEL}) DETACH DELETE n"
            )
        with contextlib.suppress(Exception):
            await self.store.execute_write(
                "MATCH (a:_AgragMergeAlias) WHERE a.merge_key STARTS WITH $p DELETE a",
                {"p": f"{self.label}:"},
            )
        await self.store.close()

    @pytest.mark.skipif(
        graspologic_native_missing, reason="graspologic-native not installed"
    )
    async def test_dry_run_does_not_write(self) -> None:
        """Dry run returns communities but writes none."""
        await _seed_small_graph(self.store, self.label)
        report = await self.graph.detect_communities(apply=False)
        assert isinstance(report, CommunityDetectionReport)
        assert len(report.communities) == 2
        assert report.applied is False
        assert await _count_communities(self.store) == 0
        # No MEMBER_OF edges.
        rows = await self.store.execute_read(
            "MATCH ()-[r:MEMBER_OF]->() RETURN count(r) AS c"
        )
        assert rows[0]["c"] == 0

    @pytest.mark.skipif(
        graspologic_native_missing, reason="graspologic-native not installed"
    )
    async def test_apply_writes_communities_and_member_of(self) -> None:
        """Apply writes Community nodes and MEMBER_OF edges."""
        await _seed_small_graph(self.store, self.label)
        report = await self.graph.detect_communities(apply=True)
        assert report.applied is True
        assert len(report.communities) == 2
        assert await _count_communities(self.store) == 2
        rows = await self.store.execute_read(
            "MATCH ()-[r:MEMBER_OF]->() RETURN count(r) AS c"
        )
        # 6 members across 2 communities.
        assert rows[0]["c"] == 6
        # Communities have embedding and rating.
        rows = await self.store.execute_read(
            f"MATCH (n:{COMMUNITY_LABEL}) RETURN n.embedding AS emb, n.rating AS rating"
        )
        for row in rows:
            assert row["emb"] is not None
            assert isinstance(row["rating"], (int, float))

    @pytest.mark.skipif(
        graspologic_native_missing, reason="graspologic-native not installed"
    )
    async def test_full_recompute_replaces(self) -> None:
        """Second apply deletes prior communities before writing new ones."""
        await _seed_small_graph(self.store, self.label)
        first = await self.graph.detect_communities(apply=True)
        first_ids = {str(c.id) for c in first.communities}
        assert len(first_ids) == 2
        # Add a new isolated clique by adding 3 more entities forming a third
        # community: we DETACH DELETE old entities and seed fresh with 3 cliques.
        await self.store.execute_write(f"MATCH (n:{self.label}) DETACH DELETE n")
        # Create 9 entities -> 3 cliques via manual seeding.
        entities = [
            Entity(id=uuid4(), label=self.label, name=f"R{i}") for i in range(9)
        ]
        await self.store.upsert_nodes(
            self.label, [e.to_node_record() for e in entities]
        )
        rels = []
        for start in (0, 3, 6):
            for offset in (0, 1):
                rels.append(
                    Relation(
                        id=uuid4(),
                        type="RELATED_TO",
                        source_id=entities[start + offset].id,
                        target_id=entities[start + offset + 1].id,
                        source_chunk_ids=[uuid4(), uuid4()],
                    ).to_relation_record()
                )
        await self.store.upsert_relations(rels)
        second = await self.graph.detect_communities(apply=True)
        assert len(second.communities) == 3
        stored_ids = await _fetch_community_ids(self.store)
        assert stored_ids == {str(c.id) for c in second.communities}
        assert stored_ids.isdisjoint(first_ids)

    @pytest.mark.skipif(
        graspologic_native_missing, reason="graspologic-native not installed"
    )
    async def test_empty_graph(self) -> None:
        """Empty graph yields no communities; apply clears stale."""
        report = await self.graph.detect_communities(apply=True)
        assert report.communities == []
        # CH-002: apply=True on empty must still delete stale Communities,
        # so applied is True even though no new communities.
        assert report.applied is True
        assert report.failures == []
        assert await _count_communities(self.store) == 0

    @pytest.mark.skipif(
        graspologic_native_missing, reason="graspologic-native not installed"
    )
    async def test_isolated_entity(self) -> None:
        """Isolated entity produces no community."""
        await _seed_isolated(self.store, self.label)
        # Also seed normal graph to ensure isolated not counted.
        report = await self.graph.detect_communities(apply=True)
        assert report.communities == []
        assert await _count_communities(self.store) == 0

    @pytest.mark.skipif(
        graspologic_native_missing, reason="graspologic-native not installed"
    )
    async def test_isolated_entity_with_clique(self) -> None:
        """Isolated entity alongside cliques does not join a community."""
        await _seed_small_graph(self.store, self.label)
        await _seed_isolated(self.store, self.label)
        report = await self.graph.detect_communities(apply=True)
        # Still 2 communities; isolated has degree 0 and is excluded.
        assert len(report.communities) == 2
        member_ids = {mid for c in report.communities for mid in c.member_ids}
        # Isolated entity not present.
        iso_rows = await self.store.execute_read(
            f"MATCH (n:{self.label} {{name: 'Isolated'}}) RETURN n.id AS id"
        )
        assert len(iso_rows) == 1
        assert UUID(iso_rows[0]["id"]) not in member_ids

    async def test_batch_delete_over_1000(self) -> None:
        """delete_all_communities batches with small batch_size."""
        # Create 5 communities directly.
        comms = [
            Community(
                id=uuid4(),
                title=f"T{i}",
                summary=f"S{i}",
                rating=5.0,
                rating_explanation="e",
                member_ids=[],
                internal_weight=1.0,
            )
            for i in range(5)
        ]
        await self.store.upsert_nodes(
            COMMUNITY_LABEL, [c.to_node_record() for c in comms]
        )
        assert await _count_communities(self.store) == 5
        # _DEFAULT_DELETE_BATCH_SIZE is bound into the batch_size default
        # at function-definition time, so patching the module constant
        # after import has no effect on delete_all_communities; pass
        # batch_size explicitly to exercise the batching loop.
        await delete_all_communities(self.store, batch_size=2)
        assert await _count_communities(self.store) == 0

    @pytest.mark.skipif(
        graspologic_native_missing, reason="graspologic-native not installed"
    )
    @pytest.mark.skipif(baml_missing, reason="baml extra not installed")
    async def test_heuristic_vs_llm_branch_and_call_counts(self) -> None:
        """Heuristic for low weight, LLM for high weight, batching and truncate.

        Qualifying communities (internal_weight >= 5) get LLM reports batched;
        others get heuristic rating = internal_weight/2. Truncation to
        max_members_per_prompt is verified.
        """
        await _seed_two_weight_cliques(self.store, self.label)
        # Compute communities to inspect weights.

        edges = await fetch_relation_edges(self.store)
        comms = await asyncio.to_thread(compute_communities, edges)
        assert len(comms) == 2
        # Identify heuristic vs qualifying.
        heuristic = [c for c in comms if c.internal_weight < 5.0]
        qualifying = [c for c in comms if c.internal_weight >= 5.0]
        assert len(heuristic) == 1
        assert len(qualifying) == 1
        # Check heuristic rating after direct call.

        needed = required_member_ids(comms)
        rows = await self.store.execute_read(
            hydrate_entities_by_id_query(), {"ids": [str(i) for i in needed]}
        )

        entities_by_id = {
            ent.id: ent
            for row in rows
            if (ent := _parse_entity_node(row.get("n", row))) is not None  # type: ignore[arg-type]
        }
        # Patch LLM to count calls and verify truncation.
        batch_size = 1
        max_members = 2
        # Make heuristic and qualifying communities have many members for
        # truncation test: extend member_ids artificially.
        extra_ids = [uuid4() for _ in range(5)]
        # Add dummy entities for truncation.
        for eid in extra_ids:
            entities_by_id[eid] = Entity(id=eid, label=self.label, name=f"Extra{eid}")
        qualifying[0].member_ids = list(qualifying[0].member_ids) + extra_ids
        # Need qualifying batch count: make 2 qualifying communities for math.
        # Duplicate qualifying.
        second_q = Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0.0,
            rating_explanation="",
            member_ids=qualifying[0].member_ids[:],
            internal_weight=10.0,
        )
        all_comms = heuristic + qualifying + [second_q]
        qualifying_count = 2  # qualifying + second_q
        expected_calls = math.ceil(qualifying_count / batch_size)

        captured: dict[str, list] = {}

        async def fake_summarize(communities):  # type: ignore[no-untyped-def]
            captured["inputs"] = communities
            return [
                MagicMock(
                    title=f"T{i}",
                    summary=f"S{i}",
                    rating=8.0,
                    rating_explanation="llm",
                    findings=[f"f{i}"],
                )
                for i in range(len(communities))
            ]

        with patch("agrag.llm.baml_client.b.SummarizeCommunities", new=fake_summarize):
            # Directly call to control batch_size.
            failures = await generate_community_reports(
                all_comms,
                entities_by_id,
                batch_size=batch_size,
                max_members_per_prompt=max_members,
            )
            assert failures == []
            # Verify truncation: each input should have max_members entries.
            for inp in captured["inputs"]:
                assert len(inp.entity_summaries) == max_members
        # Re-verify call count with AsyncMock.
        mock = AsyncMock(
            side_effect=[
                [
                    MagicMock(
                        title="T0",
                        summary="S0",
                        rating=8.0,
                        rating_explanation="e",
                        findings=[],
                    )
                ],
                [
                    MagicMock(
                        title="T1",
                        summary="S1",
                        rating=8.0,
                        rating_explanation="e",
                        findings=[],
                    )
                ],
            ]
        )
        # Need fresh communities because previous call mutated them.
        all_comms2 = [
            Community(
                id=uuid4(),
                title="",
                summary="",
                rating=0.0,
                rating_explanation="",
                member_ids=heuristic[0].member_ids[:],
                internal_weight=heuristic[0].internal_weight,
            ),
            Community(
                id=uuid4(),
                title="",
                summary="",
                rating=0.0,
                rating_explanation="",
                member_ids=qualifying[0].member_ids[:],
                internal_weight=10.0,
            ),
            Community(
                id=uuid4(),
                title="",
                summary="",
                rating=0.0,
                rating_explanation="",
                member_ids=second_q.member_ids[:],
                internal_weight=10.0,
            ),
        ]
        with patch("agrag.llm.baml_client.b.SummarizeCommunities", mock):
            await generate_community_reports(
                all_comms2, entities_by_id, batch_size=batch_size
            )
            assert mock.call_count == expected_calls
        # Heuristic rating check.
        assert all_comms2[0].rating == min(10.0, heuristic[0].internal_weight / 2)

    @pytest.mark.skipif(
        graspologic_native_missing, reason="graspologic-native not installed"
    )
    @pytest.mark.skipif(baml_missing, reason="baml extra not installed")
    async def test_short_response_fallback(self) -> None:
        """Short LLM response falls back to heuristic for leftovers."""
        eids = [uuid4() for _ in range(4)]
        entities_by_id = {
            eid: Entity(id=eid, label=self.label, name=f"N{i}")
            for i, eid in enumerate(eids)
        }
        c1 = Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0.0,
            rating_explanation="",
            member_ids=eids[:2],
            internal_weight=10.0,
        )
        c2 = Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0.0,
            rating_explanation="",
            member_ids=eids[2:],
            internal_weight=10.0,
        )
        with patch(
            "agrag.llm.baml_client.b.SummarizeCommunities", new_callable=AsyncMock
        ) as mock:
            mock.return_value = [
                MagicMock(
                    title="T1",
                    summary="S1",
                    rating=8.0,
                    rating_explanation="e",
                    findings=[],
                )
            ]
            await generate_community_reports([c1, c2], entities_by_id, batch_size=2)
            assert c1.title == "T1"
            # c2 fell back to heuristic, so title non-empty and rating heuristic.
            assert c2.title
            assert c2.summary
            assert c2.rating == min(10.0, c2.internal_weight / 2)

    @pytest.mark.skipif(
        graspologic_native_missing, reason="graspologic-native not installed"
    )
    @pytest.mark.skipif(baml_missing, reason="baml extra not installed")
    async def test_batch_exception_creates_failures(self) -> None:
        """Batch exception creates StageFailure per community and fallback."""
        eids = [uuid4() for _ in range(2)]
        entities_by_id = {
            eid: Entity(id=eid, label=self.label, name=f"N{i}")
            for i, eid in enumerate(eids)
        }
        comm = Community(
            id=uuid4(),
            title="",
            summary="",
            rating=0.0,
            rating_explanation="",
            member_ids=eids,
            internal_weight=10.0,
        )
        with patch(
            "agrag.llm.baml_client.b.SummarizeCommunities",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = Exception("down")
            failures = await generate_community_reports([comm], entities_by_id)
            assert len(failures) == 1
            assert failures[0].item_id == str(comm.id)
            # Heuristic fallback applied.
            assert comm.title

    async def test_missing_extra(self) -> None:
        """Missing graspologic-native raises CommunityDetectionMissingExtraError."""
        with (
            patch.dict(sys.modules, {"graspologic_native": None}),
            pytest.raises(CommunityDetectionMissingExtraError),
        ):
            compute_communities([("a", "b", 1.0)])
        # Also via Graph.detect_communities — seed so it reaches compute.
        await _seed_small_graph(self.store, self.label)
        with (
            patch.dict(sys.modules, {"graspologic_native": None}),
            pytest.raises(CommunityDetectionMissingExtraError),
        ):
            await self.graph.detect_communities(apply=False)

    @pytest.mark.skipif(
        graspologic_native_missing, reason="graspologic-native not installed"
    )
    async def test_determinism_seed(self) -> None:
        """Same seed yields same communities; different seed may differ."""
        await _seed_small_graph(self.store, self.label)
        first = await self.graph.detect_communities(apply=False, seed=42)
        second = await self.graph.detect_communities(apply=False, seed=42)

        # Compare sorted member sets.
        def _sorted(communities):  # type: ignore[no-untyped-def]
            return sorted([sorted(str(m) for m in c.member_ids) for c in communities])

        assert _sorted(first.communities) == _sorted(second.communities)
        # Seed None uses native default; just ensure no crash.
        await self.graph.detect_communities(apply=False, seed=None)

    @pytest.mark.skipif(
        graspologic_native_missing, reason="graspologic-native not installed"
    )
    async def test_vector_index_provisioned_via_Graph_open(self) -> None:
        """Graph.open provisions Community vector index; SHOW INDEXES has it."""
        # Use fresh store via Graph.open.
        store2 = build_graph_store("neo4j")
        label2 = validate_identifier(f"Ent2_{uuid4().hex[:8]}")
        schema2 = _schema_for(label2)
        embedder = _FixedEmbedder(dim=4)
        await Graph.open(
            schema=schema2,
            graph_store=store2,
            embedder=embedder,
            extractor=_NoopExtractor(),
        )
        try:
            query = (
                "SHOW INDEXES YIELD name, labelsOrTypes, properties "
                "RETURN name, labelsOrTypes, properties"
            )
            rows = await store2.execute_read(query)
            # Find Community embedding index.
            found = any(
                COMMUNITY_LABEL in (r.get("labelsOrTypes") or [])
                and "embedding" in (r.get("properties") or [])
                for r in rows
            )
            assert found, f"Community vector index not found: {rows}"
            # Also entity label index.
            found_ent = any(
                label2 in (r.get("labelsOrTypes") or [])
                and "embedding" in (r.get("properties") or [])
                for r in rows
            )
            assert found_ent
        finally:
            with contextlib.suppress(Exception):
                await store2.execute_write(f"MATCH (n:{label2}) DETACH DELETE n")
            with contextlib.suppress(Exception):
                await store2.execute_write(
                    f"MATCH (n:{COMMUNITY_LABEL}) DETACH DELETE n"
                )
            await store2.close()
