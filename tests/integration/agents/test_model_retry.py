"""Agent chat models retry rate-limited calls up to the configured count.

Each test points the chat model built by ``build_chat_model`` at the local fake
endpoint in ``rate-limited`` mode, which answers HTTP 429 to its first three
requests and then serves a completion. The provider library's own backoff runs
for real, so a call that retries three times waits a few seconds in total. The
OpenAI default of two retries cannot reach the completion, so the first test
fails if ``max_retries`` is ignored.
"""

from typing import Any

import openai
import pytest
from langchain_core.messages import HumanMessage

from agrag.agents.model import build_chat_model
from agrag.llm.client_config import LLMClientConfig
from tests.integration.llm._local_llm import SECRET, LocalLLM


@pytest.fixture
def local() -> Any:
    """A running fake endpoint that rate-limits its first requests."""
    server = LocalLLM()
    yield server
    server.close()


def _agent_model(server: LocalLLM, max_retries: int | None) -> Any:
    """Build the agent chat model for the fake endpoint's rate-limited mode."""
    config = LLMClientConfig(
        name="agent",
        provider="openai-generic",
        model="requested-model",
        api_key=SECRET,
        base_url=server.url("rate-limited"),
    )
    return build_chat_model(config, max_retries=max_retries)


class TestModelRetry:
    """Agent model calls retry HTTP 429 responses up to max_retries."""

    async def test_call_succeeds_once_retries_outlast_the_rate_limit(
        self, local: LocalLLM
    ) -> None:
        """Three rate-limited attempts are retried when max_retries is three."""
        model = _agent_model(local, max_retries=3)

        reply = await model.ainvoke([HumanMessage(content="Reply with OK.")])

        assert reply.content == "served after retries"
        assert len(local.received) == 4

    async def test_rate_limit_reaches_the_caller_without_retries(
        self, local: LocalLLM
    ) -> None:
        """With max_retries set to zero, the first HTTP 429 raises."""
        model = _agent_model(local, max_retries=0)

        with pytest.raises(openai.RateLimitError):
            await model.ainvoke([HumanMessage(content="Reply with OK.")])

        assert len(local.received) == 1
