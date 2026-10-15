"""Checks multi-model rotation retained by the single agent."""

import pytest
from langchain.agents.middleware.types import ModelRequest, ModelResponse

from agrag.agents.middleware import RoundRobinModelMiddleware


def _request(model: object) -> ModelRequest:
    """Build a minimal model request."""
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
    """The model middleware rotates across configured clients."""

    def test_rotates_and_wraps_across_models(self) -> None:
        """Each request uses the next model and wraps to the first."""
        first, second = object(), object()
        middleware = RoundRobinModelMiddleware([first, second])
        seen: list[object] = []

        def handler(request: ModelRequest) -> ModelResponse:
            seen.append(request.model)
            return "ok"  # ty: ignore[invalid-return-type]  # type: ignore[return-value]

        for _ in range(3):
            middleware.wrap_model_call(_request(first), handler)

        assert seen == [first, second, first]

    def test_rejects_empty_model_list(self) -> None:
        """An empty model list cannot be rotated."""
        with pytest.raises(
            ValueError,
            match="RoundRobinModelMiddleware needs at least one model",
        ):
            RoundRobinModelMiddleware([])
