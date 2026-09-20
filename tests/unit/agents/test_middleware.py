"""Tests for the agent middleware in agrag.agents.middleware.

Covers RoundRobinModelMiddleware's model rotation and
ResearchAttemptLimiter's retry budget: researcher delegations before the
first verifier call are never counted, post-verification retries are
counted and capped, and verifier or non-task calls always pass through.
Uses minimal request builders rather than a real LangChain agent run.
"""

from unittest.mock import AsyncMock

import pytest
from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest

from agrag.agents.middleware import ResearchAttemptLimiter, RoundRobinModelMiddleware


def _request(model: object) -> ModelRequest:
    """Build a minimal ModelRequest for middleware tests."""
    return ModelRequest(
        model=model,  # type: ignore[arg-type]
        messages=[],
        system_message=None,
        tool_choice=None,
        tools=[],
        response_format=None,
        state={"messages": []},
        runtime=None,
        model_settings={},
    )


class TestRoundRobinModelMiddleware:
    """RoundRobinModelMiddleware rotates models per model call."""

    def test_rotates_across_models_in_order(self) -> None:
        """Each call overrides the request with the next model in order."""
        first, second = object(), object()
        middleware = RoundRobinModelMiddleware([first, second])
        seen: list[object] = []

        def handler(request: ModelRequest) -> object:
            seen.append(request.model)
            return "ok"

        middleware.wrap_model_call(_request(first), handler)
        middleware.wrap_model_call(_request(first), handler)

        assert seen == [first, second]

    def test_wraps_around_after_last_model(self) -> None:
        """Rotation wraps back to the first model after the last."""
        first, second = object(), object()
        middleware = RoundRobinModelMiddleware([first, second])
        seen: list[object] = []

        def handler(request: ModelRequest) -> object:
            seen.append(request.model)
            return "ok"

        for _ in range(3):
            middleware.wrap_model_call(_request(first), handler)

        assert seen == [first, second, first]

    async def test_async_calls_rotate_across_models(self) -> None:
        """awrap_model_call advances the same rotation as sync calls."""
        first, second = object(), object()
        middleware = RoundRobinModelMiddleware([first, second])
        seen: list[object] = []

        async def handler(request: ModelRequest) -> object:
            seen.append(request.model)
            return "ok"

        await middleware.awrap_model_call(_request(first), handler)
        await middleware.awrap_model_call(_request(first), handler)

        assert seen == [first, second]

    def test_preserves_other_request_fields(self) -> None:
        """Only the model is overridden; the rest of the request is kept."""
        first, second = object(), object()
        request = _request(first)
        middleware = RoundRobinModelMiddleware([second])

        def handler(overridden: ModelRequest) -> object:
            assert overridden.messages == request.messages
            assert overridden.tools == request.tools
            assert overridden.model is second
            return "ok"

        middleware.wrap_model_call(request, handler)


def _tool_call_request(name: str, args: dict | None = None) -> object:
    """Build a minimal ToolCallRequest for middleware tests."""
    return ToolCallRequest(
        tool_call={"name": name, "args": args or {}, "id": "call-1"},
        tool=None,
        state={"messages": []},
        runtime=None,
    )


class TestResearchAttemptLimiter:
    """ResearchAttemptLimiter caps post-verification researcher retries."""

    def _middleware(self, max_attempts: int) -> ResearchAttemptLimiter:
        """Build a limiter with an async handler-recording helper."""
        return ResearchAttemptLimiter(max_attempts)

    @staticmethod
    def _handler() -> AsyncMock:
        """Return an async handler the limiter can call or skip."""
        return AsyncMock(return_value=ToolMessage(content="ran", tool_call_id="x"))

    async def test_researcher_delegations_before_verifier_are_never_counted(
        self,
    ) -> None:
        """The initial decomposition pass is not what the cap bounds."""
        limiter = self._middleware(3)
        handler = self._handler()

        for _ in range(4):
            await limiter.awrap_tool_call(
                _tool_call_request("task", {"subagent_type": "researcher"}),
                handler,
            )

        assert handler.await_count == 4

    async def test_researcher_delegations_after_verifier_are_counted_and_capped(
        self,
    ) -> None:
        """The full sequence: initial pass, verifier, then capped retries."""
        limiter = self._middleware(2)
        handler = self._handler()

        async def delegate(subagent_type: str) -> None:
            await limiter.awrap_tool_call(
                _tool_call_request("task", {"subagent_type": subagent_type}),
                handler,
            )

        for _ in range(3):
            await delegate("researcher")
        await delegate("verifier")
        for _ in range(3):
            await delegate("researcher")

        assert handler.await_count == 6

    async def test_the_retry_past_the_cap_returns_the_limit_message(
        self,
    ) -> None:
        """The over-budget delegation gets the limit-reached ToolMessage."""
        limiter = self._middleware(2)
        handler = self._handler()

        async def delegate(subagent_type: str) -> object:
            return await limiter.awrap_tool_call(
                _tool_call_request("task", {"subagent_type": subagent_type}),
                handler,
            )

        await delegate("verifier")
        await delegate("researcher")
        await delegate("researcher")
        result = await delegate("researcher")

        assert isinstance(result, ToolMessage)
        assert "limit reached" in result.content

    async def test_call_past_limit_short_circuits_without_calling_handler(
        self,
    ) -> None:
        """The over-budget retry gets a ToolMessage, handler not called."""
        limiter = self._middleware(1)
        handler = self._handler()

        await limiter.awrap_tool_call(
            _tool_call_request("task", {"subagent_type": "verifier"}), handler
        )
        await limiter.awrap_tool_call(
            _tool_call_request("task", {"subagent_type": "researcher"}), handler
        )
        handler.reset_mock()

        result = await limiter.awrap_tool_call(
            _tool_call_request("task", {"subagent_type": "researcher"}), handler
        )

        handler.assert_not_awaited()
        assert isinstance(result, ToolMessage)
        assert "limit reached" in result.content
        assert result.tool_call_id == "call-1"

    async def test_verifier_calls_always_reach_handler_and_are_never_limited(
        self,
    ) -> None:
        """Verifier delegations pass through no matter how many."""
        limiter = self._middleware(1)
        handler = self._handler()

        for _ in range(5):
            await limiter.awrap_tool_call(
                _tool_call_request("task", {"subagent_type": "verifier"}),
                handler,
            )

        assert handler.await_count == 5

    async def test_non_task_tool_calls_never_counted(self) -> None:
        """Regular tools neither flip the verifier flag nor spend budget."""
        limiter = self._middleware(1)
        handler = self._handler()

        for _ in range(5):
            await limiter.awrap_tool_call(
                _tool_call_request("search_source_text", {"query": "q"}), handler
            )
        await limiter.awrap_tool_call(
            _tool_call_request("task", {"subagent_type": "verifier"}), handler
        )
        for _ in range(5):
            await limiter.awrap_tool_call(
                _tool_call_request("look_up_entity", {"query": "q"}), handler
            )

        assert handler.await_count == 11

    def test_rejects_empty_model_list(self) -> None:
        """An empty model list raises ValueError."""
        with pytest.raises(ValueError, match="at least one model"):
            RoundRobinModelMiddleware([])
