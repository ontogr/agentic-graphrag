"""Tools for scoped evidence, task progress and decisions.

Tool calls and results are recorded as task events by the middleware, so these
tools only count the budget and record the events they create themselves.
"""

import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from agrag.agents.middleware import RunState, record_event_or_flag
from agrag.common.data_models.decision import DocumentSupportInput
from agrag.common.data_models.evidence import (
    DiscoveryMode,
    FetchOutcome,
    FetchStatus,
)
from agrag.common.data_models.navigation import NavigationRelation
from agrag.common.data_models.task import EventKind, StepKind, StepState
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

    def admit() -> bool:
        """Count one tool call and report whether the budget allows it."""
        state.tool_calls += 1
        state.budget_exhausted |= state.tool_calls >= state.max_tool_calls
        return state.tool_calls <= state.max_tool_calls

    @tool
    async def discover_evidence(
        query: str, mode: str = "hybrid", limit: int = 8
    ) -> str:
        """Find in-scope source passages and return their evidence ids."""
        if not admit():
            return "Tool budget exhausted."
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
            return f"Invalid discovery request: {exc}"
        state.retrieval_failed |= (
            found.status.value not in {"ok", "no_match", "empty_scope"}
            or found.truncated
        )
        return found.model_dump_json()

    @tool
    async def fetch_evidence(evidence_ids: list[str]) -> str:
        """Fetch exact passage text for evidence ids returned by discovery."""
        if not admit():
            return "Tool budget exhausted."
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
        relation: str,
        limit: int = 10,
        max_chars: int = 12_000,
    ) -> str:
        """Read nearby passages in the same document version."""
        if not admit():
            return "Tool budget exhausted."
        try:
            result = await navigate(
                graph_store,
                evidence_id,
                NavigationRelation(relation),
                scope=scope,
                limit=min(limit, 50),
                max_chars=min(max_chars, 20_000),
            )
        except ValueError as exc:
            return f"Invalid navigation request: {exc}"
        state.retrieval_failed |= result.status.value == "failed" or result.truncated
        return result.model_dump_json()

    @tool("find_entities")
    async def search_entities(
        query: str,
        labels: list[str] | None = None,
        mode: str = "hybrid",
        limit: int = 10,
    ) -> str:
        """Find entities whose names match the query and show source support."""
        if not admit():
            return "Tool budget exhausted."
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
            return f"Invalid entity search request: {exc}"
        state.retrieval_failed |= (
            result.status.value not in {"ok", "no_match", "empty_scope"}
            or result.truncated
        )
        return result.model_dump_json()

    @tool
    async def explore(
        entity_id: str,
        depth: int = 1,
        relation_types: list[str] | None = None,
        max_nodes: int = 25,
        max_edges: int = 50,
    ) -> str:
        """Explore supported relations around an entity within fixed bounds."""
        if not admit():
            return "Tool budget exhausted."
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
            return f"Invalid exploration request: {exc}"
        state.retrieval_failed |= result.status.value == "failed" or bool(
            result.truncated_by
        )
        return result.model_dump_json()

    @tool("check_citations")
    async def check_citations_tool(evidence_ids: list[str]) -> str:
        """Check that evidence ids were fetched in the permitted scope."""
        if not admit():
            return "Tool budget exhausted."
        checked = await check_citations(evidence_ids, state.fetched_ids, scope=scope)
        return json.dumps([c.model_dump(mode="json") for c in checked])

    @tool
    async def get_task() -> str:
        """Read this task's bounded resume view."""
        if not admit():
            return "Tool budget exhausted."
        lookup = await memory.get_task(task_name)
        return lookup.model_dump_json()

    @tool
    async def set_step(
        name: str,
        state_name: str,
        kind: str = "other",
        result: str | None = None,
    ) -> str:
        """Record progress for a named task step.

        A completed step needs ``result``, the text that later runs reuse
        instead of repeating the step. Use ``unknown`` when the outcome of an
        interrupted step is not known.
        """
        if not admit():
            return "Tool budget exhausted."
        try:
            step_state = StepState(state_name)
            step_kind = StepKind(kind)
        except ValueError as exc:
            return f"Invalid step: {exc}"
        result_seq = None
        if step_state is StepState.COMPLETED:
            if not result:
                return "A completed step needs its result text."
            stored = await record_event_or_flag(
                memory,
                task_name,
                state,
                EventKind.NOTE,
                name=f"step:{name}",
                payload=result,
            )
            if stored is None:
                return "The step result was not recorded, so the step is not completed."
            result_seq = stored.seq
        if step_state is StepState.IN_PROGRESS:
            state.open_steps[name] = step_kind
        else:
            state.open_steps.pop(name, None)
        outcome = await memory.set_step(
            task_name,
            name,
            step_state,
            kind=step_kind,
            result_event_seq=result_seq,
        )
        return outcome.model_dump_json()

    @tool
    async def record_decision(
        choice_key: str,
        conclusion: str,
        rationale: str,
        evidence_ids: list[str],
    ) -> str:
        """Record a decision supported by evidence fetched in this run."""
        if not admit():
            return "Tool budget exhausted."
        supports = [DocumentSupportInput(evidence_id=item) for item in evidence_ids]
        fetched = [
            state.fetches[item]
            for item in evidence_ids
            if item in state.fetches and state.fetches[item].status is FetchStatus.OK
        ]
        outcome = await decisions.record_decision(
            task_name,
            choice_key,
            conclusion,
            rationale,
            supports=supports,
            fetched_evidence=fetched,
        )
        if not outcome.recorded:
            state.fail_recording(f"record_decision: {outcome.error}")
        return outcome.model_dump_json()

    @tool
    async def supersede_decision(
        decision_id: str,
        conclusion: str,
        rationale: str,
        explanation: str,
        evidence_ids: list[str],
    ) -> str:
        """Replace a decision with a supported conclusion."""
        if not admit():
            return "Tool budget exhausted."
        supports = [DocumentSupportInput(evidence_id=item) for item in evidence_ids]
        fetched = [
            state.fetches[item]
            for item in evidence_ids
            if item in state.fetches and state.fetches[item].status is FetchStatus.OK
        ]
        try:
            old_id = UUID(decision_id)
        except ValueError:
            return "decision_id must be the id of an existing decision."
        outcome = await decisions.supersede_decision(
            old_id,
            conclusion,
            rationale,
            explanation=explanation,
            supports=supports,
            fetched_evidence=fetched,
        )
        if not outcome.recorded:
            state.fail_recording(f"supersede_decision: {outcome.error}")
        return outcome.model_dump_json()

    @tool
    async def search_decisions(query: str, limit: int = 20) -> str:
        """Find decisions in this project that may be useful as precedents."""
        if not admit():
            return "Tool budget exhausted."
        if not 1 <= limit <= 20:
            return "Limit must be between 1 and 20."
        found = await decisions.search_decisions(query, limit=limit)
        return json.dumps([item.model_dump(mode="json") for item in found])

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
    ], state
