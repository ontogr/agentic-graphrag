"""Tools for scoped evidence, task progress and decisions."""

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
    DiscoveryMode,
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
from agrag.embedding.base import Embedder
from agrag.evidence import (
    check_citations,
    discover,
    fetch,
    find_entities,
    navigate,
)
from agrag.evidence import (
    explore as explore_evidence,
)
from agrag.graphdb.base import GraphStore
from agrag.memory import DecisionMemory, TaskMemory


def make_core_tools(  # noqa: PLR0915
    *,
    graph_store: GraphStore,
    embedder: Embedder,
    scope: frozenset[str],
    task_name: str,
    memory: TaskMemory,
    decisions: DecisionMemory,
    fetched_ids: list[str],
    fetched_outcomes: Sequence[FetchOutcome],
    max_chars: int,
    max_tool_calls: int,
) -> tuple[list[Any], RunState]:
    """Bind evidence and memory tools to a single task and trusted scope."""
    from langchain_core.tools import tool  # noqa: PLC0415

    state = RunState(
        max_tool_calls=max_tool_calls,
        fetched_ids=fetched_ids,
        fetches={item.evidence_id: item for item in fetched_outcomes},
    )

    @tool
    async def discover_evidence(
        query: str,
        mode: str = "hybrid",
        limit: int = 8,
        callbacks: Any = None,
    ) -> str:
        """Find in-scope source passages and return their evidence ids."""
        with tool_span_context(callbacks):
            if not 1 <= limit <= 50:
                return "Limit must be between 1 and 50."
            try:
                found = await discover(
                    graph_store,
                    embedder,
                    query,
                    mode=DiscoveryMode(mode),
                    limit=limit,
                    scope=scope,
                )
            except (ValueError, KeyError) as exc:
                result = f"Invalid discovery request: {exc}"
            else:
                state.retrieval_failed |= (
                    found.status.value not in {"ok", "no_match", "empty_scope"}
                    or found.truncated
                )
                result = found.model_dump_json()
            return result

    @tool
    async def fetch_evidence(
        evidence_ids: list[str],
        callbacks: Any = None,
    ) -> str:
        """Fetch exact passage text for evidence ids returned by discovery."""
        with tool_span_context(callbacks):
            if len(evidence_ids) > 20:
                return "Fetch at most 20 evidence ids per call."
            outcomes = await fetch(
                graph_store, evidence_ids, scope=scope, max_chars=max_chars
            )
            for outcome in outcomes:
                state.fetches[outcome.evidence_id] = outcome
                if outcome.status is FetchStatus.OK:
                    state.fetched_ids.append(outcome.evidence_id)
                elif outcome.status in {
                    FetchStatus.FAILED,
                    FetchStatus.TRUNCATED,
                    FetchStatus.PARTIAL,
                }:
                    state.retrieval_failed = True
            valid_ids = [o.evidence_id for o in outcomes if o.status is FetchStatus.OK]
            if valid_ids:
                await record_event_or_flag(
                    memory,
                    task_name,
                    state,
                    EventKind.NOTE,
                    name="fetched_evidence",
                    payload=json.dumps(valid_ids),
                )
            return json.dumps([o.model_dump(mode="json") for o in outcomes])

    @tool("navigate")
    async def navigate_evidence(
        evidence_id: str,
        relation: NavigationRelation,
        limit: int = 10,
        max_chars: int = 12_000,
        callbacks: Any = None,
    ) -> str:
        """Read nearby passages in the same document version."""
        with tool_span_context(callbacks):
            try:
                result = await navigate(
                    graph_store,
                    evidence_id,
                    relation,
                    scope=scope,
                    limit=min(limit, 50),
                    max_chars=min(max_chars, 20_000),
                )
            except ValueError as exc:
                output = f"Invalid navigation request: {exc}"
            else:
                state.retrieval_failed |= (
                    result.status.value == "failed" or result.truncated
                )
                output = result.model_dump_json()
            return output

    @tool("find_entities")
    async def search_entities(
        query: str,
        labels: list[str] | None = None,
        mode: str = "hybrid",
        limit: int = 10,
        callbacks: Any = None,
    ) -> str:
        """Find entities whose names match the query and show source support."""
        with tool_span_context(callbacks):
            if not 1 <= limit <= 50:
                return "Limit must be between 1 and 50."
            try:
                result = await find_entities(
                    graph_store,
                    embedder,
                    query,
                    scope=scope,
                    labels=labels,
                    mode=DiscoveryMode(mode),
                    limit=limit,
                )
            except ValueError as exc:
                output = f"Invalid entity search request: {exc}"
            else:
                state.retrieval_failed |= (
                    result.status.value not in {"ok", "no_match", "empty_scope"}
                    or result.truncated
                )
                output = result.model_dump_json()
            return output

    @tool
    async def explore(
        entity_id: str,
        depth: int = 1,
        relation_types: list[str] | None = None,
        max_nodes: int = 25,
        max_edges: int = 50,
        *,
        callbacks: Any = None,
    ) -> str:
        """Explore supported relations around an entity within fixed bounds."""
        with tool_span_context(callbacks):
            try:
                result = await explore_evidence(
                    graph_store,
                    entity_id,
                    scope=scope,
                    relation_types=relation_types,
                    depth=min(depth, 2),
                    max_nodes=min(max_nodes, 200),
                    max_edges=min(max_edges, 200),
                )
            except ValueError as exc:
                output = f"Invalid exploration request: {exc}"
            else:
                state.retrieval_failed |= result.status.value == "failed" or bool(
                    result.truncated_by
                )
                output = result.model_dump_json()
            return output

    @tool("check_citations")
    async def check_citations_tool(
        evidence_ids: list[str],
        callbacks: Any = None,
    ) -> str:
        """Check that evidence ids were fetched in the permitted scope."""
        with tool_span_context(callbacks):
            checked = await check_citations(
                evidence_ids, state.fetched_ids, scope=scope
            )
            return json.dumps([c.model_dump(mode="json") for c in checked])

    @tool
    async def get_task() -> str:
        """Read this task's bounded resume view."""
        lookup = await memory.get_task(task_name)
        return lookup.model_dump_json()

    @tool
    async def set_step(  # noqa: PLR0917
        name: str,
        state_name: str,
        kind: str = "other",
        result: str | None = None,
        result_basis: str = "unknown",
        supports: list[SupportInput] | None = None,
    ) -> str:
        """Record task-step progress and the text for a completed step.

        A completed step requires result text that fits the event payload limit.
        Later runs reuse that result instead of repeating the completed work.
        """
        try:
            step_state = StepState(state_name)
            step_kind = StepKind(kind)
            basis = StepResultBasis(result_basis)
        except ValueError as exc:
            return f"Invalid step state: {exc}"
        if not await _support_inputs_are_current(decisions, supports or []):
            return "A decision support is missing, inactive, or needs review."
        result_seq = None
        if step_state is StepState.COMPLETED:
            if not result:
                return "A completed step needs its result text."
            event = await record_event_or_flag(
                memory,
                task_name,
                state,
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
            outcome = await memory.set_step(
                task_name,
                name,
                step_state,
                kind=step_kind,
                result_event_seq=result_seq,
                result_basis=basis,
                supports=supports or [],
                fetched_evidence=_current_fetches(state),
            )
        except Exception as exc:
            state.fail_recording(f"set_step {name}: {exc!r}")
            raise RuntimeError(f"Step {name!r} could not be recorded.") from exc
        if not outcome.recorded:
            state.fail_recording(f"set_step {name}: {outcome.error}")
            raise RuntimeError(f"Step {name!r} could not be recorded: {outcome.error}.")
        if step_state is StepState.IN_PROGRESS:
            state.open_steps[name] = step_kind
        else:
            state.open_steps.pop(name, None)
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
        fetched = _current_fetches(state)
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
            state.fail_recording(f"record_decision: {result.error}")
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
        fetched = _current_fetches(state)
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
            state.fail_recording(f"supersede_decision: {result.error}")
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
    async def get_event(event_task_name: str, seq: int) -> str:
        """Read one event by its task name and sequence number."""
        lookup = await memory.get_event(event_task_name, seq)
        return lookup.model_dump_json()

    @tool
    async def list_events(
        event_task_name: str, after_seq: int = 0, limit: int = 50
    ) -> str:
        """Read one bounded page of task events."""
        if not 1 <= limit <= 50:
            return "Limit must be between 1 and 50."
        page = await memory.list_events(
            event_task_name, after_seq=after_seq, limit=limit
        )
        return page.model_dump_json()

    @tool
    async def list_steps(
        state_name: str, after_name: str | None = None, limit: int = 50
    ) -> str:
        """Read one bounded page of steps in a task state."""
        if not 1 <= limit <= 50:
            return "Limit must be between 1 and 50."
        try:
            step_state = StepState(state_name)
        except ValueError as exc:
            return f"Invalid step state: {exc}"
        page = await memory.list_steps_page(
            task_name, step_state, after_name=after_name, limit=limit
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
        page = await decisions.list_review(task_name=task_name, limit=limit)
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
        fetched = _current_fetches(state, evidence_ids)
        outcome = await decisions.reaffirm_decision(
            parsed_id,
            supports,
            fetched_evidence=fetched,
            explanation=explanation,
        )
        if not outcome.recorded:
            state.fail_recording(f"reaffirm_decision: {outcome.error}")
        return outcome.model_dump_json()

    @tool
    async def continue_decision_review(limit: int = 20) -> str:
        """Advance queued decision-review propagation by a bounded amount."""
        if not 0 <= limit <= 50:
            return "Limit must be between 0 and 50."
        processed = await decisions.continue_review_propagation(limit=limit)
        return json.dumps({"processed": processed})

    return [
        discover_evidence,
        fetch_evidence,
        navigate_evidence,
        search_entities,
        explore,
        check_citations_tool,
        get_task,
        set_step,
        record_decision,
        supersede_decision,
        search_decisions,
        get_event,
        list_events,
        list_steps,
        get_decision,
        list_support_history,
        list_decisions,
        list_decisions_for_review,
        reaffirm_decision,
        continue_decision_review,
    ], state


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
    decisions: DecisionMemory, supports: Sequence[SupportInput]
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
