"""Tests for build_agent."""

import importlib.util
import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from agrag.agents.build import _RunScopedAgent, _SimpleAgent, build_agent
from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult
from agrag.llm.client_config import LLMClientConfig
from agrag.retrieval.filters import SearchFilters


class TestBuildAgent:
    """build_agent constructs an agent graph."""

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
        engine = MagicMock()
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
            agent = build_agent(engine=engine, llm_settings=settings)
        except ImportError:
            pytest.skip("langchain-openai not installed")
        assert isinstance(agent, _SimpleAgent)

    async def test_simple_agent_creates_fresh_ledger_per_run(self) -> None:
        """Each ainvoke call gets a fresh Ledger."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        result = SearchResult(item=ent, score=0.9, method="entity")
        engine = MagicMock()
        engine.search = AsyncMock(return_value=[result])

        agent = _SimpleAgent(
            model=MagicMock(),
            engine=engine,
        )

        r1 = await agent.ainvoke({"messages": [{"role": "user", "content": "first"}]})
        r2 = await agent.ainvoke({"messages": [{"role": "user", "content": "second"}]})

        # Both runs should start citation numbering from E1.
        assert "[E1]" in r1["messages"][0]["content"]
        assert "[E1]" in r2["messages"][0]["content"]

    async def test_simple_agent_passes_filters_to_search(self) -> None:
        """_SimpleAgent scopes its search with the given filters."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        result = SearchResult(item=ent, score=0.9, method="entity")
        engine = MagicMock()
        engine.search = AsyncMock(return_value=[result])
        filters = SearchFilters(document_ids=["doc-1"])

        agent = _SimpleAgent(model=MagicMock(), engine=engine, filters=filters)
        await agent.ainvoke({"messages": [{"role": "user", "content": "question"}]})

        call = engine.search.await_args
        if call is None:
            pytest.fail("engine.search was not awaited")
        _, kwargs = call
        assert kwargs["filters"] is filters

    async def test_run_scoped_agent_rebuilds_tools_with_filters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RunScopedAgent forwards filters to the per-run tool set."""
        captured: dict = {}

        class _FakeAgent:
            async def ainvoke(
                self, input_data: dict, config: dict | None = None
            ) -> dict:
                return {"messages": []}

        def fake_create_deep_agent(**kwargs: object) -> _FakeAgent:
            captured["tools"] = kwargs.get("tools")
            return _FakeAgent()

        fake_deepagents = types.SimpleNamespace(
            create_deep_agent=fake_create_deep_agent
        )
        monkeypatch.setitem(sys.modules, "deepagents", fake_deepagents)

        ent = Entity(id=uuid4(), label="Person", name="Alice")
        result = SearchResult(item=ent, score=0.9, method="entity")
        engine = MagicMock()
        engine.search = AsyncMock(return_value=[result])
        filters = SearchFilters(document_ids=["doc-1"])

        agent = _RunScopedAgent(
            engine=engine,
            model=MagicMock(),
            settings=AgentSettings(),
            filters=filters,
        )
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        tools = captured["tools"]
        await tools[0].ainvoke({"query": "test"})
        call = engine.search.await_args
        if call is None:
            pytest.fail("engine.search was not awaited")
        _, kwargs = call
        assert kwargs["filters"] is filters

    async def test_run_scoped_agent_applies_recursion_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RunScopedAgent forwards AgentSettings.recursion_limit."""
        captured: dict = {}

        class _FakeAgent:
            async def ainvoke(
                self, input_data: dict, config: dict | None = None
            ) -> dict:
                captured["config"] = config
                return {"messages": []}

        fake_deepagents = types.SimpleNamespace(
            create_deep_agent=lambda **kwargs: _FakeAgent()
        )
        monkeypatch.setitem(sys.modules, "deepagents", fake_deepagents)

        agent = _RunScopedAgent(
            engine=MagicMock(),
            model=MagicMock(),
            settings=AgentSettings(recursion_limit=7),
        )
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        assert captured["config"] == {"recursion_limit": 7}

    async def test_run_scoped_agent_passes_middleware(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RunScopedAgent forwards model middleware to the rebuilt agent."""
        sentinel = object()
        captured: dict = {}

        class _FakeAgent:
            async def ainvoke(
                self, input_data: dict, config: dict | None = None
            ) -> dict:
                return {"messages": []}

        def fake_create_deep_agent(**kwargs: object) -> _FakeAgent:
            captured["middleware"] = kwargs.get("middleware")
            return _FakeAgent()

        fake_deepagents = types.SimpleNamespace(
            create_deep_agent=fake_create_deep_agent
        )
        monkeypatch.setitem(sys.modules, "deepagents", fake_deepagents)

        agent = _RunScopedAgent(
            engine=MagicMock(),
            model=MagicMock(),
            settings=AgentSettings(),
            middleware=[sentinel],
        )
        await agent.ainvoke({"messages": [{"role": "user", "content": "q"}]})

        assert captured["middleware"] == [sentinel]
