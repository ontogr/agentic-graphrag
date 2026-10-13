"""The tool that searches candidates the extractor kept out of the graph."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agrag.agents.tracing import tool_span_context
from agrag.common.data_models.candidate import CandidateKind, CandidateRecord


if TYPE_CHECKING:
    from agrag.retrieval.search_engine import SearchEngine


_HEADER = "Unreviewed candidates (not in the graph, not checked by a person):"
_NONE = "No unreviewed candidates match."


def _describe(record: CandidateRecord) -> str:
    """Format one candidate as one line that starts with ``unreviewed``."""
    what = (
        f"{record.source_text} -> {record.target_text}"
        if record.kind == "relation"
        else record.text
    )
    return (
        f"unreviewed {record.kind} {record.label}: {what} "
        f"(seen {record.count} times, reason: {record.reason})"
    )


def make_search_candidates_tool(engine: SearchEngine) -> Any:
    """Build the search_unreviewed_candidates tool.

    Args:
        engine: The SearchEngine the tool calls.

    Returns:
        A decorated tool function.
    """
    from langchain_core.tools import tool  # noqa: PLC0415

    @tool("search_unreviewed_candidates")
    async def search_unreviewed_candidates(  # noqa: D417
        query: str,
        kind: CandidateKind | None = None,
        limit: int = 10,
        callbacks: Any = None,
    ) -> str:
        """Search items the extractor saw but did not add to the graph.

        These items are unreviewed and may be wrong. Use this only when other
        tools find nothing or the question asks what the graph is missing.
        Report every result as unreviewed. Never state one as a graph fact or
        cite it as evidence.

        Args:
            query: Words to look for in labels and names.
            kind: Only this kind of item: entity, relation or property.
            limit: The most items to return.
        """
        with tool_span_context(callbacks):
            records = await engine.search_candidates(query, kind=kind, limit=limit)
        if not records:
            return _NONE
        return "\n".join([_HEADER, *(_describe(record) for record in records)])

    return search_unreviewed_candidates
