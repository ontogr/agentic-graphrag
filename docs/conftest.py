"""Fixtures for executing the Python blocks in the docs pages.

A block opts in with a fence such as ``python fixture:llm_env``.
"""

import asyncio
import os

import pytest
import sentence_transformers  # noqa: F401
import torch  # noqa: F401

# Each doc block runs in a forked child. Importing the heavy libraries here lets every
# child inherit them, instead of loading them again.
import agrag.embedding  # noqa: F401
import agrag.ingestion  # noqa: F401
from agrag.graphdb import build_graph_store


RESET_GUARD = "DOCS_TEST_ALLOW_NEO4J_RESET"


def _escape(name: str) -> str:
    """Quote a schema object name for use in a Cypher statement."""
    return name.replace("`", "``")


async def _reset_neo4j() -> None:
    """Remove all graph data and user-defined schema objects from Neo4j.

    The built-in token lookup indexes stay, because every Neo4j database has them.
    """
    graph_store = build_graph_store("neo4j")
    await graph_store.connect()
    try:
        await graph_store.execute_write("MATCH (n) DETACH DELETE n")
        constraints = await graph_store.execute_read(
            "SHOW CONSTRAINTS YIELD name RETURN name"
        )
        for row in constraints:
            await graph_store.execute_write(
                f"DROP CONSTRAINT `{_escape(row['name'])}` IF EXISTS"
            )
        indexes = await graph_store.execute_read(
            "SHOW INDEXES YIELD name, type, owningConstraint "
            "WHERE owningConstraint IS NULL AND type <> 'LOOKUP' RETURN name"
        )
        for row in indexes:
            await graph_store.execute_write(
                f"DROP INDEX `{_escape(row['name'])}` IF EXISTS"
            )
    finally:
        await graph_store.close()


@pytest.fixture
def llm_env():
    """Skip a doc block unless an LLM endpoint is configured."""
    if not (os.environ.get("LLM_API_KEY") and os.environ.get("LLM_BASE_URL")):
        pytest.skip("LLM_BASE_URL and LLM_API_KEY are not set")


@pytest.fixture
def clean_neo4j() -> None:
    """Give a doc block an empty Neo4j database with no custom schema.

    The fixture refuses to run unless DOCS_TEST_ALLOW_NEO4J_RESET=1, so a docs
    test run never wipes a database by accident. The reset runs before the block
    only. A guide can then read, in a later block, what an earlier block wrote.
    """
    if os.environ.get(RESET_GUARD) != "1":
        pytest.fail(
            f"This block deletes every node in the database at NEO4J_URI. "
            f"Set {RESET_GUARD}=1 to confirm that it is a throwaway database."
        )
    asyncio.run(_reset_neo4j())
