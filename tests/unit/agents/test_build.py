"""Tests for build_agent."""

from unittest.mock import MagicMock

import pytest

from agrag.agents.build import build_agent
from agrag.agents.settings import AgentLLMSettings
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
