"""Integration tests for merge mechanics against a real Neo4j instance.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). The ``skipif``
only guards the missing extra; with the extra installed the tests expect a
reachable Neo4j at the default ``NEO4J_URI``.
"""

import importlib.util
from uuid import uuid4

import pytest

from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.cypher.entities import validate_identifier
from agrag.cypher.schema import merge_key_constraint_query
from agrag.graphdb import build_graph_store
from agrag.graphdb.errors import GraphStoreAliasConflictError
from agrag.ingestion.merge import apply_merge, compute_merge


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
        store = build_graph_store("neo4j")
        await store.connect()
        label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label=label, description="test")],
            relations=[],
        )
        try:
            await store.execute_write(merge_key_constraint_query(label))

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
                f"MATCH (a:_AgragMergeAlias {{merge_key: $mk}}) "
                f"MATCH (n:{label} {{id: a.entity_id}}) RETURN n.id AS id",
                {"mk": f"{label}:robert"},
            )
            assert robert_lookup == []
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.execute_write(
                "MATCH (a:_AgragMergeAlias) "
                "WHERE a.merge_key STARTS WITH $prefix DELETE a",
                {"prefix": f"{label}:"},
            )
            await store.close()
