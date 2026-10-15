"""Build the single task-scoped evidence agent."""

import importlib.util
import json
from collections.abc import Sequence
from typing import Any

from opentelemetry.trace import Tracer

from agrag.agents.errors import AgentMissingExtraError
from agrag.agents.harness import ensure_harness_profile, model_provider_key
from agrag.agents.middleware import TaskEventMiddleware, record_event_or_flag
from agrag.agents.model import build_chat_model, build_model_middleware
from agrag.agents.prompts import AGENT_SYSTEM
from agrag.agents.result import AgentRunResult
from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.agents.tools.core import make_core_tools
from agrag.agents.tracing import require_tracing, run_callbacks
from agrag.common.data_models.task import (
    Event,
    EventKind,
    StepState,
    StepSummary,
    TaskView,
)
from agrag.embedding.base import Embedder
from agrag.evidence import check_citations, fetch
from agrag.graphdb.base import GraphStore
from agrag.memory import DecisionMemory, TaskMemory


def build_agent(
    *,
    graph_store: GraphStore,
    embedder: Embedder,
    scope: frozenset[str],
    project_id: str,
    agent_id: str,
    llm_settings: AgentLLMSettings,
    agent_settings: AgentSettings | None = None,
    tracer: Tracer | None = None,
) -> Any:
    """Build one agent bound to trusted document and memory scopes.

    Args:
        graph_store: Store used by evidence and memory operations.
        embedder: Embedder used for semantic evidence discovery.
        scope: Document keys the agent may read.
        project_id: Trusted project identifier for task and decision memory.
        agent_id: Trusted author identifier for memory writes.
        llm_settings: Model configuration and composition strategy.
        agent_settings: Run limits. Defaults to environment settings.
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
    memory = TaskMemory(graph_store, project_id=project_id, agent_id=agent_id)
    decisions = DecisionMemory(graph_store, project_id=project_id, agent_id=agent_id)
    middleware = build_model_middleware(
        llm_settings.clients, strategy=llm_settings.strategy
    )
    return _TaskAgent(
        graph_store=graph_store,
        embedder=embedder,
        scope=scope,
        memory=memory,
        decisions=decisions,
        model=build_chat_model(llm_settings.clients[0]),
        settings=settings,
        middleware=middleware,
        provider=model_provider_key(llm_settings.clients[0].provider),
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
        memory: TaskMemory,
        decisions: DecisionMemory,
        model: Any,
        settings: AgentSettings,
        middleware: list[Any],
        provider: str,
        tracer: Tracer | None,
    ) -> None:
        self._graph_store = graph_store
        self._embedder = embedder
        self._scope = scope
        self._memory = memory
        self._decisions = decisions
        self._model = model
        self._settings = settings
        self._middleware = middleware
        self._provider = provider
        self._tracer = tracer

    async def ainvoke(  # noqa: PLR0912, PLR0915
        self, input_data: dict[str, str]
    ) -> AgentRunResult:
        """Run or resume the named task and validate the answer citations."""
        from deepagents import create_deep_agent  # noqa: PLC0415
        from langgraph.errors import GraphRecursionError  # noqa: PLC0415

        task_name = input_data["task_name"]
        question = input_data["question"]
        lookup = await self._memory.get_task(task_name)
        if not lookup.found:
            created = await self._memory.create_task(task_name, question)
            if not created.recorded:
                raise ValueError(f"Could not create task: {created.error}")
            lookup = await self._memory.get_task(task_name)
        if lookup.view is not None and lookup.view.step_counts[StepState.IN_PROGRESS]:
            await _mark_interrupted_steps(self._memory, task_name, lookup.view)
            lookup = await self._memory.get_task(task_name)
        view = lookup.view
        view_json = view.model_dump_json() if view is not None else "{}"
        prior_events = await _task_events(self._memory, task_name)
        saved_evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for event in prior_events
                if event.kind is EventKind.NOTE and event.name == "fetched_evidence"
                for evidence_id in json.loads(event.payload)
            )
        )
        restored = await fetch(
            self._graph_store,
            saved_evidence_ids,
            scope=self._scope,
            max_chars=self._settings.max_result_characters,
        )
        restored = [item for item in restored if item.status.value == "ok"]
        fetched_ids = [item.evidence_id for item in restored]
        tools, run_state = make_core_tools(
            graph_store=self._graph_store,
            embedder=self._embedder,
            scope=self._scope,
            task_name=task_name,
            memory=self._memory,
            decisions=self._decisions,
            fetched_ids=fetched_ids,
            fetched_outcomes=restored,
            max_chars=self._settings.max_result_characters,
            max_tool_calls=self._settings.max_tool_calls,
        )
        await record_event_or_flag(
            self._memory,
            task_name,
            run_state,
            EventKind.MESSAGE,
            role="user",
            payload=question,
        )
        completed = view.steps[StepState.COMPLETED] if view is not None else []
        reused = await _completed_results(
            self._memory,
            task_name,
            completed,
            max_chars=self._settings.max_result_characters,
        )
        ensure_harness_profile(self._provider)
        agent = create_deep_agent(
            model=self._model,
            tools=tools,
            system_prompt=AGENT_SYSTEM,
            middleware=[
                *self._middleware,
                TaskEventMiddleware(self._memory, task_name, run_state),
            ],
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
                        f"Do not repeat these steps:\n{reused}"
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
        answer = _message_content(messages_out[-1]) if messages_out else ""
        invalid: list[str] = []
        citations = _citation_ids(answer)
        valid_citations = []
        if citations:
            checks = await check_citations(citations, fetched_ids, scope=self._scope)
            invalid = [
                check.cited_id for check in checks if check.verdict.value != "valid"
            ]
            valid_citations = [
                check.cited_id for check in checks if check.verdict.value == "valid"
            ]
            if invalid and run_state.tool_calls < self._settings.max_tool_calls:
                await record_event_or_flag(
                    self._memory,
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
                    answer = (
                        _message_content(messages_out[-1]) if messages_out else answer
                    )
                    citations = _citation_ids(answer)
                    checks = await check_citations(
                        citations, fetched_ids, scope=self._scope
                    )
                    invalid = [
                        check.cited_id
                        for check in checks
                        if check.verdict.value != "valid"
                    ]
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
        elif invalid:
            status = "partial"
        elif "insufficient evidence" in answer.lower():
            status = "insufficient_evidence"
        current_task = await self._memory.get_task(task_name)
        last_seq = current_task.view.last_event_seq if current_task.view else 0
        return AgentRunResult(
            answer=answer,
            status=status,
            citations=[
                run_state.fetches[evidence_id]
                for evidence_id in valid_citations
                if evidence_id in run_state.fetches
            ],
            invalid_citations=invalid,
            task={"name": task_name, "last_event_seq": last_seq},
            recording_failures=run_state.recording_failures,
            messages=messages_out,
        )


async def _mark_interrupted_steps(
    memory: TaskMemory, task_name: str, view: TaskView
) -> None:
    """Mark steps a stopped run left in progress as unknown.

    The earlier run ended before it recorded their outcome. Unknown steps are
    rerun by the next run, and the view shows that they were not completed.
    """
    for step in view.steps[StepState.IN_PROGRESS]:
        await memory.set_step(task_name, step.name, StepState.UNKNOWN, kind=step.kind)


async def _task_events(memory: TaskMemory, task_name: str) -> list[Event]:
    """Read every event of a task in sequence order, one page at a time."""
    events: list[Event] = []
    after_seq = 0
    while True:
        page = await memory.list_events(task_name, after_seq=after_seq, limit=200)
        events.extend(page.events)
        if not page.truncated or page.next_after_seq is None:
            return events
        after_seq = page.next_after_seq


async def _completed_results(
    memory: TaskMemory,
    task_name: str,
    steps: Sequence[StepSummary],
    *,
    max_chars: int,
) -> str:
    """Render the stored result of each completed step, up to a character bound."""
    lines: list[str] = []
    used = 0
    for step in steps:
        if step.result_event_seq is None:
            text = "(no stored result)"
        else:
            page = await memory.list_events(
                task_name, after_seq=step.result_event_seq - 1, limit=1
            )
            text = page.events[0].payload if page.events else "(stored result missing)"
        room = max_chars - used
        if room <= 0:
            lines.append(f"- {step.name}: (omitted, result limit reached)")
            continue
        text = text[:room]
        used += len(text)
        lines.append(f"- {step.name}: {text}")
    return "\n".join(lines)


def _repair_request(invalid: list[str]) -> str:
    """Name the citations that failed the check, for the repair turn."""
    return (
        "Repair once. Remove unsupported citations or fetch them. "
        f"Invalid evidence ids: {invalid}"
    )


def _message_content(message: Any) -> str:
    """Return message content as text for event storage and result output."""
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content", "")
    return content if isinstance(content, str) else str(content or "")


def _citation_ids(answer: str) -> list[str]:
    """Extract evidence ids in the answer's square-bracket citations."""
    import re  # noqa: PLC0415

    return list(dict.fromkeys(re.findall(r"\[([A-Za-z0-9_-]+)\]", answer)))
