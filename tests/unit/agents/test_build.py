"""Tests for build_agent and the _SimpleAgent/_RunScopedAgent fallbacks.

Patches ``importlib.util.find_spec`` to simulate ``deepagents`` being absent
and stubs the ``deepagents`` module in ``sys.modules`` to capture the
subagents, middleware, and recursion limit passed to ``create_deep_agent``
without installing the real dependency. The retrieval engine and LLM are
mocked with ``MagicMock``/``AsyncMock``. Covers per-run citation ledger and
research-attempt-limiter isolation, the harness profile registration, that
search filters reach the engine through both agent implementations, and
that ``_SimpleAgent`` synthesizes its answer through a model call rather
than returning raw concatenated evidence.
"""

import importlib.util
import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from agrag.agents.build import _RunScopedAgent, _SimpleAgent, build_agent
from agrag.agents.middleware import ResearchAttemptLimiter
from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.agents.verification import VerificationResult
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_schema import GENERIC, GraphSchema
from agrag.common.data_models.search_result import SearchResult
from agrag.llm.client_config import LLMClientConfig
from agrag.retrieval.filters import SearchFilters


def _capture_deepagents(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    """Stub deepagents so create_deep_agent records its kwargs."""

    class _FakeAgent:
        async def ainvoke(self, input_data: dict, config: dict | None = None) -> dict:
            captured["config"] = config
            return {"messages": []}

    def fake_create_deep_agent(**kwargs: object) -> _FakeAgent:
        captured.update(kwargs)
        return _FakeAgent()

    fake_deepagents = types.SimpleNamespace(
        create_deep_agent=fake_create_deep_agent,
        HarnessProfile=MagicMock(),
        GeneralPurposeSubagentProfile=MagicMock(),
        register_harness_profile=MagicMock(),
    )
    monkeypatch.setitem(sys.modules, "deepagents", fake_deepagents)


def _engine() -> MagicMock:
    """Return a mock engine whose schema property resolves."""
    engine = MagicMock()
    engine.search = AsyncMock(return_value=[])
    engine.graph_schema = GENERIC
    return engine


class TestBuildAgent:
    """Tests agent construction and per-invocation agent wrappers."""

    def test_builds_simple_agent_without_deepagents(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without deepagents, build_agent returns _SimpleAgent."""
        real_find_spec = importlib.util.find_spec

        def no_deepagents(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "deepagents":
                return None
            return real_find_spec(name, *args, **kwargs)

        monkeypatch.setattr(importlib.util, "find_spec", no_deepagents)
        settings = AgentLLMSettings(
            clients=[
                LLMClientConfig(
                    name="test",
                    provider="openai",
                    model="gpt-4o",
                    api_key="test",
                )
            ]
        )
        try:
            agent = build_agent(engine=MagicMock(), llm_settings=settings)
        except ImportError:
            pytest.skip("langchain-openai not installed")
        assert isinstance(agent, _SimpleAgent)

    def test_rejects_mismatched_graph_schema(self) -> None:
        """A graph_schema differing from the engine's raises."""
        settings = AgentLLMSettings(
            clients=[
                LLMClientConfig(
                    name="test",
                    provider="openai",
                    model="gpt-4o",
                    api_key="test",
                )
            ]
        )
        custom = GraphSchema(
            name="other",
            version="1",
            entities=[],
            relations=[],
        )
        engine = _engine()
        try:
            with pytest.raises(ValueError, match="does not match"):
                build_agent(
                    engine=engine,
                    llm_settings=settings,
                    graph_schema=custom,
                )
        except ImportError:
            pytest.skip("agent provider extra is not installed")

    def test_accepts_the_engine_graph_schema(self) -> None:
        """Passing the engine's own schema constructs normally."""
        settings = AgentLLMSettings(
            clients=[
                LLMClientConfig(
                    name="test",
                    provider="openai",
                    model="gpt-4o",
                    api_key="test",
                )
            ]
        )
        try:
            agent = build_agent(
                engine=_engine(),
                llm_settings=settings,
                graph_schema=GENERIC,
            )
        except ImportError:
            pytest.skip("langchain-openai not installed")
        assert isinstance(agent, _SimpleAgent | _RunScopedAgent)

    async def test_build_agent_registers_the_configured_provider_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The harness key maps openai-generic to the OpenAI provider."""
        captured: dict = {}
        _capture_deepagents(monkeypatch, captured)

        real_find_spec = importlib.util.find_spec

        def with_deepagents(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "deepagents":
                return MagicMock()
            return real_find_spec(name, *args, **kwargs)

        monkeypatch.setattr(importlib.util, "find_spec", with_deepagents)

        monkeypatch.setattr(
            "agrag.agents.build.build_chat_model",
            lambda config: MagicMock(),
        )
        ensure_calls: list = []
        monkeypatch.setattr(
            "agrag.agents.build.ensure_harness_profile", ensure_calls.append
        )
        settings = AgentLLMSettings(
            clients=[
                LLMClientConfig(
                    name="test",
                    provider="openai-generic",
                    model="test-model",
                    api_key="test",
                    base_url="http://localhost:1/v1",
                )
            ]
        )
        agent = build_agent(engine=_engine(), llm_settings=settings)
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        assert ensure_calls == ["openai"]

    async def test_simple_agent_creates_fresh_ledger_per_run(self) -> None:
        """Each ainvoke call gets a fresh Ledger."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        result = SearchResult(item=ent, score=0.9, method="entity")
        engine = MagicMock()
        engine.search = AsyncMock(return_value=[result])
        model = AsyncMock(ainvoke=AsyncMock(return_value=MagicMock(text="answer")))

        agent = _SimpleAgent(
            model=model,
            engine=engine,
        )

        await agent.ainvoke({"messages": [{"role": "user", "content": "first"}]})
        await agent.ainvoke({"messages": [{"role": "user", "content": "second"}]})

        # Both runs should start citation numbering from E1.
        first_prompt = model.ainvoke.call_args_list[0].args[0][1]["content"]
        second_prompt = model.ainvoke.call_args_list[1].args[0][1]["content"]
        assert "[E1]" in first_prompt
        assert "[E1]" in second_prompt

    async def test_simple_agent_passes_filters_to_search(self) -> None:
        """_SimpleAgent scopes its search with the given filters."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        result = SearchResult(item=ent, score=0.9, method="entity")
        engine = MagicMock()
        engine.search = AsyncMock(return_value=[result])
        filters = SearchFilters(document_ids=["doc-1"])
        model = AsyncMock(ainvoke=AsyncMock(return_value=MagicMock(text="answer")))

        agent = _SimpleAgent(model=model, engine=engine, filters=filters)
        await agent.ainvoke({"messages": [{"role": "user", "content": "question"}]})

        call = engine.search.await_args
        if call is None:
            pytest.fail("engine.search was not awaited")
        _, kwargs = call
        assert kwargs["filters"] == filters

    async def test_simple_agent_searches_hybrid_directly(self) -> None:
        """_SimpleAgent never touches the tool layer."""
        from agrag.retrieval.recipes import HYBRID  # noqa: PLC0415

        engine = MagicMock()
        engine.search = AsyncMock(return_value=[])

        agent = _SimpleAgent(model=MagicMock(), engine=engine)
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        call = engine.search.await_args
        if call is None:
            pytest.fail("engine.search was not awaited")
        args, _ = call
        assert args[1] is HYBRID

    async def test_simple_agent_synthesizes_answer_via_model_call(self) -> None:
        """_SimpleAgent calls the model to synthesize the returned answer."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        result = SearchResult(item=ent, score=0.9, method="entity")
        engine = MagicMock()
        engine.search = AsyncMock(return_value=[result])
        model = AsyncMock(
            ainvoke=AsyncMock(return_value=MagicMock(text="cited answer"))
        )

        agent = _SimpleAgent(model=model, engine=engine)
        result_data = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "who is Alice?"}]}
        )

        model.ainvoke.assert_awaited_once()
        prompt = model.ainvoke.call_args.args[0][1]["content"]
        assert "who is Alice?" in prompt
        assert "[E1]" in prompt
        assert result_data["messages"][0]["content"] == "cited answer"

    async def test_simple_agent_skips_model_call_when_no_evidence(self) -> None:
        """_SimpleAgent never calls the model when search returns nothing."""
        engine = MagicMock()
        engine.search = AsyncMock(return_value=[])
        model = AsyncMock()

        agent = _SimpleAgent(model=model, engine=engine)
        result_data = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "q"}]}
        )

        model.ainvoke.assert_not_awaited()
        assert result_data["messages"][0]["content"] == "No relevant evidence found."

    async def test_ainvoke_passes_subagents_not_flat_tools(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The graph gets subagents= and no flat tools= kwarg."""
        captured: dict = {}
        _capture_deepagents(monkeypatch, captured)

        agent = _RunScopedAgent(
            engine=_engine(),
            model=MagicMock(),
            settings=AgentSettings(),
        )
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        assert "subagents" in captured
        subagents = captured["subagents"]
        assert [spec["name"] for spec in subagents] == ["researcher", "verifier"]
        assert "tools" not in captured

    async def test_verifier_spec_has_empty_tools_key_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The verifier's tools key is present and empty, not omitted."""
        captured: dict = {}
        _capture_deepagents(monkeypatch, captured)

        agent = _RunScopedAgent(
            engine=_engine(),
            model=MagicMock(),
            settings=AgentSettings(),
        )
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        verifier = captured["subagents"][1]
        assert "tools" in verifier
        assert verifier["tools"] == []

    async def test_verifier_response_format_is_verification_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The verifier returns a structured VerificationResult."""
        captured: dict = {}
        _capture_deepagents(monkeypatch, captured)

        agent = _RunScopedAgent(
            engine=_engine(),
            model=MagicMock(),
            settings=AgentSettings(),
        )
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        verifier = captured["subagents"][1]
        assert verifier["response_format"] is VerificationResult

    async def test_both_specs_carry_explicit_middleware(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Isolated subagents get their own middleware key."""
        sentinel = object()
        captured: dict = {}
        _capture_deepagents(monkeypatch, captured)

        agent = _RunScopedAgent(
            engine=_engine(),
            model=MagicMock(),
            settings=AgentSettings(),
            middleware=[sentinel],
        )
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        researcher, verifier = captured["subagents"]
        assert "middleware" in researcher
        assert "middleware" in verifier

    async def test_researcher_system_prompt_carries_schema_summary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The researcher prompt is substituted, placeholder removed."""
        captured: dict = {}
        _capture_deepagents(monkeypatch, captured)

        agent = _RunScopedAgent(
            engine=_engine(),
            model=MagicMock(),
            settings=AgentSettings(),
        )
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        researcher = captured["subagents"][0]
        assert "{schema_summary}" not in researcher["system_prompt"]
        assert researcher["system_prompt"] != ""

    async def test_planner_system_prompt_carries_attempt_count(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The planner prompt states the configured attempt count."""
        captured: dict = {}
        _capture_deepagents(monkeypatch, captured)

        agent = _RunScopedAgent(
            engine=_engine(),
            model=MagicMock(),
            settings=AgentSettings(max_research_attempts=7),
        )
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        assert "7 post-verifier research retries" in captured["system_prompt"]

    async def test_ainvoke_calls_ensure_harness_profile_with_configured_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Every ainvoke registers the harness profile for its provider."""
        captured: dict = {}
        _capture_deepagents(monkeypatch, captured)

        def fake_ensure(provider: str) -> None:
            captured["provider"] = provider

        monkeypatch.setattr("agrag.agents.build.ensure_harness_profile", fake_ensure)

        agent = _RunScopedAgent(
            engine=_engine(),
            model=MagicMock(),
            settings=AgentSettings(),
            model_provider="openai",
        )
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        assert captured["provider"] == "openai"

    async def test_limiter_is_fresh_per_ainvoke_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two ainvoke calls get distinct ResearchAttemptLimiter objects."""
        captured_first: dict = {}
        captured_second: dict = {}
        captured_by_call = [captured_first, captured_second]

        real_find_spec = importlib.util.find_spec

        def with_deepagents(name: str, *args: Any, **kwargs: Any) -> Any:
            return real_find_spec(name, *args, **kwargs)

        monkeypatch.setattr(importlib.util, "find_spec", with_deepagents)

        call_index = 0

        class _FakeAgent:
            async def ainvoke(
                self, input_data: dict, config: dict | None = None
            ) -> dict:
                return {"messages": []}

        def fake_create_deep_agent(**kwargs: object) -> _FakeAgent:
            nonlocal call_index
            captured_by_call[call_index].update(kwargs)
            call_index += 1
            return _FakeAgent()

        fake_deepagents = types.SimpleNamespace(
            create_deep_agent=fake_create_deep_agent,
            HarnessProfile=MagicMock(),
            GeneralPurposeSubagentProfile=MagicMock(),
            register_harness_profile=MagicMock(),
        )
        monkeypatch.setitem(sys.modules, "deepagents", fake_deepagents)

        agent = _RunScopedAgent(
            engine=_engine(),
            model=MagicMock(),
            settings=AgentSettings(),
        )
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        limiters = [
            middleware
            for captured in captured_by_call
            for middleware in captured["middleware"]
            if isinstance(middleware, ResearchAttemptLimiter)
        ]
        assert len(limiters) == 2
        assert limiters[0] is not limiters[1]

    async def test_run_scoped_agent_rebuilds_tools_with_filters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RunScopedAgent forwards filters to the per-run tool set."""
        captured: dict = {}
        _capture_deepagents(monkeypatch, captured)

        ent = Entity(id=uuid4(), label="Person", name="Alice")
        result = SearchResult(item=ent, score=0.9, method="entity")
        engine = _engine()
        engine.search = AsyncMock(return_value=[result])
        filters = SearchFilters(document_ids=["doc-1"])

        agent = _RunScopedAgent(
            engine=engine,
            model=MagicMock(),
            settings=AgentSettings(),
            filters=filters,
        )
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        researcher = captured["subagents"][0]
        tools = researcher["tools"]
        search_tool = next(tool for tool in tools if tool.name == "search_source_text")
        await search_tool.ainvoke({"query": "test"})
        call = engine.search.await_args
        if call is None:
            pytest.fail("engine.search was not awaited")
        _, kwargs = call
        assert kwargs["filters"] == filters
        assert kwargs["filters"] is not filters

    async def test_run_scoped_agent_applies_recursion_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RunScopedAgent forwards AgentSettings.recursion_limit."""
        captured: dict = {}
        _capture_deepagents(monkeypatch, captured)

        agent = _RunScopedAgent(
            engine=_engine(),
            model=MagicMock(),
            settings=AgentSettings(recursion_limit=7),
        )
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        assert captured["config"] == {"recursion_limit": 7}

    async def test_run_scoped_agent_passes_middleware(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The planner's middleware carries the shared list and the limiter."""
        sentinel = object()
        captured: dict = {}
        _capture_deepagents(monkeypatch, captured)

        agent = _RunScopedAgent(
            engine=_engine(),
            model=MagicMock(),
            settings=AgentSettings(),
            middleware=[sentinel],
        )
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        middleware = captured["middleware"]
        assert middleware[0] is sentinel
        assert isinstance(middleware[1], ResearchAttemptLimiter)
