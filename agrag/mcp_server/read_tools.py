"""Register bounded evidence, history, and decision read tools."""

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
from agrag.common.data_models.evidence import EvidenceSearchMode
from agrag.common.data_models.navigation import NavigationRelation, NavigationResult
from agrag.common.data_models.task import (
    EventLookup,
    EventPage,
    StepPage,
    StepState,
    TaskLookup,
)
from agrag.common.data_models.theme_search import ThemeResult
from agrag.decisions import DecisionTraces
from agrag.embedding.base import Embedder
from agrag.evidence import (
    entity_search as entity_search_evidence,
)
from agrag.evidence import (
    explore_relationships as explore_relationships_evidence,
)
from agrag.evidence import (
    navigate_document_tree as navigate_document_tree_evidence,
)
from agrag.evidence import (
    search_themes as search_themes_evidence,
)
from agrag.evidence.contract import (
    DEFAULT_MAX_EDGES,
    DEFAULT_MAX_NODES,
    DEFAULT_NAV_LIMIT,
    DEFAULT_NAV_MAX_CHARS,
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_SUPPORT_LIMIT,
    DEFAULT_THEME_LIMIT,
    ENTITY_SEARCH,
    EXPLORE_RELATIONSHIPS,
    NAVIGATE_DOCUMENT_TREE,
    SEARCH_THEMES,
    EntityId,
    EvidenceId,
    ExploreBound,
    ExploreDepth,
    Labels,
    NavMaxChars,
    Query,
    RelationTypes,
    SearchLimit,
    SupportLimit,
    ThemeLimit,
)
from agrag.graphdb.base import GraphStore
from agrag.history import ConversationHistory
from agrag.mcp_server.results import bounded_result
from agrag.mcp_server.settings import McpServerSettings
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


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
    vector_store: VectorStore | None = None,
    *,
    retrieval_settings: RetrievalSettings,
    timeout: float,
) -> None:
    """Register scoped evidence search, exploration and navigation tools.

    Args:
        server: MCP server that receives the read tools.
        store: Graph store used by the evidence services.
        settings: Trusted source scope and output limits.
        embedder: Query embedder for entity and theme search.
        vector_store: Optional external vector store for semantic legs.
        retrieval_settings: Fusion and rerank configuration for the searches.
        timeout: Store-read timeout in seconds for each evidence operation.
    """

    @server.tool(
        annotations=_READ_ONLY,
        description=ENTITY_SEARCH,
    )
    async def entity_search(
        query: Query,
        labels: Labels = None,
        mode: EvidenceSearchMode = EvidenceSearchMode.HYBRID,
        limit: SearchLimit = DEFAULT_SEARCH_LIMIT,
        support_limit: SupportLimit = DEFAULT_SUPPORT_LIMIT,
    ) -> Annotated[CallToolResult, EntityResult]:
        """Find entities using only the configured document scope."""
        return await _bounded(
            settings,
            entity_search_evidence(
                store,
                embedder,
                query,
                scope=settings.scope,
                labels=labels,
                mode=mode,
                limit=min(limit, settings.max_hits),
                support_limit=support_limit,
                vector_store=vector_store,
                settings=retrieval_settings,
                timeout=timeout,
            ),
        )

    @server.tool(
        annotations=_READ_ONLY,
        description=EXPLORE_RELATIONSHIPS,
    )
    async def explore_relationships(
        entity_id: EntityId,
        depth: ExploreDepth = 1,
        relation_types: RelationTypes = None,
        max_nodes: ExploreBound = DEFAULT_MAX_NODES,
        max_edges: ExploreBound = DEFAULT_MAX_EDGES,
    ) -> Annotated[CallToolResult, ExplorationResult]:
        """Explore relations without allowing the caller to widen source scope."""
        return await _bounded(
            settings,
            explore_relationships_evidence(
                store,
                entity_id,
                scope=settings.scope,
                depth=depth,
                relation_types=relation_types,
                max_nodes=max_nodes,
                max_edges=max_edges,
                timeout=timeout,
            ),
        )

    @server.tool(
        annotations=_READ_ONLY,
        description=NAVIGATE_DOCUMENT_TREE,
    )
    async def navigate_document_tree(
        evidence_id: EvidenceId,
        relation: NavigationRelation,
        limit: SearchLimit = DEFAULT_NAV_LIMIT,
        max_chars: NavMaxChars = DEFAULT_NAV_MAX_CHARS,
    ) -> Annotated[CallToolResult, NavigationResult]:
        """Read neighboring passages within the trusted document scope."""
        return await _bounded(
            settings,
            navigate_document_tree_evidence(
                store,
                evidence_id,
                relation,
                scope=settings.scope,
                limit=limit,
                max_chars=max_chars,
                timeout=timeout,
            ),
        )

    @server.tool(
        annotations=_READ_ONLY,
        description=SEARCH_THEMES,
    )
    async def search_themes(
        query: Query,
        limit: ThemeLimit = DEFAULT_THEME_LIMIT,
        support_limit: SupportLimit = DEFAULT_SUPPORT_LIMIT,
    ) -> Annotated[CallToolResult, ThemeResult]:
        """Find themes using only the configured document scope."""
        return await _bounded(
            settings,
            search_themes_evidence(
                store,
                embedder,
                query,
                scope=settings.scope,
                limit=min(limit, settings.max_hits),
                support_limit=support_limit,
                vector_store=vector_store,
                settings=retrieval_settings,
                timeout=timeout,
            ),
        )


def register_history_read_tools(
    server: MCPServer, store: GraphStore, settings: McpServerSettings
) -> None:
    """Register task-history and decision reads in the configured project.

    Args:
        server: MCP server that receives the read tools.
        store: Graph store used by the history and decision services.
        settings: Trusted project identity and output limits.
    """
    history = ConversationHistory(
        store, project_id=settings.project_id, agent_id=settings.agent_id
    )
    decisions = DecisionTraces(
        store, project_id=settings.project_id, agent_id=settings.agent_id
    )

    @server.tool(
        annotations=_READ_ONLY,
        description="Read the bounded task resume view in the configured project.",
    )
    async def get_task(
        task_name: Annotated[str, Field(min_length=1, max_length=200)],
    ) -> Annotated[CallToolResult, TaskLookup]:
        """Return task state without event bodies."""
        return await _bounded(settings, history.get_task(task_name))

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
            history.list_events(task_name, after_seq=after_seq, limit=limit),
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
        return await _bounded(settings, history.fetch_event(task_name, seq))

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
            history.list_steps(task_name, state, after_name=after_name, limit=limit),
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
    async def list_decisions_for_review(
        task_name: Annotated[str | None, Field(max_length=200)] = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> Annotated[CallToolResult, DecisionReviewList]:
        """Return decisions needing review, optionally limited to one task."""
        return await _bounded(
            settings,
            decisions.list_decisions_for_review(task_name=task_name, limit=limit),
        )


async def _bounded(settings: McpServerSettings, operation: Any) -> CallToolResult:
    """Bound one read against the configured deadline and response size."""
    return await bounded_result(
        settings.request_deadline_seconds, settings.max_response_chars, operation
    )
