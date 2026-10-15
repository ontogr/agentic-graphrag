"""Checks the task agent run with a scripted model and an in-memory task store.

The model replies are scripted, so no LLM is called. The evidence functions
are replaced with small fakes, and the task store keeps steps and events in
memory. The tests cover the citation check, its one repair turn, resume from
stored steps and events, and the run statuses.
"""

import json
from types import SimpleNamespace
from typing import Any

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from agrag.agents import build as build_module
from agrag.agents.build import _citation_ids, _TaskAgent
from agrag.agents.settings import AgentSettings
from agrag.common.data_models.evidence import FetchStatus
from agrag.common.data_models.task import (
    EventKind,
    SetStepResult,
    StepKind,
    StepState,
    StepSummary,
    TaskLookup,
    TaskStatus,
)
from agrag.memory.tasks import build_task_view


_VALID = "ev1:s:0d0c1b2a-0000-4000-8000-000000000001:0123456789abcdef:0-10"
_OTHER = "ev1:s:0d0c1b2a-0000-4000-8000-000000000002:0123456789abcdef:0-10"
_BAD = "ev1:s:0d0c1b2a-0000-4000-8000-000000000003:0123456789abcdef:0-10"


class _ScriptedModel(BaseChatModel):
    """Chat model that replays scripted replies and records every input."""

    replies: list[Any] = []
    calls: int = 0
    seen: list[list[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        """Name the fake model type."""
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_ScriptedModel":
        """Accept the agent's tools without changing the replies."""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Record the input, then return the next scripted reply."""
        self.seen.append(list(messages))
        reply = self.replies[self.calls]
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=reply)])


def _call(name: str, args: dict[str, Any], call_id: str) -> AIMessage:
    """Build a model reply that calls one tool."""
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": call_id}]
    )


def _text(messages: list[BaseMessage]) -> str:
    """Join the text of every message in one model input."""
    return "\n".join(str(message.content) for message in messages)


class _Memory:
    """In-memory stand-in for the task memory used by one run."""

    def __init__(self) -> None:
        """Start with no task, steps or events."""
        self.exists = False
        self.steps: dict[str, StepSummary] = {}
        self.events: list[SimpleNamespace] = []

    def _event(self, kind: EventKind, name: str | None, payload: str, role: str | None):
        """Append one event with the next sequence number."""
        event = SimpleNamespace(
            seq=len(self.events) + 1, kind=kind, name=name, payload=payload, role=role
        )
        self.events.append(event)
        return event

    async def get_task(self, name: str) -> TaskLookup:
        """Return the view of the task, when it exists."""
        if not self.exists:
            return TaskLookup(found=False)
        counts = dict.fromkeys(StepState, 0)
        for step in self.steps.values():
            counts[step.state] += 1
        view = build_task_view(
            task_name=name,
            goal="goal",
            status=TaskStatus.OPEN,
            last_event_seq=len(self.events),
            step_counts=counts,
            steps=list(self.steps.values()),
        )
        return TaskLookup(found=True, view=view)

    async def create_task(self, name: str, goal: str) -> Any:
        """Create the task."""
        self.exists = True
        return SimpleNamespace(recorded=True, error=None)

    async def record_event(
        self,
        task_name: str,
        kind: EventKind,
        *,
        role: str | None = None,
        name: str | None = None,
        payload: str,
        request_id: str | None = None,
    ) -> Any:
        """Append the event."""
        return SimpleNamespace(
            recorded=True, error=None, event=self._event(kind, name, payload, role)
        )

    async def list_events(
        self, task_name: str, *, after_seq: int = 0, limit: int = 50
    ) -> Any:
        """Return one page of events after a sequence number."""
        events = [event for event in self.events if event.seq > after_seq][:limit]
        return SimpleNamespace(
            found=True, events=events, truncated=False, next_after_seq=None
        )

    async def list_steps(self, task_name: str, state: StepState) -> list[StepSummary]:
        """Return every step in one state."""
        return sorted(
            (step for step in self.steps.values() if step.state is state),
            key=lambda step: step.name,
        )

    async def set_step(
        self,
        task_name: str,
        name: str,
        state: StepState,
        *,
        kind: StepKind = StepKind.OTHER,
        result_event_seq: int | None = None,
        request_id: str | None = None,
    ) -> SetStepResult:
        """Store the step in its new state."""
        self.steps[name] = StepSummary(
            name=name, kind=kind, state=state, result_event_seq=result_event_seq
        )
        return SetStepResult(recorded=True)


class _Decisions:
    """Decision memory that is never used by these runs."""


def _outcome(evidence_id: str) -> SimpleNamespace:
    """Return a complete fetch outcome for one evidence id."""
    return SimpleNamespace(
        evidence_id=evidence_id,
        status=FetchStatus.OK,
        text="passage",
        model_dump=lambda mode: {"evidence_id": evidence_id},
    )


def _fake_evidence(monkeypatch: pytest.MonkeyPatch, complete: set[str]) -> None:
    """Replace the evidence calls with fakes that know which ids are complete."""

    async def fetch(store: Any, ids: list[str], *, scope: Any, max_chars: int) -> list:
        return [
            _outcome(evidence_id)
            if evidence_id in complete
            else SimpleNamespace(
                evidence_id=evidence_id,
                status=FetchStatus.UNAVAILABLE,
                text=None,
                model_dump=lambda mode, e=evidence_id: {"evidence_id": e},
            )
            for evidence_id in ids
        ]

    async def check(ids: list[str], fetched: Any, *, scope: Any) -> list:
        return [
            SimpleNamespace(
                cited_id=evidence_id,
                verdict=SimpleNamespace(
                    value="valid" if evidence_id in fetched else "not_fetched"
                ),
            )
            for evidence_id in ids
        ]

    monkeypatch.setattr(build_module, "fetch", fetch)
    monkeypatch.setattr(build_module, "check_citations", check)
    monkeypatch.setattr(build_module, "ensure_harness_profile", lambda provider: None)

    async def discover(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(
            status=SimpleNamespace(value="ok"),
            truncated=False,
            model_dump_json=lambda: "{}",
        )

    monkeypatch.setattr("agrag.agents.tools.core.discover", discover)
    monkeypatch.setattr("agrag.agents.tools.core.fetch", fetch)
    monkeypatch.setattr("agrag.agents.tools.core.check_citations", check)


def _patch_deep_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use a plain LangChain agent in place of the DeepAgents graph."""

    def deep_agent(
        *, model: Any, tools: Any, system_prompt: str, middleware: Any
    ) -> Any:
        return create_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            middleware=middleware,
        )

    monkeypatch.setattr("deepagents.create_deep_agent", deep_agent)


def _agent(
    memory: _Memory,
    model: _ScriptedModel,
    *,
    settings: AgentSettings | None = None,
) -> _TaskAgent:
    """Build the task agent around the fake memory and scripted model."""
    return _TaskAgent(
        graph_store=object(),  # type: ignore[arg-type]
        embedder=object(),  # type: ignore[arg-type]
        scope=frozenset({"doc-1"}),
        memory=memory,  # type: ignore[arg-type]
        decisions=_Decisions(),  # type: ignore[arg-type]
        model=model,
        settings=settings or AgentSettings(),
        middleware=[],
        provider="openai",
        tracer=None,
    )


class TestCitationIds:
    """Bracketed citations are read from the evidence id grammar."""

    def test_reads_evidence_ids_with_colons(self) -> None:
        """A bracketed span id is found, and a repeat is listed once."""
        answer = f"Aspirin helps [{_VALID}] and again [{_VALID}]."

        assert _citation_ids(answer) == [_VALID]

    def test_reads_every_id_of_a_grouped_citation(self) -> None:
        """Ids inside one bracket group are each returned."""
        answer = f"Two sources [{_VALID}, {_OTHER}]."

        assert _citation_ids(answer) == [_VALID, _OTHER]

    def test_ignores_brackets_without_evidence_ids(self) -> None:
        """Numbered footnotes are not citations."""
        assert _citation_ids("See [1] and [note].") == []


class TestTaskAgentRun:
    """A run answers, cites, repairs, resumes, and reports its status."""

    async def test_answer_with_a_fetched_citation_is_answered(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cited id that was fetched in this run is returned as a citation."""
        _fake_evidence(monkeypatch, complete={_VALID})
        _patch_deep_agent(monkeypatch)
        model = _ScriptedModel(
            replies=[
                _call("fetch_evidence", {"evidence_ids": [_VALID]}, "f1"),
                AIMessage(content=f"Aspirin treats headaches [{_VALID}]."),
            ]
        )
        memory = _Memory()

        result = await _agent(memory, model).ainvoke(
            {"task_name": "headache", "question": "What treats headaches?"}
        )

        assert result["status"] == "answered"
        assert result["invalid_citations"] == []
        assert [item.evidence_id for item in result["citations"]] == [_VALID]
        assert result["task"]["name"] == "headache"
        assert result["recording_failures"] == []
        assert model.calls == 2

    async def test_an_unfetched_citation_gets_one_repair_turn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An invalid citation triggers one repair, after which the answer is clean."""
        _fake_evidence(monkeypatch, complete={_VALID})
        _patch_deep_agent(monkeypatch)
        model = _ScriptedModel(
            replies=[
                _call("fetch_evidence", {"evidence_ids": [_VALID]}, "f1"),
                AIMessage(content=f"Known [{_VALID}] and guessed [{_BAD}]."),
                AIMessage(content=f"Known only [{_VALID}]."),
            ]
        )
        memory = _Memory()

        result = await _agent(memory, model).ainvoke(
            {"task_name": "repair", "question": "q"}
        )

        assert model.calls == 3
        assert result["invalid_citations"] == []
        assert result["status"] == "answered"
        assert result["answer"] == f"Known only [{_VALID}]."
        repair_turns = [
            event for event in memory.events if event.payload.startswith("Repair once")
        ]
        assert len(repair_turns) == 1
        assert _BAD in repair_turns[0].payload

    async def test_a_repair_that_still_cites_badly_is_partial(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the repaired answer still has an invalid citation, the run is partial."""
        _fake_evidence(monkeypatch, complete={_VALID})
        _patch_deep_agent(monkeypatch)
        model = _ScriptedModel(
            replies=[
                _call("fetch_evidence", {"evidence_ids": [_VALID]}, "f1"),
                AIMessage(content=f"Guessed [{_BAD}]."),
                AIMessage(content=f"Still guessed [{_BAD}]."),
            ]
        )

        result = await _agent(_Memory(), model).ainvoke(
            {"task_name": "still-bad", "question": "q"}
        )

        assert result["status"] == "partial"
        assert result["invalid_citations"] == [_BAD]
        assert result["citations"] == []

    async def test_an_insufficient_answer_is_reported_as_such(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An answer that says the evidence is insufficient gets that status."""
        _fake_evidence(monkeypatch, complete=set())
        _patch_deep_agent(monkeypatch)
        model = _ScriptedModel(
            replies=[AIMessage(content="Insufficient evidence in the sources.")]
        )

        result = await _agent(_Memory(), model).ainvoke(
            {"task_name": "thin", "question": "q"}
        )

        assert result["status"] == "insufficient_evidence"

    async def test_a_run_past_its_recursion_limit_reports_the_budget(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A run the graph stops early ends with an empty answer and budget status."""
        _fake_evidence(monkeypatch, complete=set())
        _patch_deep_agent(monkeypatch)
        model = _ScriptedModel(
            replies=[_call("get_task", {}, f"g{index}") for index in range(10)]
        )

        result = await _agent(
            _Memory(),
            model,
            settings=AgentSettings(recursion_limit=2),
        ).ainvoke({"task_name": "long", "question": "q"})

        assert result["status"] == "budget_exhausted"
        assert result["answer"] == ""

    async def test_resume_reuses_completed_results_and_marks_interrupted_steps(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Stored results go to the model, and steps left in progress become unknown."""
        _fake_evidence(monkeypatch, complete={_VALID})
        _patch_deep_agent(monkeypatch)
        memory = _Memory()
        memory.exists = True
        noted = await memory.record_event(
            "resume", EventKind.NOTE, name="step:search", payload="result for search"
        )
        noted_event = noted.event
        assert noted_event is not None
        memory.steps["search"] = StepSummary(
            name="search",
            kind=StepKind.READ,
            state=StepState.COMPLETED,
            result_event_seq=noted_event.seq,
        )
        memory.steps["draft"] = StepSummary(
            name="draft",
            kind=StepKind.ANALYSIS,
            state=StepState.IN_PROGRESS,
            result_event_seq=None,
        )
        model = _ScriptedModel(replies=[AIMessage(content="Done.")])

        result = await _agent(memory, model).ainvoke(
            {"task_name": "resume", "question": "q"}
        )

        assert result["status"] == "answered"
        assert "result for search" in _text(model.seen[0])
        assert memory.steps["draft"].state is StepState.UNKNOWN

    async def test_resume_restores_fetched_evidence_from_saved_notes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Evidence fetched by an earlier run is fetched again and can be cited."""
        _fake_evidence(monkeypatch, complete={_VALID})
        _patch_deep_agent(monkeypatch)
        memory = _Memory()
        memory.exists = True
        await memory.record_event(
            "resume-evidence",
            EventKind.NOTE,
            name="fetched_evidence",
            payload=json.dumps([_VALID]),
        )
        model = _ScriptedModel(replies=[AIMessage(content=f"Cited again [{_VALID}].")])

        result = await _agent(memory, model).ainvoke(
            {"task_name": "resume-evidence", "question": "q"}
        )

        assert result["status"] == "answered"
        assert [item.evidence_id for item in result["citations"]] == [_VALID]
