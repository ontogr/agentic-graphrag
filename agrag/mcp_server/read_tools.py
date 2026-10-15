"""Register project-scoped task and decision read tools."""

import asyncio
from typing import Annotated, Any, TypeVar
from uuid import UUID

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field
from pydantic_core import to_json

from agrag.common.data_models.decision import (
    ConflictList,
    DecisionHit,
    DecisionLookup,
)
from agrag.common.data_models.task import EventPage, TaskLookup
from agrag.graphdb.base import GraphStore
from agrag.mcp_server.settings import McpServerSettings
from agrag.memory import DecisionMemory, TaskMemory


_READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
_ResultT = TypeVar("_ResultT")


def register_memory_read_tools(
    server: MCPServer, store: GraphStore, settings: McpServerSettings
) -> None:
    """Register bounded reads, including when write access is disabled.

    Args:
        server: MCP server that receives the read tools.
        store: Graph store used by the memory services.
        settings: Trusted project identity and output limits.
    """
    tasks = TaskMemory(
        store, project_id=settings.project_id, agent_id=settings.agent_id
    )
    decisions = DecisionMemory(
        store, project_id=settings.project_id, agent_id=settings.agent_id
    )

    @server.tool(
        annotations=_READ_ONLY,
        description="Read the bounded task resume view in the configured project.",
    )
    async def get_task(
        name: Annotated[str, Field(min_length=1, max_length=200)],
    ) -> TaskLookup:
        """Return task state without event bodies."""
        return await _bounded(settings, tasks.get_task(name))

    @server.tool(
        annotations=_READ_ONLY,
        description="List bounded events for a task after a sequence number.",
    )
    async def list_events(
        task_name: Annotated[str, Field(min_length=1, max_length=200)],
        after_seq: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=200)] = 50,
    ) -> EventPage:
        """Return task events in sequence order."""
        return await _bounded(
            settings,
            tasks.list_events(task_name, after_seq=after_seq, limit=limit),
        )

    @server.tool(
        annotations=_READ_ONLY,
        description="Fetch one event by task name and sequence number.",
    )
    async def fetch_event(
        task_name: Annotated[str, Field(min_length=1, max_length=200)],
        seq: Annotated[int, Field(ge=1)],
    ) -> EventPage:
        """Return the requested event in a one-event page, or an empty page."""
        page = await _bounded(
            settings, tasks.list_events(task_name, after_seq=seq - 1, limit=1)
        )
        if not page.events or page.events[0].seq != seq:
            return page.model_copy(update={"events": [], "truncated": False})
        return page.model_copy(update={"truncated": False, "next_after_seq": None})

    @server.tool(
        annotations=_READ_ONLY,
        description=(
            "Find same-project decisions as precedents. Results do not imply "
            "applicability."
        ),
    )
    async def search_decisions(
        query: Annotated[str, Field(min_length=1, max_length=1000)],
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> list[DecisionHit]:
        """Search decisions in the configured project."""
        return await _bounded(
            settings,
            decisions.search_decisions(query, limit=min(limit, settings.max_hits)),
        )

    @server.tool(
        annotations=_READ_ONLY,
        description="List active cross-task conflicts in the configured project.",
    )
    async def list_conflicts() -> ConflictList:
        """Return same-choice decisions with different conclusions."""
        return await _bounded(settings, decisions.list_conflicts())

    @server.tool(
        annotations=_READ_ONLY,
        description=(
            "Fetch one decision by id only when it belongs to the configured project."
        ),
    )
    async def get_decision(decision_id: UUID) -> DecisionLookup:
        """Return a project-scoped decision lookup."""
        return await _bounded(settings, decisions.get_decision(decision_id))


async def _bounded(settings: McpServerSettings, operation: Any) -> Any:
    """Apply the deadline and serialized-result cap without exposing details."""
    try:
        async with asyncio.timeout(settings.request_deadline_seconds):
            result = await operation
    except TimeoutError:
        raise ToolError("memory operation deadline exceeded") from None
    if 2 * len(to_json(result)) > settings.max_response_chars:
        raise ToolError("memory result exceeds the configured response limit")
    return result
