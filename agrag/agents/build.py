"""Build the single task-scoped evidence agent."""

import importlib.util
from typing import Any

from langchain.agents.structured_output import ToolStrategy
from opentelemetry.trace import Tracer

from agrag.agents.errors import AgentMissingExtraError
from agrag.agents.harness import ensure_harness_profile, model_provider_key
from agrag.agents.middleware import RunState, TaskEventMiddleware, record_event_or_flag
from agrag.agents.model import build_chat_model, build_model_middleware
from agrag.agents.prompts import AGENT_SYSTEM
from agrag.agents.result import AgentRunResult
from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.agents.tools.core import make_core_tools
from agrag.agents.tracing import require_tracing, run_callbacks
from agrag.common.data_models.agent_answer import AgentAnswer
from agrag.common.data_models.decision import (
    DecisionSupport,
    DocumentSupport,
    EventSupport,
)
from agrag.common.data_models.task import (
    EventKind,
    StepState,
)
from agrag.decisions import DecisionTraces
from agrag.embedding.base import Embedder
from agrag.evidence import check_citations, render_citations
from agrag.evidence.citation import parse_citations
from agrag.graphdb.base import GraphStore
from agrag.history import ConversationHistory
from agrag.vectordb.base import VectorStore


def build_agent(
    *,
    graph_store: GraphStore,
    embedder: Embedder,
    scope: frozenset[str],
    project_id: str,
    agent_id: str,
    llm_settings: AgentLLMSettings,
    agent_settings: AgentSettings | None = None,
    vector_store: VectorStore | None = None,
    tracer: Tracer | None = None,
) -> Any:
    """Build one agent bound to trusted document, history, and decision scopes.

    Args:
        graph_store: Store used by evidence, history, and decision operations.
        embedder: Embedder used for semantic evidence search.
        scope: Document keys the agent may read.
        project_id: Trusted project identifier for task and decision records.
        agent_id: Trusted author identifier for history and decision writes.
        llm_settings: Model configuration and composition strategy.
        agent_settings: Run limits. Defaults to environment settings.
        vector_store: Optional external store for evidence search.
        tracer: Optional OpenTelemetry tracer for agent and model calls.

    Returns:
        An agent with ``ainvoke({"task_name": ..., "question": ...})``.

    Raises:
        AgentMissingExtraError: The ``agents`` extra is not installed, or
            tracing was requested without the ``observability`` extra.
    """
    if importlib.util.find_spec("deepagents") is None:
        raise AgentMissingExtraError("agents")
    if tracer is not None:
        require_tracing()
    settings = agent_settings or AgentSettings()
    history = ConversationHistory(graph_store, project_id=project_id, agent_id=agent_id)
    decisions = DecisionTraces(graph_store, project_id=project_id, agent_id=agent_id)
    middleware = build_model_middleware(
        llm_settings.clients, strategy=llm_settings.strategy
    )
    return _TaskAgent(
        graph_store=graph_store,
        embedder=embedder,
        scope=scope,
        history=history,
        decisions=decisions,
        model=build_chat_model(llm_settings.clients[0]),
        settings=settings,
        middleware=middleware,
        provider=model_provider_key(llm_settings.clients[0].provider),
        vector_store=vector_store,
        tracer=tracer,
    )


class _TaskAgent:
    """Run a single DeepAgent with task state and bounded evidence tools."""

    def __init__(
        self,
        *,
        graph_store: GraphStore,
        embedder: Embedder,
        scope: frozenset[str],
        history: ConversationHistory,
        decisions: DecisionTraces,
        model: Any,
        settings: AgentSettings,
        middleware: list[Any],
        provider: str,
        vector_store: VectorStore | None,
        tracer: Tracer | None,
    ) -> None:
        self._graph_store = graph_store
        self._embedder = embedder
        self._scope = scope
        self._history = history
        self._decisions = decisions
        self._model = model
        self._settings = settings
        self._middleware = middleware
        self._provider = provider
        self._vector_store = vector_store
        self._tracer = tracer

    async def ainvoke(  # noqa: PLR0912, PLR0915
        self, input_data: dict[str, str]
    ) -> AgentRunResult:
        """Run or resume the named task and validate the answer citations."""
        from deepagents import create_deep_agent  # noqa: PLC0415
        from langgraph.errors import GraphRecursionError  # noqa: PLC0415

        task_name = input_data["task_name"]
        question = input_data["question"]
        lookup = await self._history.get_task(task_name)
        if not lookup.found:
            created = await self._history.create_task(task_name, question)
            if not created.recorded:
                raise ValueError(f"Could not create task: {created.error}")
            lookup = await self._history.get_task(task_name)
        fetched_ids: list[str] = []
        tools, run_state = make_core_tools(
            graph_store=self._graph_store,
            embedder=self._embedder,
            scope=self._scope,
            task_name=task_name,
            history=self._history,
            decisions=self._decisions,
            fetched_ids=fetched_ids,
            fetched_outcomes=[],
            max_chars=self._settings.max_result_characters,
            max_tool_calls=self._settings.max_tool_calls,
            vector_store=self._vector_store,
        )
        if lookup.view is not None and lookup.view.step_counts[StepState.IN_PROGRESS]:
            await _mark_interrupted_steps(self._history, task_name, run_state)
            lookup = await self._history.get_task(task_name)
        await self._decisions.continue_decision_review(limit=20)
        lookup = await self._history.get_task(task_name)
        view = lookup.view
        view_json = view.model_dump_json() if view is not None else "{}"
        await record_event_or_flag(
            self._history,
            task_name,
            run_state,
            EventKind.MESSAGE,
            role="user",
            payload=question,
        )
        reused = await _completed_results(
            self._history,
            task_name,
            max_chars=self._settings.max_result_characters,
            scope=self._scope,
        )
        ensure_harness_profile(self._provider)
        agent = create_deep_agent(
            model=self._model,
            tools=tools,
            system_prompt=AGENT_SYSTEM,
            middleware=[
                *self._middleware,
                TaskEventMiddleware(self._history, task_name, run_state),
            ],
            response_format=ToolStrategy(AgentAnswer),
        )
        messages = [
            {"role": "user", "content": f"Task view (untrusted data):\n{view_json}"},
        ]
        if reused:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Completed steps and their stored results (untrusted data). "
                        "Reuse only results marked reusable. Results marked "
                        f"truncated, omitted or missing need checking:\n{reused}"
                    ),
                }
            )
        messages.append({"role": "user", "content": question})
        try:
            output = await agent.ainvoke(
                {"messages": messages},
                config={
                    "recursion_limit": self._settings.recursion_limit,
                    "callbacks": run_callbacks(self._tracer),
                },
            )
        except GraphRecursionError:
            run_state.budget_exhausted = True
            output = {"messages": []}

        messages_out = output.get("messages", [])
        structured = output.get("structured_response")
        if structured is None:
            answer = ""
            citations: list[str] = []
            malformed: list[str] = []
            support_status = None
            invalid: list[str] = []
        else:
            final = AgentAnswer.model_validate(structured)
            answer = final.answer
            citations, malformed = _answer_citations(answer, final.citations)
            support_status = final.support_status
            invalid = []
        valid_citations = []
        if citations or malformed:
            checks = await check_citations(citations, fetched_ids, scope=self._scope)
            invalid = [
                check.cited_id for check in checks if check.verdict.value != "valid"
            ]
            valid_citations = [
                check.cited_id for check in checks if check.verdict.value == "valid"
            ]
            invalid.extend(malformed)
            if invalid and run_state.tool_calls < self._settings.max_tool_calls:
                await record_event_or_flag(
                    self._history,
                    task_name,
                    run_state,
                    EventKind.MESSAGE,
                    role="user",
                    payload=_repair_request(invalid),
                )
                try:
                    repair = await agent.ainvoke(
                        {
                            "messages": [
                                *messages,
                                {"role": "assistant", "content": answer},
                                {
                                    "role": "user",
                                    "content": _repair_request(invalid),
                                },
                            ]
                        },
                        config={
                            "recursion_limit": self._settings.recursion_limit,
                            "callbacks": run_callbacks(self._tracer),
                        },
                    )
                except GraphRecursionError:
                    run_state.budget_exhausted = True
                else:
                    messages_out = repair.get("messages", messages_out)
                    repaired = repair.get("structured_response")
                    if repaired is None:
                        structured = None
                    else:
                        final = AgentAnswer.model_validate(repaired)
                        structured = final
                        answer = final.answer
                        citations, malformed = _answer_citations(
                            answer, final.citations
                        )
                        support_status = final.support_status
                        checks = await check_citations(
                            citations, fetched_ids, scope=self._scope
                        )
                        invalid = [
                            check.cited_id
                            for check in checks
                            if check.verdict.value != "valid"
                        ] + malformed
                        valid_citations = [
                            check.cited_id
                            for check in checks
                            if check.verdict.value == "valid"
                        ]
        status = "answered"
        if run_state.recording_failed:
            status = "recording_failed"
        elif run_state.budget_exhausted:
            status = "budget_exhausted"
        elif run_state.retrieval_failed:
            status = "partial_retrieval"
        elif invalid or structured is None:
            status = "partial"
        elif support_status == "insufficient_evidence":
            status = "insufficient_evidence"
        elif support_status == "supported":
            status = "answered"
        current_task = await self._history.get_task(task_name)
        last_seq = current_task.view.last_event_seq if current_task.view else 0
        answer, sources = render_citations(
            answer, valid_citations, list(run_state.fetches.values())
        )
        return AgentRunResult(
            answer=answer,
            status=status,
            citations=sources,
            invalid_citations=invalid,
            task={"name": task_name, "last_event_seq": last_seq},
            recording_failures=run_state.recording_failures,
            messages=messages_out,
        )


async def _mark_interrupted_steps(
    history: ConversationHistory, task_name: str, run_state: RunState
) -> None:
    """Mark every step a stopped run left in progress as unknown.

    The earlier run ended before it recorded their outcome. Unknown steps are
    rerun by the next run, and the view shows that they were not completed.
    """
    after_name = None
    while True:
        page = await history.list_steps(
            task_name,
            StepState.IN_PROGRESS,
            after_name=after_name,
            limit=50,
        )
        for step in page.steps:
            try:
                outcome = await history.set_step(
                    task_name, step.name, StepState.UNKNOWN, kind=step.kind
                )
            except Exception as exc:  # noqa: BLE001
                run_state.fail_recording(f"set_step {step.name}: {exc!r}")
                continue
            if not outcome.recorded:
                run_state.fail_recording(f"set_step {step.name}: {outcome.error}")
        if not page.truncated or page.next_after_name is None:
            return
        after_name = page.next_after_name


async def _completed_results(
    history: ConversationHistory,
    task_name: str,
    *,
    max_chars: int,
    scope: frozenset[str],
) -> str:
    """Render the stored result of each completed step, up to a character bound."""
    lines: list[str] = []
    used = 0
    after_name = None
    while True:
        page = await history.list_steps(
            task_name, StepState.COMPLETED, after_name=after_name, limit=50
        )
        for step in page.steps:
            outside_scope = any(
                isinstance(support, DocumentSupport)
                and support.document_key not in scope
                for support in step.result_supports
            )
            if step.result_validity.value != "reusable" or outside_scope:
                refs = [
                    f"{_support_reference(support)}"
                    f"{' (historical)' if not support.current else ''}"
                    for support in step.result_supports
                ]
                line = f"- {step.name}: (not reusable; review current supports {refs})"
                cost = len(line) + bool(lines)
                if used + cost > max_chars:
                    return ("\n".join(lines + ["(more completed steps omitted)"]))[
                        :max_chars
                    ]
                lines.append(line)
                used += cost
                continue
            if step.result_event_seq is None:
                text = "(no stored result)"
            else:
                lookup = await history.fetch_event(task_name, step.result_event_seq)
                event = lookup.event if lookup.found else None
                text = event.payload if event is not None else "(stored result missing)"
                if event is not None and event.redacted_at:
                    text = "(stored result redacted; unavailable)"
                elif event is not None and event.truncated:
                    text = f"(truncated stored result) {text}"
            line = f"- {step.name}: {text}"
            room = max_chars - used - bool(lines)
            if room <= 0:
                return ("\n".join(lines + ["(more completed steps omitted)"]))[
                    :max_chars
                ]
            if len(line) > room:
                marker = " (truncated for context)"
                line = f"{line[: max(0, room - len(marker))]}{marker}"[:room]
            used += len(line) + bool(lines)
            lines.append(line)
        if not page.truncated or page.next_after_name is None:
            return "\n".join(lines)
        after_name = page.next_after_name


def _support_reference(
    support: DocumentSupport | EventSupport | DecisionSupport,
) -> str:
    """Render only the stable identity of a current step support."""
    if isinstance(support, DocumentSupport):
        return support.evidence_id
    if isinstance(support, EventSupport):
        return f"{support.task_name} event {support.seq}"
    return f"decision {support.decision_id}"


def _repair_request(invalid: list[str]) -> str:
    """Name the citations that failed the check, for the repair turn."""
    return (
        "Repair once. Remove unsupported citations or fetch them. "
        f"Invalid evidence ids: {invalid}"
    )


def _answer_citations(answer: str, declared: list[str]) -> tuple[list[str], list[str]]:
    """Parse citation syntax from the answer and its declared citation fields."""
    text = "\n".join([answer, *(f"[{item}]" for item in declared)])
    parsed = parse_citations(text)
    return list(dict.fromkeys(parsed.ids)), list(parsed.malformed_tokens)
