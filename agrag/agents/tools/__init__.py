"""Agent tools: thin wrappers calling SearchEngine with fixed Recipes.

Each tool is a LangChain-compatible callable that deepagents can register.
Tools are named for what the agent is trying to find out, not for the
retrieval method they use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agrag.agents.tools.search import (
    make_answer_from_graph_structure_tool,
    make_answer_thematic_question_tool,
    make_explore_related_tool,
    make_look_up_entity_tool,
    make_query_graph_directly_tool,
    make_search_source_text_tool,
)
from agrag.agents.tools.traversal import (
    make_describe_entity_tool,
    make_find_related_entities_tool,
    make_list_relationship_types_tool,
    make_traverse_from_entity_tool,
)


if TYPE_CHECKING:
    from agrag.agents.ledger import Ledger
    from agrag.retrieval.filters import SearchFilters
    from agrag.retrieval.search_engine import SearchEngine


__all__ = ["make_tools"]


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
        filters: Caller-set retrieval scope applied to every tool's
            search, e.g. document or tenant constraints. The model never
            sees this scope and cannot widen it: a tool argument that
            falls outside it is refused rather than merged. None searches
            unscoped.

    Returns:
        A list of LangChain tool instances: search_source_text,
        look_up_entity, explore_related, answer_from_graph_structure,
        answer_thematic_question, list_relationship_types,
        find_related_entities, describe_entity, traverse_from_entity,
        and compute_over_evidence. query_graph_directly joins them
        only when filters is None or empty: it runs a generated
        read-only Cypher query, which cannot be confined to a caller
        scope, so a scoped agent never receives it.
    """
    # Imported here, not at module scope: aggregate.py decorates its
    # function at import time, which would make this package require
    # langchain_core to import at all.
    from agrag.agents.tools.aggregate import (  # noqa: PLC0415
        compute_over_evidence,
    )
    from agrag.retrieval.filters import SearchFilters  # noqa: PLC0415

    tools: list[Any] = [
        make_search_source_text_tool(engine, ledger, filters=filters),
        make_look_up_entity_tool(engine, ledger, filters=filters),
        make_explore_related_tool(engine, ledger, filters=filters),
        make_answer_from_graph_structure_tool(engine, ledger, filters=filters),
        make_answer_thematic_question_tool(engine, ledger, filters=filters),
        make_list_relationship_types_tool(engine, ledger, filters=filters),
        make_find_related_entities_tool(engine, ledger, filters=filters),
        make_describe_entity_tool(engine, ledger, filters=filters),
        make_traverse_from_entity_tool(engine, ledger, filters=filters),
        compute_over_evidence,
    ]
    if filters is None or filters == SearchFilters():
        tools.append(make_query_graph_directly_tool(engine, ledger, filters=filters))
    return tools
