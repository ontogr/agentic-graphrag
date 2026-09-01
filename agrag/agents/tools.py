"""Agent tools: thin wrappers calling SearchEngine with fixed Recipes.

Each tool is a LangChain-compatible callable that deepagents can
register. Tools are named for what the agent is trying to find
out, not for the retrieval method they use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from agrag.agents.ledger import Ledger
    from agrag.retrieval.filters import SearchFilters
    from agrag.retrieval.search_engine import SearchEngine


def _make_tool_fn(
    engine: "SearchEngine",
    ledger: "Ledger",
    recipe: Any,
    tool_name: str,
    filters: "SearchFilters | None" = None,
) -> Any:
    """Create a LangChain tool function wrapping SearchEngine.

    Args:
        engine: The SearchEngine to call.
        ledger: The citation ledger for one run.
        recipe: The fixed Recipe this tool uses.
        tool_name: The name for the tool.
        filters: Retrieval scope applied to every search, e.g.
            document or tenant constraints. None searches unfiltered.

    Returns:
        A decorated tool function.
    """
    from langchain_core.tools import tool  # noqa: PLC0415

    @tool(tool_name)
    async def _tool_fn(query: str) -> str:
        """Search the knowledge graph and return cited results."""
        results = await engine.search(query, recipe, filters=filters)
        if not results:
            return "No results found."
        lines = [ledger.render(r) for r in results]
        return "\n".join(lines)

    return _tool_fn


def make_tools(
    engine: "SearchEngine",
    ledger: "Ledger",
    *,
    filters: "SearchFilters | None" = None,
) -> list[Any]:
    """Build the agent's tool set over one SearchEngine and Ledger.

    Args:
        engine: The SearchEngine every tool calls.
        ledger: The citation ledger for one run.
        filters: Retrieval scope applied to every tool's search.
            Pass document or tenant constraints here so the agent
            cannot surface graph data outside them; the LLM never
            sees or chooses the scope.

    Returns:
        A list of LangChain tool instances: search_source_text,
        look_up_entity, find_connection, explore_related, and
        answer_from_graph_structure.
    """
    from agrag.retrieval.recipes import (  # noqa: PLC0415
        CHUNK,
        ENTITY,
        GRAPH_EXPAND,
        HYBRID,
        HYBRID_RERANKED,
    )

    return [
        _make_tool_fn(engine, ledger, CHUNK, "search_source_text", filters),
        _make_tool_fn(engine, ledger, ENTITY, "look_up_entity", filters),
        _make_tool_fn(engine, ledger, GRAPH_EXPAND, "find_connection", filters),
        _make_tool_fn(engine, ledger, HYBRID, "explore_related", filters),
        _make_tool_fn(
            engine,
            ledger,
            HYBRID_RERANKED,
            "answer_from_graph_structure",
            filters,
        ),
    ]
