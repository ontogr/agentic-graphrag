"""Checks the bounded tool set exposed by a default task agent."""

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from agrag.agents.tools.core import make_core_tools
from agrag.common.data_models.evidence import FetchStatus
from agrag.common.data_models.task import EventKind, StepKind, StepState


class TestCoreTools:
    """The default agent exposes only scoped evidence and memory operations."""

    def test_returns_evidence_navigation_task_and_decision_tools(self) -> None:
        """Tool names expose the single-agent operations and no delegation."""
        tools, _ = make_core_tools(
            graph_store=MagicMock(),
            embedder=MagicMock(),
            scope=frozenset({"doc-1"}),
            task_name="task-1",
            memory=MagicMock(),
            decisions=MagicMock(),
            fetched_ids=[],
            fetched_outcomes=[],
            max_chars=1_000,
            max_tool_calls=10,
        )

        assert {tool.name for tool in tools} == {
            "discover_evidence",
            "fetch_evidence",
            "navigate",
            "find_entities",
            "explore",
            "check_citations",
            "get_task",
            "set_step",
            "record_decision",
            "supersede_decision",
            "search_decisions",
        }


class _Memory:
    """Task memory stand-in that records steps and events."""

    def __init__(self, *, record_ok: bool = True) -> None:
        """Choose whether event writes succeed."""
        self.record_ok = record_ok
        self.events: list[tuple[EventKind, str | None, str]] = []
        self.steps: list[dict[str, Any]] = []

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
        """Store the event and return a stand-in result."""
        self.events.append((kind, name, payload))
        event = SimpleNamespace(seq=len(self.events))
        return SimpleNamespace(
            recorded=self.record_ok,
            event=event,
            error=None if self.record_ok else "unavailable",
        )

    async def set_step(
        self, task_name: str, name: str, state: StepState, **kwargs: Any
    ) -> Any:
        """Store the step and return a stand-in result."""
        self.steps.append({"name": name, "state": state, **kwargs})
        return SimpleNamespace(model_dump_json=lambda: '{"recorded": true}')

    async def get_task(self, name: str) -> Any:
        """Return a lookup for a task that does not exist."""
        return SimpleNamespace(model_dump_json=lambda: '{"found": false}')


class _Decisions:
    """Decision memory stand-in with a fixed outcome."""

    def __init__(self, *, recorded: bool = True) -> None:
        """Choose whether decision writes succeed."""
        self.recorded = recorded
        self.calls: list[str] = []

    async def record_decision(self, *args: Any, **kwargs: Any) -> Any:
        """Return a recorded or refused outcome."""
        self.calls.append("record")
        return SimpleNamespace(
            recorded=self.recorded,
            error=None if self.recorded else "conflict",
            model_dump_json=lambda: '{"recorded": true}',
        )

    async def supersede_decision(self, *args: Any, **kwargs: Any) -> Any:
        """Return a recorded outcome."""
        self.calls.append("supersede")
        return SimpleNamespace(
            recorded=self.recorded,
            error=None if self.recorded else "missing",
            model_dump_json=lambda: '{"recorded": true}',
        )

    async def search_decisions(self, query: str, *, limit: int) -> list[Any]:
        """Return one precedent."""
        return [SimpleNamespace(model_dump=lambda mode: {"choice_key": query})]


def _outcome(evidence_id: str, status: FetchStatus, text: str = "passage") -> Any:
    """Return a stand-in fetch outcome."""
    return SimpleNamespace(
        evidence_id=evidence_id,
        status=status,
        text=text,
        model_dump=lambda mode: {"evidence_id": evidence_id, "status": status.value},
    )


def _result(status: str = "ok", *, truncated: bool = False, **extra: Any) -> Any:
    """Return a stand-in search or navigation result."""
    return SimpleNamespace(
        status=SimpleNamespace(value=status),
        truncated=truncated,
        truncated_by=extra.get("truncated_by", []),
        model_dump_json=lambda: json.dumps({"status": status}),
    )


def _tools(
    memory: Any,
    decisions: Any = None,
    *,
    fetched: list[Any] | None = None,
    max_tool_calls: int = 50,
) -> tuple[dict[str, Any], Any]:
    """Build the core tools by name, with the run state they share."""
    tools, state = make_core_tools(
        graph_store=MagicMock(),
        embedder=MagicMock(),
        scope=frozenset({"doc-1"}),
        task_name="task-1",
        memory=memory,
        decisions=decisions or _Decisions(),
        fetched_ids=[],
        fetched_outcomes=fetched or [],
        max_chars=1_000,
        max_tool_calls=max_tool_calls,
    )
    return {tool.name: tool for tool in tools}, state


class TestCoreToolBodies:
    """Each evidence, step and decision tool validates input and records outcomes."""

    async def test_discover_rejects_a_limit_outside_bounds(self) -> None:
        """A limit of zero or above fifty is refused without a search."""
        tools, _ = _tools(_Memory())

        assert await tools["discover_evidence"].ainvoke({"query": "q", "limit": 0}) == (
            "Limit must be between 1 and 50."
        )

    async def test_discover_reports_an_unknown_mode(self) -> None:
        """An unknown search mode is a correctable tool message."""
        tools, _ = _tools(_Memory())

        reply = await tools["discover_evidence"].ainvoke(
            {"query": "q", "mode": "bogus"}
        )

        assert reply.startswith("Invalid discovery request:")

    async def test_discover_flags_a_failed_search(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A search that did not complete marks the run's retrieval as failed."""

        async def failed(*args: Any, **kwargs: Any) -> Any:
            return _result("failed")

        monkeypatch.setattr("agrag.agents.tools.core.discover", failed)
        tools, state = _tools(_Memory())

        await tools["discover_evidence"].ainvoke({"query": "q"})

        assert state.retrieval_failed

    async def test_fetch_rejects_more_than_twenty_ids(self) -> None:
        """A fetch of more than twenty ids is refused."""
        tools, _ = _tools(_Memory())

        reply = await tools["fetch_evidence"].ainvoke({"evidence_ids": ["x"] * 21})

        assert reply == "Fetch at most 20 evidence ids per call."

    async def test_fetch_records_complete_ids_and_flags_partial_ones(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Complete text is recorded as fetched; partial text flags the run."""

        async def fetch(*args: Any, **kwargs: Any) -> list[Any]:
            return [
                _outcome("ev1:s:a", FetchStatus.OK),
                _outcome("ev1:s:b", FetchStatus.PARTIAL, ""),
            ]

        monkeypatch.setattr("agrag.agents.tools.core.fetch", fetch)
        memory = _Memory()
        tools, state = _tools(memory)

        reply = await tools["fetch_evidence"].ainvoke(
            {"evidence_ids": ["ev1:s:a", "ev1:s:b"]}
        )

        assert [item["status"] for item in json.loads(reply)] == ["ok", "partial"]
        assert state.fetched_ids == ["ev1:s:a"]
        assert state.retrieval_failed
        assert memory.events == [(EventKind.NOTE, "fetched_evidence", '["ev1:s:a"]')]

    async def test_navigate_reports_an_unknown_relation(self) -> None:
        """A relation outside the enum is a correctable tool message."""
        tools, _ = _tools(_Memory())

        reply = await tools["navigate"].ainvoke(
            {"evidence_id": "ev1:s:a", "relation": "sideways"}
        )

        assert reply.startswith("Invalid navigation request:")

    async def test_navigate_flags_a_failed_navigation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed navigation marks the run's retrieval as failed."""

        async def navigate(*args: Any, **kwargs: Any) -> Any:
            return _result("failed")

        monkeypatch.setattr("agrag.agents.tools.core.navigate", navigate)
        tools, state = _tools(_Memory())

        await tools["navigate"].ainvoke({"evidence_id": "ev1:s:a", "relation": "next"})

        assert state.retrieval_failed

    async def test_find_entities_rejects_a_limit_outside_bounds(self) -> None:
        """An entity search limit above fifty is refused."""
        tools, _ = _tools(_Memory())

        reply = await tools["find_entities"].ainvoke({"query": "q", "limit": 51})

        assert reply == "Limit must be between 1 and 50."

    async def test_find_entities_flags_a_truncated_search(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A truncated entity search marks the run's retrieval as failed."""

        async def find(*args: Any, **kwargs: Any) -> Any:
            return _result("ok", truncated=True)

        monkeypatch.setattr("agrag.agents.tools.core.find_entities", find)
        tools, state = _tools(_Memory())

        await tools["find_entities"].ainvoke({"query": "aspirin"})

        assert state.retrieval_failed

    async def test_explore_clamps_depth_and_flags_a_bounded_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Depth is capped at two, and a bounded exploration marks the run."""
        seen: dict[str, Any] = {}

        async def explore(*args: Any, depth: int, **kwargs: Any) -> Any:
            seen["depth"] = depth
            return _result("ok", truncated_by=["max_nodes"])

        monkeypatch.setattr("agrag.agents.tools.core.explore_evidence", explore)
        tools, state = _tools(_Memory())

        await tools["explore"].ainvoke({"entity_id": "e1", "depth": 9})

        assert seen["depth"] == 2
        assert state.retrieval_failed

    async def test_explore_reports_an_invalid_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A request the store refuses is a correctable tool message."""

        async def explore(*args: Any, **kwargs: Any) -> Any:
            raise ValueError("unknown entity")

        monkeypatch.setattr("agrag.agents.tools.core.explore_evidence", explore)
        tools, _ = _tools(_Memory())

        reply = await tools["explore"].ainvoke({"entity_id": "e1"})

        assert reply == "Invalid exploration request: unknown entity"

    async def test_check_citations_returns_a_verdict_per_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each cited id gets one verdict in the order given."""

        async def check(ids: list[str], fetched: Any, *, scope: Any) -> list[Any]:
            return [
                SimpleNamespace(
                    model_dump=lambda mode, cited=cited: {"cited_id": cited}
                )
                for cited in ids
            ]

        monkeypatch.setattr("agrag.agents.tools.core.check_citations", check)
        tools, _ = _tools(_Memory())

        reply = await tools["check_citations"].ainvoke({"evidence_ids": ["a", "b"]})

        assert [item["cited_id"] for item in json.loads(reply)] == ["a", "b"]

    async def test_get_task_reads_the_task_view(self) -> None:
        """The task tool returns the memory's lookup as JSON."""
        tools, _ = _tools(_Memory())

        assert await tools["get_task"].ainvoke({}) == '{"found": false}'

    async def test_set_step_rejects_an_unknown_state(self) -> None:
        """A state outside the enum is a correctable tool message."""
        tools, _ = _tools(_Memory())

        reply = await tools["set_step"].ainvoke({"name": "s", "state_name": "paused"})

        assert reply.startswith("Invalid step:")

    async def test_set_step_completed_needs_result_text(self) -> None:
        """A completed step without its result is refused."""
        memory = _Memory()
        tools, _ = _tools(memory)

        reply = await tools["set_step"].ainvoke(
            {"name": "s", "state_name": "completed", "result": ""}
        )

        assert reply == "A completed step needs its result text."
        assert memory.steps == []

    async def test_set_step_does_not_complete_when_the_result_is_not_recorded(
        self,
    ) -> None:
        """A step is not completed when its result event cannot be written."""
        memory = _Memory(record_ok=False)
        tools, _ = _tools(memory)

        reply = await tools["set_step"].ainvoke(
            {"name": "s", "state_name": "completed", "result": "text"}
        )

        assert (
            reply == "The step result was not recorded, so the step is not completed."
        )
        assert memory.steps == []

    async def test_set_step_tracks_open_steps_until_they_resolve(self) -> None:
        """An in-progress step is open for this run until another state is set."""
        memory = _Memory()
        tools, state = _tools(memory)

        await tools["set_step"].ainvoke(
            {"name": "draft", "state_name": "in_progress", "kind": "analysis"}
        )
        assert state.open_steps == {"draft": StepKind.ANALYSIS}

        await tools["set_step"].ainvoke(
            {"name": "draft", "state_name": "completed", "result": "done"}
        )
        assert state.open_steps == {}
        completed = memory.steps[-1]
        assert completed["state"] is StepState.COMPLETED
        assert completed["result_event_seq"] == 1

    async def test_record_decision_flags_a_refused_write(self) -> None:
        """A decision the store refuses flags the run's recording."""
        tools, state = _tools(_Memory(), _Decisions(recorded=False))

        reply = await tools["record_decision"].ainvoke(
            {
                "choice_key": "k",
                "conclusion": "c",
                "rationale": "r",
                "evidence_ids": [],
            }
        )

        assert json.loads(reply) == {"recorded": True}
        assert state.recording_failed
        assert state.recording_failures == ["record_decision: conflict"]

    async def test_supersede_decision_needs_a_decision_id(self) -> None:
        """A supersede call with a malformed id is refused."""
        tools, _ = _tools(_Memory())

        reply = await tools["supersede_decision"].ainvoke(
            {
                "decision_id": "not-a-uuid",
                "conclusion": "c",
                "rationale": "r",
                "explanation": "e",
                "evidence_ids": [],
            }
        )

        assert reply == "decision_id must be the id of an existing decision."

    async def test_supersede_decision_records_the_replacement(self) -> None:
        """A valid supersede call reaches the decision memory."""
        decisions = _Decisions()
        tools, state = _tools(_Memory(), decisions)

        await tools["supersede_decision"].ainvoke(
            {
                "decision_id": "7f8d2d4e-6a8f-4c3e-9f0a-1b2c3d4e5f60",
                "conclusion": "c",
                "rationale": "r",
                "explanation": "e",
                "evidence_ids": [],
            }
        )

        assert decisions.calls == ["supersede"]
        assert not state.recording_failed

    async def test_search_decisions_checks_its_limit_and_returns_precedents(
        self,
    ) -> None:
        """The precedent search refuses a large limit and returns matches."""
        tools, _ = _tools(_Memory())

        refused = await tools["search_decisions"].ainvoke({"query": "q", "limit": 21})
        found = await tools["search_decisions"].ainvoke({"query": "q", "limit": 5})

        assert refused == "Limit must be between 1 and 20."
        assert json.loads(found) == [{"choice_key": "q"}]

    async def test_every_tool_stops_once_the_budget_is_spent(self) -> None:
        """After the budget is used, a tool returns the budget message only."""
        tools, state = _tools(_Memory(), max_tool_calls=1)

        first = await tools["get_task"].ainvoke({})
        second = await tools["get_task"].ainvoke({})

        assert first == '{"found": false}'
        assert second == "Tool budget exhausted."
        assert state.budget_exhausted
