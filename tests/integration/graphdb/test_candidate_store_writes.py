"""Candidate writes share one schema setup and refuse reserved edge types.

Runs against the Neo4j instance from ``docker/docker-compose.ci.yml``. The
store under test never runs ``setup_constraints``, so the first candidate
write creates the candidate schema itself.
"""

import asyncio
import importlib.util
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio

from agrag.common.data_models.candidate import CANDIDATE_LABEL
from agrag.common.data_models.graph_record import RelationRecord
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore


neo4j_missing = importlib.util.find_spec("neo4j") is None

pytestmark = pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")


@pytest_asyncio.fixture
async def fresh_store() -> AsyncIterator[GraphStore]:
    """Open a store that has not yet created the candidate schema."""
    graph_store = build_graph_store("neo4j")
    await graph_store.connect()
    try:
        yield graph_store
    finally:
        await graph_store.close()


async def test_concurrent_first_candidate_writes_both_succeed(
    fresh_store: GraphStore,
) -> None:
    """Two first writes at once both succeed and leave the id constraint in place."""
    first, second = await asyncio.gather(
        fresh_store.upsert_candidates([]),
        fresh_store.upsert_candidates([]),
    )
    constraints = await fresh_store.execute_read(
        "SHOW CONSTRAINTS YIELD name, labelsOrTypes "
        "WHERE labelsOrTypes = [$label] RETURN name",
        {"label": CANDIDATE_LABEL},
    )

    assert (first.written, second.written) == (0, 0)
    assert first.failures == []
    assert second.failures == []
    assert await fresh_store.blocked_candidate_keys([]) == set()
    assert constraints == [{"name": "candidate_id_unique"}]


async def test_relation_with_a_candidate_edge_type_is_refused(
    fresh_store: GraphStore,
) -> None:
    """A relation that reuses a candidate edge type fails without a write."""
    relation = RelationRecord(
        id=uuid4(),
        type="SOURCE",
        start_id=uuid4(),
        end_id=uuid4(),
        properties={},
    )

    result = await fresh_store.upsert_relations([relation])

    assert result.written == 0
    assert [
        (failure.id, failure.error_type, failure.error_message)
        for failure in result.failures
    ] == [
        (
            str(relation.id),
            "ValueError",
            "'SOURCE' is reserved for the candidate store",
        )
    ]
