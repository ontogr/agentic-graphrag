"""Shared fixtures for task memory integration tests.

Every test gets its own project ids, so tests share one database without seeing
each other's tasks. Teardown deletes only the Task, Event, Step and Request
nodes of those projects. Uniqueness constraints are left in place because other
tests use the same labels.
"""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest

from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore


async def _delete_project_memory(store: GraphStore, project_id: str) -> None:
    """Delete the task memory nodes that belong to one project.

    Args:
        store: A connected graph store.
        project_id: The project whose nodes are removed.
    """
    params = {"project_id": project_id}
    await store.execute_write(
        "MATCH (t:MemoryTask {project_id: $project_id}) "
        "OPTIONAL MATCH (t)-[:HAS_EVENT|HAS_STEP]->(child) "
        "DETACH DELETE child, t",
        params,
    )
    await store.execute_write(
        "MATCH (r:MemoryRequest {project_id: $project_id}) DETACH DELETE r", params
    )
    await store.execute_write(
        "MATCH (p:MemoryProject {project_id: $project_id}) DETACH DELETE p", params
    )


@pytest.fixture
async def store() -> AsyncGenerator[GraphStore, None]:
    """Open the configured Neo4j store for one test."""
    graph_store = build_graph_store("neo4j")
    async with graph_store:
        yield graph_store


@pytest.fixture
async def project(store: GraphStore) -> AsyncGenerator[str, None]:
    """Yield a project id no other test uses, and delete its nodes afterwards."""
    project_id = f"proj-{uuid4().hex[:8]}"
    try:
        yield project_id
    finally:
        await _delete_project_memory(store, project_id)


@pytest.fixture
async def other_project(store: GraphStore) -> AsyncGenerator[str, None]:
    """Yield a second project id for scope tests, and delete its nodes afterwards."""
    project_id = f"proj-{uuid4().hex[:8]}"
    try:
        yield project_id
    finally:
        await _delete_project_memory(store, project_id)
