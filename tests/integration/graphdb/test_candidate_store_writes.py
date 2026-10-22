"""Candidate writes share one schema setup and refuse reserved edge types.

Runs against the Neo4j instance from ``docker/docker-compose.ci.yml``. The
store under test never runs ``setup_constraints``, so the first candidate
write creates the candidate schema itself.
"""

import asyncio
import importlib.util
from collections.abc import AsyncIterator, Mapping
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio

from agrag.candidates import reject_candidates
from agrag.common.data_models.candidate import CANDIDATE_LABEL, CandidateRecord
from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.graph_record import RelationRecord
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.graphdb.base import GraphStore
from agrag.graphdb.errors import GraphStoreConstraintViolationError
from tests.integration._backend import build_test_store


neo4j_missing = importlib.util.find_spec("neo4j") is None

pytestmark = [
    pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed"),
    pytest.mark.xdist_group(name="candidate_state"),
]


@pytest_asyncio.fixture
async def fresh_store() -> AsyncIterator[GraphStore]:
    """Open a store that has not yet created the candidate schema."""
    graph_store = build_test_store()
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
    candidate_id = str(uuid4())
    await fresh_store.execute_write(
        f"CREATE (:{CANDIDATE_LABEL} {{id: $id}})", {"id": candidate_id}
    )

    assert (first.written, second.written) == (0, 0)
    assert first.failures == []
    assert second.failures == []
    assert await fresh_store.blocked_candidate_keys([]) == set()
    with pytest.raises(GraphStoreConstraintViolationError):
        await fresh_store.execute_write(
            f"CREATE (:{CANDIDATE_LABEL} {{id: $id}})", {"id": candidate_id}
        )


async def test_write_after_review_transition_is_suppressed_successfully(
    fresh_store: GraphStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A review between preflight and upsert blocks a twin without a failure."""
    chunk_id = uuid4()
    text = f"Candidate {uuid4()}"
    first = CandidateRecord(
        kind="entity",
        label="Person",
        text=text,
        confidence=0.8,
        reason="off_pattern",
        chunk_id=chunk_id,
    )
    second = first.model_copy(update={"id": uuid4()})
    await fresh_store.execute_write(
        f"CREATE (chunk:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} {{id: $id}})",
        {"id": str(chunk_id)},
    )
    assert (await fresh_store.upsert_candidates([first])).written == 1

    preflight_complete = asyncio.Event()
    continue_write = asyncio.Event()
    execute_read = fresh_store.execute_read

    async def pause_after_preflight(
        query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        rows = await execute_read(query, parameters)
        if parameters and parameters.get("keys") == [first.key]:
            preflight_complete.set()
            await continue_write.wait()
        return rows

    monkeypatch.setattr(fresh_store, "execute_read", pause_after_preflight)
    write_task = asyncio.create_task(fresh_store.upsert_candidates([second]))
    try:
        await preflight_complete.wait()
        review = await reject_candidates(fresh_store, keys=[first.key])
        assert review.changed == [first.key]
    finally:
        continue_write.set()

    result = await write_task
    candidates = await fresh_store.execute_read(
        f"MATCH (candidate:{CANDIDATE_LABEL} {{key: $key}}) "
        "RETURN candidate.id AS id, candidate.state AS state ORDER BY id",
        {"key": first.key},
    )

    assert result.written == 1
    assert result.failures == []
    assert candidates == [{"id": str(first.id), "state": "rejected"}]
    await fresh_store.execute_write(
        f"MATCH (candidate:{CANDIDATE_LABEL} {{id: $id}}) DETACH DELETE candidate",
        {"id": str(first.id)},
    )
    await fresh_store.execute_write(
        f"MATCH (chunk:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} {{id: $id}}) "
        "DETACH DELETE chunk",
        {"id": str(chunk_id)},
    )


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
