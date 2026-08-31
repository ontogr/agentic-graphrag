"""Tests for build_agent."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from agrag.agents.build import _SimpleAgent, build_agent
from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult
from agrag.llm.client_config import LLMClientConfig


class TestBuildAgent:
    """build_agent constructs an agent graph."""

    def test_builds_simple_agent_without_deepagents(self) -> None:
        """Without deepagents, build_agent returns _SimpleAgent."""
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
        assert agent is not None
        assert hasattr(agent, "ainvoke")

    async def test_simple_agent_creates_fresh_ledger_per_run(self) -> None:
        """Each ainvoke call gets a fresh Ledger."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        result = SearchResult(item=ent, score=0.9, method="entity")
        engine = MagicMock()
        engine.search = AsyncMock(return_value=[result])

        agent = _SimpleAgent(
            model=MagicMock(),
            engine=engine,
            settings=AgentSettings(),
        )

        r1 = await agent.ainvoke({"messages": [{"role": "user", "content": "first"}]})
        r2 = await agent.ainvoke({"messages": [{"role": "user", "content": "second"}]})

        # Both runs should start citation numbering from E1.
        assert "[E1]" in r1["messages"][0]["content"]
        assert "[E1]" in r2["messages"][0]["content"]
