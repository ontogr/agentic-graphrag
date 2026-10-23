"""Register bounded task and decision tools on the local MCP server."""

from collections.abc import Callable, Sequence
from typing import Annotated, Any
from uuid import UUID

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import CallToolResult, ToolAnnotations
from pydantic import Field

from agrag.common.data_models.decision import (
    DocumentSupportInput,
    ReaffirmDecisionResult,
    RecordDecisionResult,
    RejectDecisionResult,
    SupportInput,
)
from agrag.common.data_models.evidence import FetchOutcome
from agrag.common.data_models.task import (
    CreateTaskResult,
    EventKind,
    RecordEventResult,
    SetStepResult,
    StepKind,
    StepResultBasis,
    StepState,
)
from agrag.decisions import DecisionTraces
from agrag.graphdb.base import GraphStore
from agrag.history import ConversationHistory
from agrag.mcp_server.results import bounded_result
from agrag.mcp_server.settings import McpServerSettings


_WRITE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
_REJECT = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=True,
    open_world_hint=False,
)


def register_write_tools(
    server: MCPServer,
    store: GraphStore,
    settings: McpServerSettings,
    *,
    fetched_evidence_for: Callable[[Context[Any, Any]], Sequence[FetchOutcome]],
) -> None:
    """Register task and decision operations with trusted project identity.

    Args:
        server: MCP server that receives the tools.
        store: Graph store used by the history and decision services.
        settings: Trusted project, author, access gates and limits.
        fetched_evidence_for: Returns complete evidence fetches from this
            server process, never from model-controlled arguments.
    """
    history = ConversationHistory(
        store,
        project_id=settings.project_id,
        agent_id=settings.agent_id,
    )
    decisions = DecisionTraces(
        store, project_id=settings.project_id, agent_id=settings.agent_id
    )
    deadline = settings.request_deadline_seconds

    @server.tool(
        annotations=_WRITE,
        description=(
            "Create a task or return its existing record. A name with another "
            "goal returns task_exists."
        ),
    )
    async def create_task(
        task_name: Annotated[str, Field(min_length=1, max_length=200)],
        goal: Annotated[str, Field(min_length=1, max_length=4000)],
        request_id: Annotated[str, Field(min_length=1, max_length=64)],
    ) -> Annotated[CallToolResult, CreateTaskResult]:
        """Create a task in the configured project with a retry key."""
        return await bounded_result(
            deadline,
            settings.max_response_chars,
            history.create_task(task_name, goal, request_id=request_id),
        )

    @server.tool(
        annotations=_WRITE,
        description=(
            "Append a bounded raw event. The payload hash covers the full "
            "supplied text."
        ),
    )
    async def record_event(  # noqa: PLR0917
        task_name: Annotated[str, Field(min_length=1, max_length=200)],
        kind: EventKind,
        payload: Annotated[str, Field(max_length=1_000_000)],
        request_id: Annotated[str, Field(min_length=1, max_length=64)],
        role: Annotated[str | None, Field(max_length=100)] = None,
        name: Annotated[str | None, Field(max_length=200)] = None,
    ) -> Annotated[CallToolResult, RecordEventResult]:
        """Append one message, tool call, tool result or note."""
        return await bounded_result(
            deadline,
            settings.max_response_chars,
            history.record_event(
                task_name,
                kind,
                role=role,
                name=name,
                payload=payload,
                request_id=request_id,
            ),
        )

    @server.tool(annotations=_WRITE, description="Create or update a named task step.")
    async def set_step(  # noqa: PLR0917
        ctx: Context[Any, Any],
        task_name: Annotated[str, Field(min_length=1, max_length=200)],
        name: Annotated[str, Field(min_length=1, max_length=200)],
        state: StepState,
        request_id: Annotated[str, Field(min_length=1, max_length=64)],
        kind: StepKind = StepKind.OTHER,
        result_event_seq: Annotated[int | None, Field(ge=1)] = None,
        result_basis: StepResultBasis = StepResultBasis.UNKNOWN,
        supports: Annotated[list[SupportInput] | None, Field(max_length=20)] = None,
    ) -> Annotated[CallToolResult, SetStepResult]:
        """Set a step state with its result basis and trusted source evidence."""
        fetched = list(fetched_evidence_for(ctx))
        return await bounded_result(
            deadline,
            settings.max_response_chars,
            history.set_step(
                task_name,
                name,
                state,
                kind=kind,
                result_event_seq=result_event_seq,
                result_basis=result_basis,
                supports=supports or (),
                fetched_evidence=fetched,
                request_id=request_id,
            ),
        )

    @server.tool(
        annotations=_WRITE,
        description=(
            "Record a decision with explicit support references. Document "
            "evidence must have been fetched by this server session."
        ),
    )
    async def record_decision(  # noqa: PLR0917
        ctx: Context[Any, Any],
        task_name: Annotated[str, Field(min_length=1, max_length=200)],
        choice_key: Annotated[str, Field(min_length=1, max_length=200)],
        conclusion: Annotated[str, Field(min_length=1, max_length=4000)],
        rationale: Annotated[str, Field(min_length=1, max_length=8000)],
        supports: Annotated[list[SupportInput], Field(min_length=1, max_length=20)],
        request_id: Annotated[str, Field(min_length=1, max_length=64)],
        assumptions: Annotated[list[str], Field(max_length=20)],
        open_questions: Annotated[list[str], Field(max_length=20)],
    ) -> Annotated[CallToolResult, RecordDecisionResult]:
        """Record a supported decision with a safe retry key."""
        fetched = list(fetched_evidence_for(ctx))
        return await bounded_result(
            deadline,
            settings.max_response_chars,
            decisions.record_decision(
                task_name,
                choice_key,
                conclusion,
                rationale,
                supports=supports,
                fetched_evidence=fetched,
                assumptions=assumptions,
                open_questions=open_questions,
                request_id=request_id,
            ),
        )

    @server.tool(
        annotations=_WRITE,
        description="Supersede a decision while preserving its history.",
    )
    async def supersede_decision(  # noqa: PLR0917
        ctx: Context[Any, Any],
        decision_id: UUID,
        conclusion: Annotated[str, Field(min_length=1, max_length=4000)],
        rationale: Annotated[str, Field(min_length=1, max_length=8000)],
        explanation: Annotated[str, Field(min_length=1, max_length=4000)],
        supports: Annotated[list[SupportInput], Field(min_length=1, max_length=20)],
        request_id: Annotated[str, Field(min_length=1, max_length=64)],
        assumptions: Annotated[list[str], Field(max_length=20)],
        open_questions: Annotated[list[str], Field(max_length=20)],
    ) -> Annotated[CallToolResult, RecordDecisionResult]:
        """Record a same-choice replacement with its reason and support."""
        return await bounded_result(
            deadline,
            settings.max_response_chars,
            decisions.supersede_decision(
                decision_id,
                conclusion,
                rationale,
                explanation=explanation,
                supports=supports,
                fetched_evidence=list(fetched_evidence_for(ctx)),
                assumptions=assumptions,
                open_questions=open_questions,
                request_id=request_id,
            ),
        )

    @server.tool(
        annotations=_WRITE,
        description=(
            "Reaffirm an active decision using current fetched document evidence."
        ),
    )
    async def reaffirm_decision(
        ctx: Context[Any, Any],
        decision_id: UUID,
        evidence_ids: Annotated[list[str], Field(min_length=1, max_length=20)],
        explanation: Annotated[str, Field(min_length=1, max_length=4000)],
        request_id: Annotated[str, Field(min_length=1, max_length=64)],
    ) -> Annotated[CallToolResult, ReaffirmDecisionResult]:
        """Reaffirm a decision with evidence fetched in this server session."""
        supports = [DocumentSupportInput(evidence_id=item) for item in evidence_ids]
        return await bounded_result(
            deadline,
            settings.max_response_chars,
            decisions.reaffirm_decision(
                decision_id,
                supports,
                fetched_evidence=list(fetched_evidence_for(ctx)),
                explanation=explanation,
                request_id=request_id,
            ),
        )

    @server.tool(
        annotations=_WRITE,
        description="Continue bounded project-scoped decision review propagation.",
    )
    async def continue_decision_review(
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> Annotated[CallToolResult, int]:
        """Process at most the requested number of queued review units."""
        return await bounded_result(
            deadline,
            settings.max_response_chars,
            decisions.continue_decision_review(limit=limit),
        )

    if settings.allow_reject:

        @server.tool(
            annotations=_REJECT,
            description="Reject a decision while preserving its history.",
        )
        async def reject_decision(
            decision_id: UUID,
            reason: Annotated[str, Field(min_length=1, max_length=4000)],
            request_id: Annotated[str, Field(min_length=1, max_length=64)],
        ) -> Annotated[CallToolResult, RejectDecisionResult]:
            """Mark a decision rejected using the operator-authorized tool."""
            return await bounded_result(
                deadline,
                settings.max_response_chars,
                decisions.reject_decision(decision_id, reason, request_id=request_id),
            )
