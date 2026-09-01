"""Tests for RoundRobinModelMiddleware."""

import pytest
from langchain.agents.middleware.types import ModelRequest

from agrag.agents.middleware import RoundRobinModelMiddleware


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

    def test_rejects_empty_model_list(self) -> None:
        """An empty model list raises ValueError."""
        with pytest.raises(ValueError, match="at least one model"):
            RoundRobinModelMiddleware([])
