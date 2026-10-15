"""Checks that the agent builder rejects a missing optional runtime."""

from unittest.mock import MagicMock

import pytest

from agrag.agents import AgentMissingExtraError
from agrag.agents.build import build_agent
from agrag.agents.settings import AgentLLMSettings


class TestBuildAgent:
    """The public builder requires DeepAgents instead of substituting behavior."""

    def test_missing_agents_extra_fails_at_build_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No fallback agent is returned when DeepAgents is unavailable."""
        monkeypatch.setattr(
            "agrag.agents.build.importlib.util.find_spec", lambda _: None
        )

        with pytest.raises(AgentMissingExtraError, match="agents"):
            build_agent(
                graph_store=MagicMock(),
                embedder=MagicMock(),
                scope=frozenset({"document"}),
                project_id="project",
                agent_id="agent",
                llm_settings=AgentLLMSettings(
                    clients=[
                        {
                            "name": "test",
                            "provider": "openai-generic",
                            "model": "test-model",
                        }
                    ]
                ),
            )
