"""Register bounded evidence and project memory read tools."""

from typing import Annotated, Any
from uuid import UUID

from mcp.server import MCPServer
from mcp.types import CallToolResult, ToolAnnotations
from pydantic import Field

from agrag.common.data_models.decision import (
    ConflictList,
    DecisionHit,
    DecisionLookup,
    DecisionPageLookup,
    DecisionReviewList,
    SupportHistoryPage,
)
from agrag.common.data_models.entity_search import EntityResult, ExplorationResult
from agrag.common.data_models.evidence import DiscoveryMode
from agrag.common.data_models.navigation import NavigationRelation, NavigationResult
from agrag.common.data_models.task import (
    EventLookup,
    EventPage,
    StepPage,
    StepState,
    TaskLookup,
)
from agrag.embedding.base import Embedder
from agrag.evidence import (
    explore as explore_evidence,
)
from agrag.evidence import (
    find_entities as find_entities_evidence,
)
from agrag.evidence import (
    navigate as navigate_evidence,
)
from agrag.graphdb.base import GraphStore
from agrag.mcp_server.results import bounded_result
from agrag.mcp_server.settings import McpServerSettings
from agrag.memory import DecisionMemory, TaskMemory


_READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


def register_evidence_read_tools(
    server: MCPServer,
    store: GraphStore,
    embedder: Embedder,
    settings: McpServerSettings,
) -> None:
    """Register scoped entity search, exploration and navigation tools.

    Args:
        server: MCP server that receives the read tools.
        store: Graph store used by the evidence services.
        settings: Trusted source scope and output limits.
        embedder: Query embedder for entity search.
    """

    @server.tool(
        annotations=_READ_ONLY,
        description="Find entities with support in configured documents.",
    )
    async def find_entities(
        query: Annotated[str, Field(min_length=1, max_length=1000)],
        labels: Annotated[list[str] | None, Field(max_length=20)] = None,
        mode: DiscoveryMode = DiscoveryMode.HYBRID,
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
    ) -> Annotated[CallToolResult, EntityResult]:
        """Find entities using only the configured document scope."""
        return await _bounded(
            settings,
            find_entities_evidence(
                store,
                embedder,
                query,
                scope=settings.scope,
                labels=labels,
                mode=mode,
                limit=min(limit, settings.max_hits),
            ),
        )

    @server.tool(
        annotations=_READ_ONLY,
        description="Explore supported entity relations in configured documents.",
    )
    async def explore(
        entity_id: Annotated[str, Field(min_length=1, max_length=100)],
        depth: Annotated[int, Field(ge=1, le=2)] = 1,
        relation_types: Annotated[list[str] | None, Field(max_length=20)] = None,
        max_nodes: Annotated[int, Field(ge=1, le=200)] = 25,
        max_edges: Annotated[int, Field(ge=1, le=200)] = 50,
    ) -> Annotated[CallToolResult, ExplorationResult]:
        """Explore relations without allowing the caller to widen source scope."""
        return await _bounded(
            settings,
            explore_evidence(
                store,
                entity_id,
                scope=settings.scope,
                depth=depth,
                relation_types=relation_types,
                max_nodes=max_nodes,
                max_edges=max_edges,
            ),
        )

    @server.tool(
        annotations=_READ_ONLY,
        description="Navigate to nearby passages in configured documents.",
    )
    async def navigate(
        evidence_id: Annotated[str, Field(min_length=1, max_length=500)],
        relation: NavigationRelation,
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
        max_chars: Annotated[int, Field(ge=1, le=20000)] = 12000,
    ) -> Annotated[CallToolResult, NavigationResult]:
        """Read neighboring passages within the trusted document scope."""
        return await _bounded(
            settings,
            navigate_evidence(
                store,
                evidence_id,
                relation,
                scope=settings.scope,
                limit=limit,
                max_chars=max_chars,
            ),
        )


def register_memory_read_tools(
    server: MCPServer, store: GraphStore, settings: McpServerSettings
) -> None:
    """Register task and decision reads in the configured project.

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
    ) -> Annotated[CallToolResult, TaskLookup]:
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
    ) -> Annotated[CallToolResult, EventPage]:
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
    ) -> Annotated[CallToolResult, EventLookup]:
        """Return exactly the requested event, or not-found."""
        return await _bounded(settings, tasks.get_event(task_name, seq))

    @server.tool(
        annotations=_READ_ONLY, description="Read one bounded page of task steps."
    )
    async def list_steps(
        task_name: Annotated[str, Field(min_length=1, max_length=200)],
        state: StepState,
        after_name: Annotated[str | None, Field(max_length=200)] = None,
        limit: Annotated[int, Field(ge=1, le=200)] = 50,
    ) -> Annotated[CallToolResult, StepPage]:
        """Return steps in one state, with a continuation cursor."""
        return await _bounded(
            settings,
            tasks.list_steps_page(task_name, state, after_name=after_name, limit=limit),
        )

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
    ) -> Annotated[CallToolResult, list[DecisionHit]]:
        """Search decisions in the configured project."""
        return await _bounded(
            settings,
            decisions.search_decisions(query, limit=min(limit, settings.max_hits)),
        )

    @server.tool(
        annotations=_READ_ONLY,
        description="List active cross-task conflicts in the configured project.",
    )
    async def list_conflicts() -> Annotated[CallToolResult, ConflictList]:
        """Return same-choice decisions with different conclusions."""
        return await _bounded(settings, decisions.list_conflicts())

    @server.tool(
        annotations=_READ_ONLY,
        description=(
            "Fetch one decision by id only when it belongs to the configured project."
        ),
    )
    async def get_decision(
        decision_id: UUID,
    ) -> Annotated[CallToolResult, DecisionLookup]:
        """Return a project-scoped decision lookup."""
        return await _bounded(settings, decisions.get_decision(decision_id))

    @server.tool(
        annotations=_READ_ONLY,
        description="Read one page of original and refreshed decision supports.",
    )
    async def list_support_history(
        decision_id: UUID,
        after_ordinal: int = -1,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> Annotated[CallToolResult, SupportHistoryPage]:
        """Return original evidence identities and review transitions."""
        return await _bounded(
            settings,
            decisions.list_support_history(
                decision_id, after_ordinal=after_ordinal, limit=limit
            ),
        )

    @server.tool(
        annotations=_READ_ONLY,
        description="List a task's decisions and lifecycle history.",
    )
    async def list_decisions(
        task_name: Annotated[str, Field(min_length=1, max_length=200)],
    ) -> Annotated[CallToolResult, DecisionPageLookup]:
        """Return bounded decisions and their support history for one task."""
        return await _bounded(settings, decisions.list_decisions(task_name))

    @server.tool(
        annotations=_READ_ONLY, description="List active decisions that need review."
    )
    async def list_needing_review(
        task_name: Annotated[str | None, Field(max_length=200)] = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> Annotated[CallToolResult, DecisionReviewList]:
        """Return decisions needing review, optionally limited to one task."""
        return await _bounded(
            settings, decisions.list_review(task_name=task_name, limit=limit)
        )


async def _bounded(settings: McpServerSettings, operation: Any) -> CallToolResult:
    """Bound one read against the configured deadline and response size."""
    return await bounded_result(
        settings.request_deadline_seconds, settings.max_response_chars, operation
    )
