"""Integration tests for ancestor labels on merge survivors against Neo4j.

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
from agrag.cypher.entities import fetch_all_by_label_query
from agrag.ingestion.merge import apply_merge, compute_merge
from tests.integration._backend import build_test_store


neo4j_missing = importlib.util.find_spec("neo4j") is None


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestApplyMergeAncestorLabelsIntegration:
    """A child-type survivor is stored under its parent label too."""

    async def test_vendor_survivor_carries_organization_label(self) -> None:
        """A Vendor survivor matches its Organization label in Cypher.

        The node is found by the parent label, but the committed-entity
        fetch for Organization skips it, because its merge_key is prefixed
        with its leaf label Vendor. Resolution therefore never merges
        Vendors into Organizations.
        """
        store = build_test_store()
        await store.connect()
        schema = GraphSchema(
            name="test",
            version="1",
            entities=[
                EntityType(label="Organization", description="test"),
                EntityType(
                    label="Vendor", description="test", parents=["Organization"]
                ),
            ],
            relations=[],
        )
        mention = ExtractedEntity(
            chunk_id=uuid4(), label="Vendor", text="Acme", char_start=0, char_end=4
        )
        plan, _ = await compute_merge(
            existing_entities=[], mentions=[mention], schema=schema
        )
        survivor_id = str(plan.survivor.id)
        try:
            await apply_merge(plan, graph_store=store, schema=schema)

            by_parent_label = await store.execute_read(
                "MATCH (n:Organization {id: $id}) RETURN n.id AS id",
                {"id": survivor_id},
            )
            assert [row["id"] for row in by_parent_label] == [survivor_id]

            organization_rows = await store.execute_read(
                fetch_all_by_label_query("Organization"),
                {"skip": 0, "limit": 100},
            )
            returned_ids = {row["n"]["id"] for row in organization_rows}
            assert survivor_id not in returned_ids
        finally:
            await store.execute_write(
                "MATCH (n {id: $id}) DETACH DELETE n", {"id": survivor_id}
            )
            await store.execute_write(
                "MATCH (a:_MergeAlias) WHERE a.entity_id = $id DELETE a",
                {"id": survivor_id},
            )
            await store.close()
