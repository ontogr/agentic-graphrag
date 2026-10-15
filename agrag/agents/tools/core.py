"""Tools for scoped evidence, task progress and decisions."""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from agrag.agents.tracing import tool_span_context
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


@dataclass
class RunState:
    """Mutable facts accumulated by tools during one agent run."""

    max_tool_calls: int
    tool_calls: int = 0
    budget_exhausted: bool = False
    recording_failed: bool = False
    retrieval_failed: bool = False
    fetched_ids: list[str] = field(default_factory=list)
    fetches: dict[str, Any] = field(default_factory=dict)


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

    async def begin(name: str, arguments: dict[str, Any]) -> bool:
        state.tool_calls += 1
        call = await memory.record_event(
            task_name,
            EventKind.TOOL_CALL,
            name=name,
            payload=json.dumps(arguments, default=str),
        )
        state.recording_failed |= not call.recorded
        allowed = state.tool_calls <= state.max_tool_calls
        state.budget_exhausted |= state.tool_calls >= state.max_tool_calls
        return allowed

    async def end(name: str, result: str) -> str:
        recorded = await memory.record_event(
            task_name,
            EventKind.TOOL_RESULT,
            name=name,
            payload=result,
        )
        state.recording_failed |= not recorded.recorded
        return result

    @tool
    async def discover_evidence(
        query: str,
        mode: str = "hybrid",
        limit: int = 8,
        callbacks: Any = None,
    ) -> str:
        """Find in-scope source passages and return their evidence ids."""
        with tool_span_context(callbacks):
            args = {"query": query, "mode": mode, "limit": limit}
            if not await begin("discover_evidence", args):
                return await end("discover_evidence", "Tool budget exhausted.")
            if not 1 <= limit <= 50:
                return await end("discover_evidence", "Limit must be between 1 and 50.")
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
            return await end("discover_evidence", result)

    @tool
    async def fetch_evidence(
        evidence_ids: list[str],
        callbacks: Any = None,
    ) -> str:
        """Fetch exact passage text for evidence ids returned by discovery."""
        with tool_span_context(callbacks):
            args = {"evidence_ids": evidence_ids}
            if not await begin("fetch_evidence", args):
                return await end("fetch_evidence", "Tool budget exhausted.")
            if len(evidence_ids) > 20:
                return await end(
                    "fetch_evidence", "Fetch at most 20 evidence ids per call."
                )
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
                stored = await memory.record_event(
                    task_name,
                    EventKind.NOTE,
                    name="fetched_evidence",
                    payload=json.dumps(valid_ids),
                )
                state.recording_failed |= not stored.recorded
            return await end(
                "fetch_evidence",
                json.dumps([o.model_dump(mode="json") for o in outcomes]),
            )

    @tool("navigate")
    async def navigate_evidence(
        evidence_id: str,
        relation: str,
        limit: int = 10,
        max_chars: int = 12_000,
        callbacks: Any = None,
    ) -> str:
        """Read nearby passages in the same document version."""
        with tool_span_context(callbacks):
            args = {
                "evidence_id": evidence_id,
                "relation": relation,
                "limit": limit,
                "max_chars": max_chars,
            }
            if not await begin("navigate", args):
                return await end("navigate", "Tool budget exhausted.")
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
                output = f"Invalid navigation request: {exc}"
            else:
                state.retrieval_failed |= (
                    result.status.value == "failed" or result.truncated
                )
                output = result.model_dump_json()
            return await end("navigate", output)

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
            args = {"query": query, "labels": labels, "mode": mode, "limit": limit}
            if not await begin("find_entities", args):
                return await end("find_entities", "Tool budget exhausted.")
            if not 1 <= limit <= 50:
                return await end("find_entities", "Limit must be between 1 and 50.")
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
            return await end("find_entities", output)

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
            args = {
                "entity_id": entity_id,
                "depth": depth,
                "relation_types": relation_types,
                "max_nodes": max_nodes,
                "max_edges": max_edges,
            }
            if not await begin("explore", args):
                return await end("explore", "Tool budget exhausted.")
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
            return await end("explore", output)

    @tool("check_citations")
    async def check_citations_tool(
        evidence_ids: list[str],
        callbacks: Any = None,
    ) -> str:
        """Check that evidence ids were fetched in the permitted scope."""
        with tool_span_context(callbacks):
            args = {"evidence_ids": evidence_ids}
            if not await begin("check_citations", args):
                return await end("check_citations", "Tool budget exhausted.")
            checked = await check_citations(
                evidence_ids, state.fetched_ids, scope=scope
            )
            return await end(
                "check_citations",
                json.dumps([c.model_dump(mode="json") for c in checked]),
            )

    @tool
    async def get_task() -> str:
        """Read this task's bounded resume view."""
        if not await begin("get_task", {}):
            return await end("get_task", "Tool budget exhausted.")
        lookup = await memory.get_task(task_name)
        return await end("get_task", lookup.model_dump_json())

    @tool
    async def set_step(name: str, state_name: str, kind: str = "other") -> str:
        """Record progress for a named task step."""
        args = {"name": name, "state": state_name, "kind": kind}
        if not await begin("set_step", args):
            return await end("set_step", "Tool budget exhausted.")
        try:
            result = await memory.set_step(
                task_name,
                name,
                StepState(state_name),
                kind=StepKind(kind),
            )
        except ValueError as exc:
            output = f"Invalid step state: {exc}"
        else:
            output = result.model_dump_json()
        return await end("set_step", output)

    @tool
    async def record_decision(
        choice_key: str,
        conclusion: str,
        rationale: str,
        evidence_ids: list[str],
    ) -> str:
        """Record a decision supported by evidence fetched in this run."""
        args = locals().copy()
        if not await begin("record_decision", args):
            return await end("record_decision", "Tool budget exhausted.")
        supports = [DocumentSupportInput(evidence_id=item) for item in evidence_ids]
        fetched = [
            state.fetches[item]
            for item in evidence_ids
            if item in state.fetches and state.fetches[item].status is FetchStatus.OK
        ]
        result = await decisions.record_decision(
            task_name,
            choice_key,
            conclusion,
            rationale,
            supports=supports,
            fetched_evidence=fetched,
        )
        state.recording_failed |= not result.recorded
        return await end("record_decision", result.model_dump_json())

    @tool
    async def supersede_decision(
        decision_id: str,
        conclusion: str,
        rationale: str,
        explanation: str,
        evidence_ids: list[str],
    ) -> str:
        """Replace a decision with a supported conclusion."""
        args = locals().copy()
        if not await begin("supersede_decision", args):
            return await end("supersede_decision", "Tool budget exhausted.")
        supports = [DocumentSupportInput(evidence_id=item) for item in evidence_ids]
        fetched = [
            state.fetches[item]
            for item in evidence_ids
            if item in state.fetches and state.fetches[item].status is FetchStatus.OK
        ]
        result = await decisions.supersede_decision(
            UUID(decision_id),
            conclusion,
            rationale,
            explanation=explanation,
            supports=supports,
            fetched_evidence=fetched,
        )
        state.recording_failed |= not result.recorded
        return await end("supersede_decision", result.model_dump_json())

    @tool
    async def search_decisions(query: str, limit: int = 20) -> str:
        """Find decisions in this project that may be useful as precedents."""
        if not await begin("search_decisions", {"query": query, "limit": limit}):
            return await end("search_decisions", "Tool budget exhausted.")
        if not 1 <= limit <= 20:
            return await end("search_decisions", "Limit must be between 1 and 20.")
        found = await decisions.search_decisions(query, limit=limit)
        return await end(
            "search_decisions",
            json.dumps([item.model_dump(mode="json") for item in found]),
        )

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
