"""Integration tests for merge mechanics against a real Neo4j instance.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``). The ``skipif``
only guards the missing extra; with the extra installed the tests expect a
reachable Neo4j at the default ``NEO4J_URI``.
"""

import importlib.util
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.cypher.entities import validate_identifier
from agrag.cypher.schema import merge_key_constraint_query
from agrag.graphdb import build_graph_store
from agrag.graphdb.errors import GraphStoreAliasConflictError
from agrag.ingestion.graph import _apply_merge_with_conflict_retry
from agrag.ingestion.merge import (
    PropertyRules,
    PropertyStrategy,
    apply_merge,
    compute_merge,
)


neo4j_missing = importlib.util.find_spec("neo4j") is None


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestApplyMergeConstraintIntegration:
    """Regression coverage for the per-label merge_key uniqueness constraint."""

    async def test_survivor_adopting_absorbed_name_commits(self) -> None:
        """A survivor whose resolved name matches a tombstone's name commits.

        Canonical selection picks entity B as survivor while KEEP_FIRST
        resolves the name from entity A, so the survivor's resolved
        merge_key equals A's still-live merge_key at the moment the merge
        runs. Without clearing A's merge_key before the survivor is written,
        Neo4j rejects the whole transaction with a constraint violation
        instead of committing the merge.
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
            # entity_a is listed first (so KEEP_FIRST resolves the survivor's
            # name from it) but is created later, so _select_canonical picks
            # entity_b as the survivor on the created_at tiebreak.
            entity_a = Entity(
                id=uuid4(),
                label=label,
                name="Ada Lovelace",
                created_at=datetime.now(UTC),
            )
            entity_b = Entity(
                id=uuid4(),
                label=label,
                name="A. Lovelace",
                created_at=datetime.now(UTC) - timedelta(minutes=5),
            )
            await store.upsert_nodes(
                label, [entity_a.to_node_record(), entity_b.to_node_record()]
            )
            # A direct, label-scoped constraint instead of setup_constraints():
            # that sweeps every label the whole database has ever seen, so on a
            # long-lived shared instance it can fail on unrelated leftover state.
            await store.execute_write(merge_key_constraint_query(label))

            plan, _ = await compute_merge(
                existing_entities=[entity_a, entity_b],
                mentions=[],
                schema=schema,
                rules=PropertyRules(default=PropertyStrategy.KEEP_FIRST),
            )
            assert plan.survivor.id == entity_b.id
            assert plan.survivor.name == entity_a.name
            assert plan.tombstone_ids == [entity_a.id]

            await apply_merge(plan, graph_store=store, schema=schema)

            survivor_rows = await store.execute_read(
                f"MATCH (n:{label} {{id: $id}}) RETURN n.merge_key AS merge_key",
                {"id": str(entity_b.id)},
            )
            assert survivor_rows[0]["merge_key"] == entity_a.merge_key

            tombstone_rows = await store.execute_read(
                f"MATCH (n:{label} {{id: $id}}) "
                f"RETURN n.merge_key AS merge_key, n.merged_into AS merged_into",
                {"id": str(entity_a.id)},
            )
            assert tombstone_rows[0]["merge_key"] is None
            assert tombstone_rows[0]["merged_into"] == str(entity_b.id)
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.close()


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestApplyMergeAliasConflictIntegration:
    """Regression coverage for a merge-key alias claimed by another entity."""

    async def test_bob_racing_robert_recovers_into_one_entity(self) -> None:
        """Canonical "Bob" races an entity resolving "Bob" as an alias of "Robert".

        Simulates the race deterministically, in sequence: one writer
        commits a canonical entity named "Bob" first; a second writer then
        separately resolves mentions "Robert" and "Bob" as the same entity
        and tries to accept "Bob" as an alias. Neither writer's own node
        merge_key collides (their own names differ), so nothing at the
        database level rejects the second write; without recovery it would
        leave two live entities that both believe they own the name "Bob".
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

            recovered_plan, _ = await _apply_merge_with_conflict_retry(
                plan_b,
                graph_store=store,
                schema=schema,
                existing_entities=[],
                mentions=[robert_mention, bob_mention],
                is_new_entity=True,
            )

            assert recovered_plan.survivor.id == plan_a.survivor.id
            count_rows = await store.execute_read(
                f"MATCH (n:{label}) RETURN count(n) AS c", {}
            )
            assert count_rows[0]["c"] == 1

            robert_lookup = await store.execute_read(
                f"MATCH (a:_AgragMergeAlias {{merge_key: $mk}}) "
                f"MATCH (n:{label} {{id: a.entity_id}}) RETURN n.id AS id",
                {"mk": f"{label}:robert"},
            )
            assert robert_lookup[0]["id"] == str(plan_a.survivor.id)
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.execute_write(
                "MATCH (a:_AgragMergeAlias) "
                "WHERE a.merge_key STARTS WITH $prefix DELETE a",
                {"prefix": f"{label}:"},
            )
            await store.close()
