"""Real Neo4j reads must not expose or traverse candidate nodes."""

import importlib.util
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio

from agrag.common.data_models.candidate import CANDIDATE_LABEL, CandidateRecord
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import (
    NODE_IDENTITY_LABEL,
    fetch_all_by_label_query,
    fetch_entity_neighbors_query,
    fetch_relations_between_query,
    load_entities_by_id_query,
)
from agrag.cypher.relations import (
    bfs_expand_query,
    fetch_all_relations_query_cursor,
    relationship_types_from_query,
)
from agrag.cypher.resolution_read import (
    fetch_active_matches_among_ids_query,
    fetch_active_resolved_member_ids_query,
    load_resolved_entities_by_id_query,
)
from agrag.graphdb.base import GraphStore
from agrag.graphdb.errors import GraphStoreConstraintViolationError
from tests.integration._backend import await_indexes, build_test_store


neo4j_missing = importlib.util.find_spec("neo4j") is None

pytestmark = pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")


@pytest_asyncio.fixture
async def store() -> AsyncIterator[GraphStore]:
    """Open the configured Neo4j store for one test module."""
    graph_store = build_test_store()
    await graph_store.connect()
    await graph_store.setup_constraints()
    try:
        yield graph_store
    finally:
        await graph_store.close()


class TestCandidateVisibility:
    """Readers stay inside the identity graph when candidate edges exist."""

    @staticmethod
    async def test_read_paths_skip_candidate_and_keep_real_control_data(  # noqa: PLR0915
        store: GraphStore,  # noqa: PLR0915
    ) -> None:
        """Graph traversals and lookups omit candidates but return real edges."""
        label = f"CandidateProbe{uuid4().hex[:10]}"
        a, b, c, d, chunk_a, chunk_b = (uuid4() for _ in range(6))
        candidates = [
            CandidateRecord(
                kind="relation",
                label=f"KNOWS_{label}",
                confidence=0.6,
                reason="off_pattern",
                chunk_id=chunk_a,
                source_entity_id=a,
                target_entity_id=b,
            ),
            CandidateRecord(
                kind="entity",
                label=f"Contract{label}",
                text="Agreement",
                confidence=0.4,
                reason="entity_band",
                chunk_id=chunk_a,
            ),
            CandidateRecord(
                kind="property",
                label="salary",
                text=label,
                confidence=0.5,
                reason="property",
                chunk_id=chunk_a,
                source_entity_id=a,
            ),
        ]
        candidate_ids = {str(record.id) for record in candidates}
        node_ids = [a, b, c, d, chunk_a, chunk_b]
        entity_names = {a: "A", b: "B", c: "C", d: "D"}
        try:
            entities = [
                NodeRecord(
                    id=node_id,
                    labels=[label] if node_id in {a, b, c, d} else ["Chunk"],
                    properties={
                        "name": entity_names[node_id],
                        "embedding": [1.0, 0.0, 0.0],
                    }
                    if node_id in entity_names
                    else {},
                )
                for node_id in node_ids
            ]
            await store.upsert_nodes(label, entities[:4])
            await store.upsert_nodes("Chunk", entities[4:])
            await store.upsert_relations(
                [
                    RelationRecord(
                        id=uuid4(),
                        type="MENTIONED_IN",
                        start_id=chunk_a,
                        end_id=a,
                        properties={},
                    ),
                    RelationRecord(
                        id=uuid4(),
                        type="MENTIONED_IN",
                        start_id=chunk_b,
                        end_id=b,
                        properties={},
                    ),
                    RelationRecord(
                        id=uuid4(),
                        type="KNOWS",
                        start_id=c,
                        end_id=d,
                        properties={},
                    ),
                ]
            )
            result = await store.upsert_candidates(candidates)
            assert result.written == 3
            candidate_shape = await store.execute_read(
                f"MATCH (candidate:{CANDIDATE_LABEL}) "
                "WHERE candidate.id IN $ids "
                "RETURN collect(DISTINCT labels(candidate)) AS labels",
                {"ids": sorted(candidate_ids)},
            )
            edge_types = await store.execute_read(
                f"MATCH (candidate:{CANDIDATE_LABEL})-[edge]->() "
                "WHERE candidate.id IN $ids RETURN DISTINCT type(edge) AS type",
                {"ids": sorted(candidate_ids)},
            )
            assert candidate_shape == [{"labels": [[CANDIDATE_LABEL]]}]
            assert {row["type"] for row in edge_types} == {
                "EVIDENCED_BY",
                "SOURCE",
                "TARGET",
            }

            await store.ensure_vector_index(
                label=label,
                vector_property="embedding",
                dimensions=3,
                distance=Distance.COSINE,
            )
            await await_indexes(store)

            hits = await store.vector_search(
                label=label,
                vector_property="embedding",
                query_vector=[1.0, 0.0, 0.0],
            )
            assert {str(hit.id) for hit in hits} == {str(node) for node in (a, b, c, d)}
            with pytest.raises(ValueError, match="reserved"):
                fetch_all_by_label_query(CANDIDATE_LABEL)
            with pytest.raises(ValueError, match="reserved"):
                await store.ensure_vector_index(
                    label=CANDIDATE_LABEL,
                    vector_property="embedding",
                    dimensions=3,
                    distance=Distance.COSINE,
                )
            assert (
                await store.execute_read(
                    load_entities_by_id_query(), {"ids": sorted(candidate_ids)}
                )
                == []
            )

            neighbors = await store.execute_read(
                fetch_entity_neighbors_query(),
                {"ids": [str(a)], "exclude_types": ["MENTIONED_IN"], "limit": 10},
            )
            control_neighbors = await store.execute_read(
                fetch_entity_neighbors_query(),
                {"ids": [str(c)], "exclude_types": [], "limit": 10},
            )
            assert neighbors == []
            assert [row["neighbor_name"] for row in control_neighbors] == ["D"]

            for relation_types in (None, ["SOURCE", "TARGET", "EVIDENCED_BY"]):
                query, params = bfs_expand_query(depth=4, relation_types=relation_types)
                reached = await store.execute_read(
                    query, {**params, "seed_ids": [str(a)], "job_id": None}
                )
                assert str(b) not in {str(row["id"]) for row in reached}
                assert not candidate_ids & {str(row["id"]) for row in reached}
            query, params = bfs_expand_query(depth=2)
            control_reached = await store.execute_read(
                query, {**params, "seed_ids": [str(c)], "job_id": None}
            )
            assert {str(row["id"]) for row in control_reached} == {str(d)}

            assert (
                await store.execute_read(
                    store.shortest_path_distance_query(),
                    {"seed_ids": [str(a)], "target_ids": [str(b)]},
                )
                == []
            )
            assert [
                row["dist"]
                for row in await store.execute_read(
                    store.shortest_path_distance_query(),
                    {"seed_ids": [str(c)], "target_ids": [str(d)]},
                )
            ] == [1]

            assert (
                await store.execute_read(
                    relationship_types_from_query(),
                    {"seed_ids": [str(a)], "job_id": None},
                )
                == []
            )
            assert [
                row["rel_type"]
                for row in await store.execute_read(
                    relationship_types_from_query(),
                    {"seed_ids": [str(c)], "job_id": None},
                )
            ] == ["KNOWS"]
            assert (
                await store.execute_read(
                    fetch_relations_between_query("SOURCE"),
                    {
                        "pairs": [
                            {"source_id": str(candidates[0].id), "target_id": str(a)}
                        ]
                    },
                )
                == []
            )

            for builder, extra in (
                (fetch_active_matches_among_ids_query, {"job_id": None}),
                (load_resolved_entities_by_id_query, {"job_id": None}),
                (fetch_active_resolved_member_ids_query, {"job_id": None}),
            ):
                assert (
                    await store.execute_read(
                        builder(), {**extra, "ids": sorted(candidate_ids)}
                    )
                    == []
                )

            rows = await store.execute_read(
                fetch_all_relations_query_cursor(),
                {
                    "last_a": "",
                    "last_b": "",
                    "last_type": "",
                    "last_rel_id": "",
                    "limit": 100000,
                },
            )
            relevant = {str(node) for node in (a, b, c, d)} | candidate_ids
            pairs = {
                (row["source_id"], row["target_id"])
                for row in rows
                if row["source_id"] in relevant or row["target_id"] in relevant
            }
            assert pairs == {(str(c), str(d))}

            await store.setup_constraints()
            duplicate_id = str(uuid4())
            await store.execute_write(
                f"CREATE (:{CANDIDATE_LABEL} {{id: $id}})", {"id": duplicate_id}
            )
            with pytest.raises(GraphStoreConstraintViolationError):
                await store.execute_write(
                    f"CREATE (:{CANDIDATE_LABEL} {{id: $id}})", {"id": duplicate_id}
                )
            await store.execute_write(
                f"MATCH (c:{CANDIDATE_LABEL} {{id: $id}}) DELETE c",
                {"id": duplicate_id},
            )

            for query in (
                f"MATCH (n:{label}) WHERE n._pending_job_id IS NULL RETURN n",
                f"MATCH (n) WHERE n:{NODE_IDENTITY_LABEL} "
                "AND n._pending_job_id IS NULL RETURN n",
            ):
                returned = await store.execute_read(query)
                assert not any(
                    candidate in repr(returned) for candidate in candidate_ids
                )
        finally:
            await store.execute_write(
                f"MATCH (c:{CANDIDATE_LABEL}) WHERE c.id IN $ids DETACH DELETE c",
                {"ids": sorted(candidate_ids)},
            )
            await store.execute_write(
                "MATCH (n) WHERE n.id IN $ids DETACH DELETE n",
                {"ids": [str(node) for node in node_ids]},
            )
