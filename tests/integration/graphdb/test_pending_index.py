"""Commit and rollback scans use the pending-tag indexes, against real Neo4j.

Run against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``).
"""

import importlib.util
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio

from agrag.cypher.cutover_job_write import (
    clear_pending_node_tags_query,
    clear_pending_relation_tags_query,
)
from agrag.cypher.entities import PENDING_TAGGED_NODE_LABELS
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from tests.integration._schema_cleanup import drop_schema_for


neo4j_missing = importlib.util.find_spec("neo4j") is None

pytestmark = [
    pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed"),
    pytest.mark.asyncio(loop_scope="module"),
]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def store() -> AsyncIterator[GraphStore]:
    """Open one connected store for the module."""
    graph_store = build_graph_store("neo4j")
    await graph_store.connect()
    try:
        yield graph_store
    finally:
        await graph_store.close()


async def _explain_operator_types(store: GraphStore, query: str) -> set[str]:
    """Return every operator type in the plan Neo4j chooses for ``query``."""
    async with store.session() as session:
        result = await session.run("EXPLAIN " + query, {"job_id": str(uuid4())})
        summary = await result.consume()
    return _collect_operator_types(summary.plan)


def _collect_operator_types(plan: dict[str, Any]) -> set[str]:
    """Collect the operator type of a plan node and all of its children."""
    types = {plan["operatorType"]}
    for child in plan.get("children", []):
        types |= _collect_operator_types(child)
    return types


class TestPendingTagIndexes:
    """Commit and rollback statements seek the pending-tag indexes."""

    async def test_node_commit_scan_seeks_index_for_every_tagged_label(
        self, store: GraphStore
    ) -> None:
        """Each label a job can tag is cleared through an index seek."""
        await store.setup_constraints()
        await store.execute_write("CALL db.awaitIndexes(60)")

        for label in PENDING_TAGGED_NODE_LABELS:
            operators = await _explain_operator_types(
                store, clear_pending_node_tags_query(label)
            )

            assert any("NodeIndexSeek" in operator for operator in operators), label

    async def test_relation_commit_scan_seeks_index_for_probe_type(
        self, store: GraphStore
    ) -> None:
        """A relationship type's tagged edges are cleared through an index seek."""
        rel_type = f"PendingProbe{uuid4().hex[:8].upper()}"
        try:
            await store.ensure_relation_constraint(rel_type)
            await store.execute_write("CALL db.awaitIndexes(60)")

            operators = await _explain_operator_types(
                store, clear_pending_relation_tags_query(rel_type)
            )

            assert any("RelationshipIndexSeek" in op for op in operators)
        finally:
            await drop_schema_for(store, rel_type)
