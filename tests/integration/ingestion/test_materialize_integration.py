"""Integration tests for non-destructive entity-match materialization."""

import importlib.util
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_record import RelationRecord
from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType
from agrag.cypher.entities import validate_identifier
from agrag.graphdb import build_graph_store
from agrag.ingestion.materialize import MatchDecision, write_matches_and_materialize


neo4j_missing = importlib.util.find_spec("neo4j") is None


def _schema(label: str) -> GraphSchema:
    """Build the schema used by one isolated Neo4j test graph."""
    return GraphSchema(
        name="test",
        version="1",
        entities=[EntityType(label=label, description="test")],
        relations=[
            RelationType(
                label="KNOWS",
                description="test relation",
                patterns=[(label, label)],
            )
        ],
    )


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestMatchMaterializationIntegration:
    """Materialization preserves raw graph records in a real transaction."""

    async def test_preserves_raw_nodes_and_domain_relationships(self) -> None:
        """A fuzzy match creates derived state without replacing raw graph state."""
        store = build_graph_store("neo4j")
        await store.connect()
        label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        first = Entity(id=uuid4(), label=label, name="Ada", properties={"rank": 1})
        second = Entity(
            id=uuid4(), label=label, name="Ada Lovelace", properties={"rank": 2}
        )
        schema = _schema(label)
        try:
            await store.upsert_nodes(
                label, [first.to_node_record(), second.to_node_record()]
            )
            await store.upsert_relations(
                [
                    RelationRecord(
                        id=uuid4(),
                        type="KNOWS",
                        start_id=first.id,
                        end_id=second.id,
                        properties={"source": "test"},
                    )
                ]
            )

            materialization = await write_matches_and_materialize(
                [
                    MatchDecision(
                        entity_a_id=first.id,
                        entity_b_id=second.id,
                        comparator="FuzzyMatch",
                        score=0.98,
                        decided_at=datetime.now(UTC),
                    )
                ],
                graph_store=store,
                schema=schema,
                members=[first, second],
            )

            rows = await store.execute_read(
                "MATCH (a)-[match:MATCHES]->(b) "
                "WHERE a.id IN $ids AND b.id IN $ids "
                "MATCH (a)-[:RESOLVED_AS]->(resolved:ResolvedEntity) "
                "MATCH (b)-[:RESOLVED_AS]->(resolved) "
                "OPTIONAL MATCH (a)-[domain:KNOWS]->(b) "
                "RETURN a.id AS first_id, b.id AS second_id, "
                "resolved.id AS resolved_id, "
                "count(domain) AS domain_count",
                {"ids": [str(first.id), str(second.id)]},
            )

            assert len(rows) == 1
            assert {rows[0]["first_id"], rows[0]["second_id"]} == {
                str(first.id),
                str(second.id),
            }
            assert rows[0]["resolved_id"] == str(materialization.resolved_entity.id)
            assert rows[0]["domain_count"] == 1
            raw_rows = await store.execute_read(
                f"MATCH (entity:{label}) WHERE entity.id IN $ids "
                "RETURN entity.id AS id, entity.rank AS rank",
                {"ids": [str(first.id), str(second.id)]},
            )
            assert {(row["id"], row["rank"]) for row in raw_rows} == {
                (str(first.id), 1),
                (str(second.id), 2),
            }
        finally:
            await store.execute_write(
                f"MATCH (node:{label}) DETACH DELETE node",
            )
            await store.execute_write(
                "MATCH (node:ResolvedEntity) "
                "WHERE any(member_id IN node.member_ids "
                "WHERE member_id IN $ids) DETACH DELETE node",
                {"ids": [str(first.id), str(second.id)]},
            )
            await store.close()

    async def test_reverse_match_writes_are_idempotent(self) -> None:
        """Repeating a match in reverse leaves one canonical edge and cluster."""
        store = build_graph_store("neo4j")
        await store.connect()
        label = validate_identifier(f"Person_{uuid4().hex[:8]}")
        first, second = sorted(
            (
                Entity(id=uuid4(), label=label, name="Ada"),
                Entity(id=uuid4(), label=label, name="Ada Lovelace"),
            ),
            key=lambda entity: str(entity.id),
        )
        schema = _schema(label)
        try:
            await store.upsert_nodes(
                label, [first.to_node_record(), second.to_node_record()]
            )
            for entity_a_id, entity_b_id in (
                (first.id, second.id),
                (second.id, first.id),
            ):
                await write_matches_and_materialize(
                    [
                        MatchDecision(
                            entity_a_id=entity_a_id,
                            entity_b_id=entity_b_id,
                            comparator="FuzzyMatch",
                            decided_at=datetime.now(UTC),
                        )
                    ],
                    graph_store=store,
                    schema=schema,
                    members=[first, second],
                )

            rows = await store.execute_read(
                "MATCH (a)-[match:MATCHES]->(b) "
                "WHERE a.id IN $ids AND b.id IN $ids "
                "RETURN a.id AS first_id, b.id AS second_id, count(match) AS count",
                {"ids": [str(first.id), str(second.id)]},
            )
            assert rows == [
                {
                    "first_id": str(first.id),
                    "second_id": str(second.id),
                    "count": 1,
                }
            ]
        finally:
            await store.execute_write(f"MATCH (node:{label}) DETACH DELETE node")
            await store.execute_write(
                "MATCH (node:ResolvedEntity) "
                "WHERE any(member_id IN node.member_ids "
                "WHERE member_id IN $ids) DETACH DELETE node",
                {"ids": [str(first.id), str(second.id)]},
            )
            await store.close()
