"""Fixtures for executing the Python blocks in the docs pages.

A block opts in with ``fixture:llm_env`` or ``fixture:agent_llm_env``.
"""

import asyncio
import contextlib
import os
from typing import Literal

import httpx
import pytest
import sentence_transformers  # noqa: F401
import torch  # noqa: F401

# Each doc block runs in a forked child. Importing the heavy libraries here lets every
# child inherit them, instead of loading them again.
import agrag.embedding  # noqa: F401
import agrag.ingestion  # noqa: F401
from agrag.agents.settings import AgentLLMSettings
from agrag.graphdb import build_graph_store
from agrag.ingestion.extract import ExtractionLLMSettings
from tests.integration._live_llm import probe_live_llm


RESET_GUARD = "DOCS_TEST_ALLOW_NEO4J_RESET"
_LLMFixture = Literal["llm_env", "agent_llm_env"]


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


def _live_llm_config(
    fixture_name: _LLMFixture,
) -> tuple[str, str | None, str] | None:
    """Return the endpoint, optional key, and model used by a docs block."""
    if fixture_name == "llm_env":
        try:
            settings = ExtractionLLMSettings.from_openai_compatible_env()
        except RuntimeError:
            return None
    else:
        settings = AgentLLMSettings.from_openai_compatible_env()

    client = settings.clients[0]
    if not client.base_url:
        return None
    api_key = client.api_key.get_secret_value() if client.api_key else None
    return client.base_url, api_key, client.model


def _require_live_llm(
    fixture_name: _LLMFixture, transport: httpx.BaseTransport | None
) -> None:
    """Skip a docs block when its configured provider is unavailable."""
    config = _live_llm_config(fixture_name)
    if config is None:
        reason = (
            "LLM_BASE_URL or LLM_MODEL_ID is not set"
            if fixture_name == "llm_env"
            else "AGENT_LLM_BASE_URL or LLM_BASE_URL is not set"
        )
        pytest.skip(reason)
    probe_live_llm(*config, transport=transport)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Prime provider checks before forked docs blocks start."""
    if config.getoption("collectonly"):
        return

    fixture_names = {
        fixture_name
        for item in items
        for fixture_name in getattr(item, "fixturenames", ())
        if fixture_name in {"llm_env", "agent_llm_env"}
    }
    for fixture_name in fixture_names:
        llm_config = _live_llm_config(fixture_name)
        if llm_config is None:
            continue
        with contextlib.suppress(pytest.skip.Exception, httpx.HTTPStatusError):
            probe_live_llm(*llm_config)


@pytest.fixture
def llm_env(request: pytest.FixtureRequest) -> None:
    """Check the configured extraction LLM before a docs block runs."""
    _require_live_llm("llm_env", getattr(request, "param", None))


@pytest.fixture
def agent_llm_env(request: pytest.FixtureRequest) -> None:
    """Check the configured agent LLM before a docs block runs."""
    _require_live_llm("agent_llm_env", getattr(request, "param", None))


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
