"""Tools for scoped evidence, conversation history, and decisions."""

import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from agrag.agents.middleware import RunState, record_event_or_flag
from agrag.agents.tracing import tool_span_context
from agrag.common.data_models.decision import (
    DecisionSupportInput,
    DocumentSupportInput,
    SupportInput,
)
from agrag.common.data_models.evidence import (
    EvidenceSearchMode,
    FetchOutcome,
    FetchStatus,
)
from agrag.common.data_models.navigation import NavigationRelation
from agrag.common.data_models.task import (
    EventKind,
    StepKind,
    StepResultBasis,
    StepState,
)
from agrag.decisions import DecisionTraces
from agrag.embedding.base import Embedder
from agrag.evidence import (
    check_citations,
    entity_search,
    explore_relationships,
    fetch_evidence,
    navigate_document_tree,
    search_evidence,
    search_themes,
)
from agrag.evidence.contract import (
    CHECK_CITATIONS,
    DEFAULT_MAX_EDGES,
    DEFAULT_MAX_NODES,
    DEFAULT_NAV_LIMIT,
    DEFAULT_NAV_MAX_CHARS,
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_SUPPORT_LIMIT,
    DEFAULT_THEME_LIMIT,
    ENTITY_SEARCH,
    EXPLORE_RELATIONSHIPS,
    FETCH_EVIDENCE,
    NAVIGATE_DOCUMENT_TREE,
    SEARCH_EVIDENCE,
    SEARCH_THEMES,
    EntityId,
    EvidenceId,
    EvidenceIds,
    ExploreBound,
    ExploreDepth,
    FetchMaxChars,
    Labels,
    NavMaxChars,
    Query,
    RelationTypes,
    SearchLimit,
    SupportLimit,
    ThemeLimit,
    validation_message,
)
from agrag.evidence.rerank import Reranker
from agrag.graphdb.base import GraphStore
from agrag.history import ConversationHistory
from agrag.retrieval import RetrievalSettings
from agrag.vectordb.base import VectorStore


def make_core_tools(  # noqa: PLR0915
    *,
    graph_store: GraphStore,
    embedder: Embedder,
    scope: frozenset[str],
    task_name: str,
    history: ConversationHistory,
    decisions: DecisionTraces,
    fetched_ids: list[str],
    fetched_outcomes: Sequence[FetchOutcome],
    max_chars: int,
    max_tool_calls: int,
    retrieval_settings: RetrievalSettings,
    reranker: Reranker | None = None,
    timeout: float | None = None,
    vector_store: VectorStore | None = None,
) -> tuple[list[Any], RunState]:
    """Bind evidence, history, and decision tools to one trusted task scope."""
    from langchain_core.tools import tool  # noqa: PLC0415

    run_state = RunState(
        max_tool_calls=max_tool_calls,
        fetched_ids=fetched_ids,
        fetches={item.evidence_id: item for item in fetched_outcomes},
    )

    @tool("search_evidence", description=SEARCH_EVIDENCE)
    async def search_evidence_tool(
        query: Query,
        mode: EvidenceSearchMode = EvidenceSearchMode.HYBRID,
        limit: SearchLimit = DEFAULT_SEARCH_LIMIT,
        callbacks: Any = None,
    ) -> str:
        """Find in-scope source passages and return their evidence ids."""
        with tool_span_context(callbacks):
            found = await search_evidence(
                graph_store,
                embedder,
                query,
                mode=mode,
                limit=limit,
                scope=scope,
                vector_store=vector_store,
                reranker=reranker,
                settings=retrieval_settings,
                timeout=timeout,
            )
            run_state.retrieval_failed |= (
                found.status.value not in {"ok", "no_match", "empty_scope"}
                or found.truncated
            )
            return found.model_dump_json()

    search_evidence_tool.handle_validation_error = validation_message

    fetch_char_cap = max_chars

    @tool("fetch_evidence", description=FETCH_EVIDENCE)
    async def fetch_evidence_tool(
        evidence_ids: EvidenceIds,
        max_chars: FetchMaxChars = None,
        callbacks: Any = None,
    ) -> str:
        """Fetch exact passage text for evidence ids returned by discovery."""
        with tool_span_context(callbacks):
            effective_chars = (
                min(max_chars, fetch_char_cap)
                if max_chars is not None
                else fetch_char_cap
            )
            result = await fetch_evidence(
                graph_store,
                evidence_ids,
                scope=scope,
                max_chars=effective_chars,
                timeout=timeout,
            )
            for outcome in result.outcomes:
                run_state.fetches[outcome.evidence_id] = outcome
                if outcome.status is FetchStatus.OK:
                    run_state.fetched_ids.append(outcome.evidence_id)
                elif outcome.status in {
                    FetchStatus.FAILED,
                    FetchStatus.TRUNCATED,
                    FetchStatus.PARTIAL,
                }:
                    run_state.retrieval_failed = True
            valid_ids = [
                o.evidence_id for o in result.outcomes if o.status is FetchStatus.OK
            ]
            if valid_ids:
                await record_event_or_flag(
                    history,
                    task_name,
                    run_state,
                    EventKind.NOTE,
                    name="fetched_evidence",
                    payload=json.dumps(valid_ids),
                )
            return result.model_dump_json()

    fetch_evidence_tool.handle_validation_error = validation_message

    @tool("navigate_document_tree", description=NAVIGATE_DOCUMENT_TREE)
    async def navigate_evidence(
        evidence_id: EvidenceId,
        relation: NavigationRelation,
        limit: SearchLimit = DEFAULT_NAV_LIMIT,
        max_chars: NavMaxChars = DEFAULT_NAV_MAX_CHARS,
        callbacks: Any = None,
    ) -> str:
        """Read nearby passages in the same document version."""
        with tool_span_context(callbacks):
            result = await navigate_document_tree(
                graph_store,
                evidence_id,
                relation,
                scope=scope,
                limit=limit,
                max_chars=max_chars,
                timeout=timeout,
            )
            run_state.retrieval_failed |= (
                result.status.value == "failed" or result.truncated
            )
            return result.model_dump_json()

    navigate_evidence.handle_validation_error = validation_message

    @tool("entity_search", description=ENTITY_SEARCH)
    async def search_entities(
        query: Query,
        labels: Labels = None,
        mode: EvidenceSearchMode = EvidenceSearchMode.HYBRID,
        limit: SearchLimit = DEFAULT_SEARCH_LIMIT,
        support_limit: SupportLimit = DEFAULT_SUPPORT_LIMIT,
        *,
        callbacks: Any = None,
    ) -> str:
        """Find entities whose names match the query and show source support."""
        with tool_span_context(callbacks):
            result = await entity_search(
                graph_store,
                embedder,
                query,
                scope=scope,
                labels=labels,
                mode=mode,
                limit=limit,
                support_limit=support_limit,
                vector_store=vector_store,
                settings=retrieval_settings,
                timeout=timeout,
            )
            run_state.retrieval_failed |= (
                result.status.value not in {"ok", "no_match", "empty_scope"}
                or result.truncated
            )
            return result.model_dump_json()

    search_entities.handle_validation_error = validation_message

    @tool("explore_relationships", description=EXPLORE_RELATIONSHIPS)
    async def explore_relationships_tool(
        entity_id: EntityId,
        depth: ExploreDepth = 1,
        relation_types: RelationTypes = None,
        max_nodes: ExploreBound = DEFAULT_MAX_NODES,
        max_edges: ExploreBound = DEFAULT_MAX_EDGES,
        *,
        callbacks: Any = None,
    ) -> str:
        """Explore supported relations around an entity within fixed bounds."""
        with tool_span_context(callbacks):
            result = await explore_relationships(
                graph_store,
                entity_id,
                scope=scope,
                relation_types=relation_types,
                depth=depth,
                max_nodes=max_nodes,
                max_edges=max_edges,
                timeout=timeout,
            )
            run_state.retrieval_failed |= result.status.value == "failed" or bool(
                result.truncated_by
            )
            return result.model_dump_json()

    explore_relationships_tool.handle_validation_error = validation_message

    @tool("search_themes", description=SEARCH_THEMES)
    async def search_themes_tool(
        query: Query,
        limit: ThemeLimit = DEFAULT_THEME_LIMIT,
        support_limit: SupportLimit = DEFAULT_SUPPORT_LIMIT,
        callbacks: Any = None,
    ) -> str:
        """Find themes that span many documents, with their supporting passages."""
        with tool_span_context(callbacks):
            found = await search_themes(
                graph_store,
                embedder,
                query,
                scope=scope,
                limit=limit,
                support_limit=support_limit,
                vector_store=vector_store,
                settings=retrieval_settings,
                timeout=timeout,
            )
            run_state.retrieval_failed |= (
                found.status.value not in {"ok", "no_match", "empty_scope"}
                or found.truncated
            )
            return found.model_dump_json()

    search_themes_tool.handle_validation_error = validation_message

    @tool("check_citations", description=CHECK_CITATIONS)
    async def check_citations_tool(
        evidence_ids: EvidenceIds,
        callbacks: Any = None,
    ) -> str:
        """Check that evidence ids were fetched in the permitted scope."""
        with tool_span_context(callbacks):
            result = await check_citations(
                evidence_ids, run_state.fetched_ids, scope=scope
            )
            return result.model_dump_json()

    check_citations_tool.handle_validation_error = validation_message

    @tool
    async def get_task() -> str:
        """Read this task's bounded resume view."""
        lookup = await history.get_task(task_name)
        return lookup.model_dump_json()

    @tool
    async def set_step(  # noqa: PLR0917
        name: str,
        state: StepState,
        kind: StepKind = StepKind.OTHER,
        result: str | None = None,
        result_basis: StepResultBasis = StepResultBasis.UNKNOWN,
        supports: list[SupportInput] | None = None,
    ) -> str:
        """Record task-step progress and the text for a completed step.

        A completed step requires result text that fits the event payload limit.
        Later runs reuse that result instead of repeating the completed work.
        """
        if not await _support_inputs_are_current(decisions, supports or []):
            return "A decision support is missing, inactive, or needs review."
        result_seq = None
        if state is StepState.COMPLETED:
            if not result:
                return "A completed step needs its result text."
            event = await record_event_or_flag(
                history,
                task_name,
                run_state,
                EventKind.NOTE,
                name=f"step:{name}",
                payload=result,
            )
            if event is None:
                raise RuntimeError(
                    "Step result could not be recorded; step is unresolved."
                )
            if event.truncated:
                raise RuntimeError("Step result was truncated; step is unresolved.")
            result_seq = event.seq
        try:
            outcome = await history.set_step(
                task_name,
                name,
                state,
                kind=kind,
                result_event_seq=result_seq,
                result_basis=result_basis,
                supports=supports or [],
                fetched_evidence=_current_fetches(run_state),
            )
        except Exception as exc:
            run_state.fail_recording(f"set_step {name}: {exc!r}")
            raise RuntimeError(f"Step {name!r} could not be recorded.") from exc
        if not outcome.recorded:
            run_state.fail_recording(f"set_step {name}: {outcome.error}")
            raise RuntimeError(f"Step {name!r} could not be recorded: {outcome.error}.")
        if state is StepState.IN_PROGRESS:
            run_state.open_steps[name] = kind
        else:
            run_state.open_steps.pop(name, None)
        return outcome.model_dump_json()

    @tool
    async def record_decision(  # noqa: PLR0917
        choice_key: str,
        conclusion: str,
        rationale: str,
        supports: list[SupportInput],
        assumptions: list[str] | None = None,
        open_questions: list[str] | None = None,
    ) -> str:
        """Record a decision with typed source and decision supports."""
        if not await _support_inputs_are_current(decisions, supports):
            return "A decision support is missing, inactive, or needs review."
        fetched = _current_fetches(run_state)
        result = await decisions.record_decision(
            task_name,
            choice_key,
            conclusion,
            rationale,
            supports=supports,
            fetched_evidence=fetched,
            assumptions=assumptions or [],
            open_questions=open_questions or [],
        )
        if not result.recorded:
            run_state.fail_recording(f"record_decision: {result.error}")
        return result.model_dump_json()

    @tool
    async def supersede_decision(  # noqa: PLR0917
        decision_id: str,
        conclusion: str,
        rationale: str,
        explanation: str,
        supports: list[SupportInput],
        assumptions: list[str] | None = None,
        open_questions: list[str] | None = None,
    ) -> str:
        """Replace a decision with a supported conclusion."""
        if not await _support_inputs_are_current(decisions, supports):
            return "A decision support is missing, inactive, or needs review."
        fetched = _current_fetches(run_state)
        try:
            old_id = UUID(decision_id)
        except ValueError:
            return "decision_id must be the id of an existing decision."
        result = await decisions.supersede_decision(
            old_id,
            conclusion,
            rationale,
            explanation=explanation,
            supports=supports,
            fetched_evidence=fetched,
            assumptions=assumptions or [],
            open_questions=open_questions or [],
        )
        if not result.recorded:
            run_state.fail_recording(f"supersede_decision: {result.error}")
        return result.model_dump_json()

    @tool
    async def search_decisions(query: str, limit: int = 20) -> str:
        """Find current decisions in this project that can serve as precedents.

        Excludes decisions that need review or have non-current supports. Use
        list_decisions_for_review to inspect this task's pending decisions.
        """
        if not 1 <= limit <= 20:
            return "Limit must be between 1 and 20."
        found = await decisions.search_decisions(query, limit=limit)
        usable = [
            hit.model_dump(mode="json")
            for hit in found
            if hit.decision.review_state.value == "clear"
            and all(support.current for support in hit.decision.supports)
        ]
        return json.dumps(usable)

    @tool
    async def fetch_event(task_name: str, seq: int) -> str:
        """Read one event by its task name and sequence number."""
        lookup = await history.fetch_event(task_name, seq)
        return lookup.model_dump_json()

    @tool
    async def list_events(task_name: str, after_seq: int = 0, limit: int = 50) -> str:
        """Read one bounded page of task events."""
        if not 1 <= limit <= 50:
            return "Limit must be between 1 and 50."
        page = await history.list_events(task_name, after_seq=after_seq, limit=limit)
        return page.model_dump_json()

    @tool
    async def list_steps(
        state: StepState, after_name: str | None = None, limit: int = 50
    ) -> str:
        """Read one bounded page of steps in a task state."""
        if not 1 <= limit <= 50:
            return "Limit must be between 1 and 50."
        page = await history.list_steps(
            task_name, state, after_name=after_name, limit=limit
        )
        return page.model_dump_json()

    @tool
    async def get_decision(decision_id: str) -> str:
        """Read a decision by its id, including its typed supports."""
        try:
            parsed_id = UUID(decision_id)
        except ValueError:
            return "decision_id must be a UUID."
        return (await decisions.get_decision(parsed_id)).model_dump_json()

    @tool
    async def list_support_history(
        decision_id: str, after_ordinal: int = -1, limit: int = 20
    ) -> str:
        """Read one bounded page of a decision's original and refreshed supports."""
        if not 1 <= limit <= 50:
            return "Limit must be between 1 and 50."
        try:
            parsed_id = UUID(decision_id)
        except ValueError:
            return "decision_id must be a UUID."
        return (
            await decisions.list_support_history(
                parsed_id, after_ordinal=after_ordinal, limit=limit
            )
        ).model_dump_json()

    @tool
    async def list_decisions(include_history: bool = True) -> str:
        """List task decisions, including superseded history by default."""
        page = await decisions.list_decisions(
            task_name, include_history=include_history
        )
        return page.model_dump_json()

    @tool
    async def list_decisions_for_review(limit: int = 20) -> str:
        """List decisions flagged for review without treating them as false."""
        if not 1 <= limit <= 50:
            return "Limit must be between 1 and 50."
        page = await decisions.list_decisions_for_review(
            task_name=task_name, limit=limit
        )
        return page.model_dump_json()

    @tool
    async def reaffirm_decision(
        decision_id: str,
        evidence_ids: list[str],
        explanation: str = "Reaffirmed after current evidence review.",
    ) -> str:
        """Reaffirm a reviewed decision using current fetched documents."""
        try:
            parsed_id = UUID(decision_id)
        except ValueError:
            return "decision_id must be a UUID."
        supports = [DocumentSupportInput(evidence_id=item) for item in evidence_ids]
        fetched = _current_fetches(run_state, evidence_ids)
        outcome = await decisions.reaffirm_decision(
            parsed_id,
            supports,
            fetched_evidence=fetched,
            explanation=explanation,
        )
        if not outcome.recorded:
            run_state.fail_recording(f"reaffirm_decision: {outcome.error}")
        return outcome.model_dump_json()

    @tool
    async def continue_decision_review(limit: int = 20) -> str:
        """Advance queued decision-review propagation by a bounded amount."""
        if not 0 <= limit <= 50:
            return "Limit must be between 0 and 50."
        processed = await decisions.continue_decision_review(limit=limit)
        return json.dumps({"processed": processed})

    return [
        search_evidence_tool,
        fetch_evidence_tool,
        navigate_evidence,
        search_entities,
        explore_relationships_tool,
        search_themes_tool,
        check_citations_tool,
        get_task,
        set_step,
        record_decision,
        supersede_decision,
        search_decisions,
        fetch_event,
        list_events,
        list_steps,
        get_decision,
        list_support_history,
        list_decisions,
        list_decisions_for_review,
        reaffirm_decision,
        continue_decision_review,
    ], run_state


def _current_fetches(
    state: RunState, evidence_ids: Sequence[str] | None = None
) -> list[FetchOutcome]:
    """Return only complete fetches of current document versions."""
    ids = evidence_ids if evidence_ids is not None else state.fetched_ids
    return [
        state.fetches[item]
        for item in ids
        if item in state.fetches
        and state.fetches[item].status is FetchStatus.OK
        and state.fetches[item].status_of_version is not None
        and state.fetches[item].status_of_version.value == "current"
    ]


async def _support_inputs_are_current(
    decisions: DecisionTraces, supports: Sequence[SupportInput]
) -> bool:
    """Reject decision dependencies that are not active and fully current."""
    for support in supports:
        if not isinstance(support, DecisionSupportInput):
            continue
        try:
            decision_id = UUID(support.decision_id)
        except ValueError:
            return False
        lookup = await decisions.get_decision(decision_id)
        decision = lookup.decision
        if (
            decision is None
            or decision.status.value != "active"
            or decision.review_state.value != "clear"
            or any(not item.current for item in decision.supports)
        ):
            return False
    return True
