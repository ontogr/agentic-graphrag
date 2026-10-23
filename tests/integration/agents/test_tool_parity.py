"""Integration tests that the three tool surfaces expose one contract.

The public Python functions in ``agrag.evidence``, the agent tools built by
``make_core_tools`` and the MCP tools registered by ``build_server`` must take
the same model-facing arguments with the same defaults and bounds, describe
themselves with the same strings, and return the same results for the same
query. Surface-only parameters (``ctx``, ``callbacks``) and injected
parameters are not part of the contract.
"""

import inspect
from typing import Any

from mcp import Client

from agrag.agents.tools.core import make_core_tools
from agrag.common.data_models.evidence import (
    CitationResult,
    EvidenceSearchMode,
    EvidenceSearchResult,
    FetchResult,
)
from agrag.decisions import DecisionTraces
from agrag.evidence import (
    check_citations,
    contract,
    entity_search,
    explore_relationships,
    fetch_evidence,
    navigate_document_tree,
    search_evidence,
    search_themes,
)
from agrag.history import ConversationHistory
from agrag.mcp_server.server import build_server
from agrag.mcp_server.settings import McpServerSettings
from agrag.retrieval import RetrievalSettings
from tests.integration.retrieval.evidence._corpus import BagOfWordsEmbedder
from tests.integration.retrieval.evidence.conftest import EvidenceEnv


_QUERY = "do you keep and upload my activity to your database"

# tool name -> (model-facing arguments with defaults, injected argument names)
_PYTHON_CONTRACT: dict[str, tuple[dict[str, Any], set[str]]] = {
    "search_evidence": (
        {
            "query": inspect.Parameter.empty,
            "mode": EvidenceSearchMode.HYBRID,
            "limit": 10,
        },
        {
            "store",
            "embedder",
            "scope",
            "vector_store",
            "reranker",
            "settings",
            "timeout",
        },
    ),
    "entity_search": (
        {
            "query": inspect.Parameter.empty,
            "labels": None,
            "mode": EvidenceSearchMode.HYBRID,
            "limit": 10,
            "support_limit": 3,
        },
        {"store", "embedder", "scope", "vector_store", "settings", "timeout"},
    ),
    "explore_relationships": (
        {
            "entity_id": inspect.Parameter.empty,
            "depth": 1,
            "relation_types": None,
            "max_nodes": 25,
            "max_edges": 50,
        },
        {"store", "scope", "timeout"},
    ),
    "navigate_document_tree": (
        {
            "evidence_id": inspect.Parameter.empty,
            "relation": inspect.Parameter.empty,
            "limit": 10,
            "max_chars": 12000,
        },
        {"store", "scope", "timeout"},
    ),
    "search_themes": (
        {"query": inspect.Parameter.empty, "limit": 5, "support_limit": 3},
        {"store", "embedder", "scope", "vector_store", "settings", "timeout"},
    ),
    "fetch_evidence": (
        {"evidence_ids": inspect.Parameter.empty, "max_chars": None},
        {"store", "scope", "timeout"},
    ),
    "check_citations": (
        {"evidence_ids": inspect.Parameter.empty},
        {"store", "fetched_ids", "scope"},
    ),
}

_PYTHON_FUNCTIONS = {
    "search_evidence": search_evidence,
    "entity_search": entity_search,
    "explore_relationships": explore_relationships,
    "navigate_document_tree": navigate_document_tree,
    "search_themes": search_themes,
    "fetch_evidence": fetch_evidence,
    "check_citations": check_citations,
}

_SURFACE_ONLY_ARGUMENTS = {"ctx", "callbacks"}


def _strip_titles(node: Any) -> Any:
    """Return a schema copy without the cosmetic title keys."""
    if isinstance(node, dict):
        return {
            key: _strip_titles(value) for key, value in node.items() if key != "title"
        }
    if isinstance(node, list):
        return [_strip_titles(item) for item in node]
    return node


def _mcp_settings(env: EvidenceEnv) -> McpServerSettings:
    """Return server settings whose scope holds two of the authored documents."""
    return McpServerSettings(
        scope_document_keys=f"{env.keep},{env.harbor}",
        _env_file=None,
    )


def _agent_tools(env: EvidenceEnv) -> dict[str, Any]:
    """Build the agent tools over the corpus scope and index them by name."""
    history = ConversationHistory(
        env.store, project_id="parity", agent_id="parity-test"
    )
    decisions = DecisionTraces(env.store, project_id="parity", agent_id="parity-test")
    tools, _ = make_core_tools(
        graph_store=env.store,
        embedder=BagOfWordsEmbedder(),
        scope=frozenset({env.keep, env.harbor}),
        task_name="parity-task",
        history=history,
        decisions=decisions,
        fetched_ids=[],
        fetched_outcomes=[],
        max_chars=12_000,
        max_tool_calls=30,
        retrieval_settings=RetrievalSettings(),
    )
    return {tool.name: tool for tool in tools}


def _agent_schema(tool: Any) -> dict[str, Any]:
    """Return the normalized JSON schema of an agent tool's arguments."""
    return _strip_titles(tool.args_schema.model_json_schema())


class TestParity:
    """The Python functions, agent tools and MCP tools expose one contract."""

    async def test_python_functions_take_the_model_facing_arguments(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Each Python function's signature matches the section 2 contract."""
        for name, (arguments, injected) in _PYTHON_CONTRACT.items():
            function = _PYTHON_FUNCTIONS[name]
            parameters = inspect.signature(function).parameters
            actual_injected = {
                parameter
                for parameter, spec in parameters.items()
                if parameter not in arguments
            }
            assert actual_injected == injected, name
            for argument, default in arguments.items():
                assert parameters[argument].default == default, (name, argument)
                if default is not inspect.Parameter.empty:
                    assert (
                        parameters[argument].kind is inspect.Parameter.KEYWORD_ONLY
                    ), (name, argument)

    async def test_agent_and_mcp_argument_schemas_are_identical(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Each tool's argument schema is the same on the agent and the server."""
        agent_tools = _agent_tools(evidence_env)
        server = build_server(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _mcp_settings(evidence_env),
        )
        async with Client(server) as client:
            listing = await client.list_tools()
        mcp_schemas = {
            tool.name: _strip_titles(tool.input_schema) for tool in listing.tools
        }

        for name in _PYTHON_CONTRACT:
            agent_properties = {
                argument: spec
                for argument, spec in _agent_schema(agent_tools[name])[
                    "properties"
                ].items()
                if argument not in _SURFACE_ONLY_ARGUMENTS
            }
            mcp_properties = mcp_schemas[name]["properties"]
            assert set(agent_properties) == set(mcp_properties), name
            for argument in mcp_properties:
                assert agent_properties[argument] == mcp_properties[argument], (
                    name,
                    argument,
                )

    async def test_descriptions_come_from_the_contract(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Both surfaces describe each tool with the contract string."""
        descriptions = {
            "search_evidence": contract.SEARCH_EVIDENCE,
            "entity_search": contract.ENTITY_SEARCH,
            "explore_relationships": contract.EXPLORE_RELATIONSHIPS,
            "navigate_document_tree": contract.NAVIGATE_DOCUMENT_TREE,
            "search_themes": contract.SEARCH_THEMES,
            "fetch_evidence": contract.FETCH_EVIDENCE,
            "check_citations": contract.CHECK_CITATIONS,
        }
        agent_tools = _agent_tools(evidence_env)
        server = build_server(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _mcp_settings(evidence_env),
        )
        async with Client(server) as client:
            listing = await client.list_tools()
        mcp_descriptions = {tool.name: tool.description for tool in listing.tools}

        for name, description in descriptions.items():
            assert agent_tools[name].description == description, name
            assert mcp_descriptions[name] == description, name

    async def test_search_returns_the_same_hits_on_all_three_surfaces(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Python, the agent tool and the MCP tool rank the same hits first."""
        scope = frozenset({evidence_env.keep, evidence_env.harbor})
        python_result = await search_evidence(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _QUERY,
            limit=3,
            scope=scope,
        )
        agent_tools = _agent_tools(evidence_env)
        agent_result = EvidenceSearchResult.model_validate_json(
            await agent_tools["search_evidence"].ainvoke({"query": _QUERY, "limit": 3})
        )
        server = build_server(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _mcp_settings(evidence_env),
        )
        async with Client(server) as client:
            call = await client.call_tool(
                "search_evidence", {"query": _QUERY, "limit": 3}
            )
            assert not call.is_error
            mcp_result = EvidenceSearchResult.model_validate(call.structured_content)

        assert python_result.status == agent_result.status == mcp_result.status
        python_ids = [hit.evidence_id for hit in python_result.hits]
        assert python_ids == [hit.evidence_id for hit in agent_result.hits]
        assert python_ids == [hit.evidence_id for hit in mcp_result.hits]

    async def test_fetch_and_citations_track_the_same_outcomes(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Fetch returns a FetchResult and citation checks agree on all surfaces."""
        scope = frozenset({evidence_env.keep, evidence_env.harbor})
        search = await search_evidence(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _QUERY,
            limit=2,
            scope=scope,
        )
        ids = [hit.evidence_id for hit in search.hits]
        assert ids

        python_fetch = await fetch_evidence(evidence_env.store, ids, scope=scope)
        fetched_ok = [
            outcome.evidence_id
            for outcome in python_fetch.outcomes
            if outcome.status.value == "ok"
        ]
        python_checks = await check_citations(ids, fetched_ok, scope=scope)

        agent_tools = _agent_tools(evidence_env)
        agent_fetch = FetchResult.model_validate_json(
            await agent_tools["fetch_evidence"].ainvoke({"evidence_ids": ids})
        )
        agent_checks = CitationResult.model_validate_json(
            await agent_tools["check_citations"].ainvoke({"evidence_ids": ids})
        )
        server = build_server(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _mcp_settings(evidence_env),
        )
        async with Client(server) as client:
            fetch_call = await client.call_tool("fetch_evidence", {"evidence_ids": ids})
            assert not fetch_call.is_error
            mcp_fetch = FetchResult.model_validate(fetch_call.structured_content)
            citation_call = await client.call_tool(
                "check_citations", {"evidence_ids": ids}
            )
            assert not citation_call.is_error
            mcp_checks = CitationResult.model_validate(citation_call.structured_content)

        assert [
            outcome.model_dump(mode="json") for outcome in python_fetch.outcomes
        ] == [outcome.model_dump(mode="json") for outcome in agent_fetch.outcomes]
        assert [
            outcome.model_dump(mode="json") for outcome in python_fetch.outcomes
        ] == [outcome.model_dump(mode="json") for outcome in mcp_fetch.outcomes]
        for checks in (agent_checks, mcp_checks):
            assert [check.model_dump(mode="json") for check in checks.checks] == [
                check.model_dump(mode="json") for check in python_checks.checks
            ]
