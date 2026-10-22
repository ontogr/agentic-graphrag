"""Integration tests for merge mechanics against a real Neo4j instance.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). The ``skipif``
only guards the missing extra; with the extra installed the tests expect a
reachable Neo4j at the default ``NEO4J_URI``.
"""

import importlib.util
from uuid import uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.graph_record import RelationRecord
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.cypher.cutover_job_write import fold_pending_relations_query
from agrag.cypher.entities import validate_identifier
from agrag.graphdb.errors import GraphStoreAliasConflictError
from agrag.ingestion.merge import apply_merge, compute_merge
from tests.integration._backend import build_test_store


neo4j_missing = importlib.util.find_spec("neo4j") is None


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestApplyMergeAliasConflictIntegration:
    """Regression coverage for a merge-key alias claimed by another entity."""

    async def test_bob_racing_robert_conflicts_and_commits_nothing(self) -> None:
        """A second writer claiming an owned merge-key alias fails atomically.

        Simulates the race deterministically, in sequence: one writer
        commits a canonical entity named "Bob" first; a second writer then
        separately resolves mentions "Robert" and "Bob" as the same entity
        and tries to accept "Bob" as an alias. Neither writer's own node
        merge_key collides (their own names differ), so nothing at the
        database level rejects the second write; the alias-ownership check
        raises instead, and the rejected transaction must have committed
        nothing: plan_b's own node never becomes a second live entity.
        """
        store = build_test_store()
        await store.connect()
        label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label=label, description="test")],
            relations=[],
        )
        try:
            await store.ensure_unique_constraint(label=label, properties=["merge_key"])

            bob_mention = ExtractedEntity(
                chunk_id=uuid4(), label=label, text="Bob", char_start=0, char_end=3
            )
            plan_a, _ = await compute_merge(
                existing_entities=[], mentions=[bob_mention], schema=schema
            )
            await apply_merge(plan_a, graph_store=store, schema=schema)

            robert_mention = ExtractedEntity(
                chunk_id=uuid4(), label=label, text="Robert", char_start=0, char_end=6
            )
            plan_b, _ = await compute_merge(
                existing_entities=[],
                mentions=[robert_mention, bob_mention],
                schema=schema,
            )
            assert plan_b.survivor.id != plan_a.survivor.id

            with pytest.raises(GraphStoreAliasConflictError) as exc_info:
                await apply_merge(plan_b, graph_store=store, schema=schema)
            assert exc_info.value.conflicts == {f"{label}:bob": str(plan_a.survivor.id)}

            # The rejected transaction must have committed nothing: plan_b's
            # own node never becomes a second live entity for "Bob".
            rejected_rows = await store.execute_read(
                f"MATCH (n:{label} {{id: $id}}) RETURN n",
                {"id": str(plan_b.survivor.id)},
            )
            assert rejected_rows == []

            count_rows = await store.execute_read(
                f"MATCH (n:{label}) RETURN count(n) AS c", {}
            )
            assert count_rows[0]["c"] == 1

            robert_lookup = await store.execute_read(
                f"MATCH (a:_MergeAlias {{merge_key: $mk}}) "
                f"MATCH (n:{label} {{id: a.entity_id}}) RETURN n.id AS id",
                {"mk": f"{label}:robert"},
            )
            assert robert_lookup == []
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.execute_write(
                "MATCH (a:_MergeAlias) WHERE a.merge_key STARTS WITH $prefix DELETE a",
                {"prefix": f"{label}:"},
            )
            await store.close()


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestRelationProvenanceIntegration:
    """Relation confidence and extractors are kept across repeated upserts."""

    @staticmethod
    async def test_keeps_the_largest_confidence_and_unions_extractors() -> None:
        """Repeated writes keep the highest confidence and both extractor names."""
        store = build_test_store()
        await store.connect()
        label = validate_identifier(f"Thing_{uuid4().hex[:8]}")
        rel_type = validate_identifier(f"LINKS_{uuid4().hex[:8]}")
        alpha = Entity(id=uuid4(), label=label, name="Alpha")
        beta = Entity(id=uuid4(), label=label, name="Beta")
        relation_id = uuid4()

        def _record(properties: dict[str, object]) -> RelationRecord:
            return RelationRecord(
                id=relation_id,
                type=rel_type,
                start_id=alpha.id,
                end_id=beta.id,
                properties=properties,
            )

        async def _read_edge() -> dict[str, object]:
            [row] = await store.execute_read(
                f"MATCH ()-[r:{rel_type} {{id: $id}}]->() "
                "RETURN r.confidence AS confidence, r.extractors AS extractors",
                {"id": str(relation_id)},
            )
            return row

        try:
            await store.upsert_nodes(
                label, [alpha.to_node_record(), beta.to_node_record()]
            )
            await store.upsert_relations(
                [_record({"confidence": 0.6, "extractors": ["gliner"]})]
            )
            await store.upsert_relations(
                [_record({"confidence": 0.4, "extractors": ["llm"]})]
            )

            edge = await _read_edge()
            assert edge["confidence"] == 0.6
            assert edge["extractors"] == ["gliner", "llm"]

            await store.upsert_relations([_record({"extractors": ["gliner"]})])

            edge = await _read_edge()
            assert edge["confidence"] == 0.6
            assert sorted(edge["extractors"]) == ["gliner", "llm"]
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.close()

    @staticmethod
    async def test_folding_a_pending_edge_keeps_the_best_provenance() -> None:
        """A job's new edge folds into the committed one without losing either side."""
        store = build_test_store()
        await store.connect()
        label = validate_identifier(f"Thing_{uuid4().hex[:8]}")
        rel_type = validate_identifier(f"LINKS_{uuid4().hex[:8]}")
        committed_id, pending_id, job_id = str(uuid4()), str(uuid4()), str(uuid4())

        try:
            await store.execute_write(
                f"CREATE (a:_Node:{label} {{id: $a}}), (b:_Node:{label} {{id: $b}}), "
                f"(a)-[:{rel_type} {{id: $committed, confidence: 0.4, "
                "extractors: ['gliner']}]->(b), "
                f"(a)-[:{rel_type} {{id: $pending, _pending_job_id: $job, "
                "_canonical_id: $committed, confidence: 0.7, "
                "extractors: ['llm']}]->(b)",
                {
                    "a": str(uuid4()),
                    "b": str(uuid4()),
                    "committed": committed_id,
                    "pending": pending_id,
                    "job": job_id,
                },
            )

            await store.execute_write(
                fold_pending_relations_query(rel_type), {"job_id": job_id}
            )

            rows = await store.execute_read(
                f"MATCH ()-[r:{rel_type}]->() "
                "RETURN r.id AS id, r.confidence AS confidence, "
                "r.extractors AS extractors"
            )
            assert [row["id"] for row in rows] == [committed_id]
            assert rows[0]["confidence"] == 0.7
            assert sorted(rows[0]["extractors"]) == ["gliner", "llm"]
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.close()
