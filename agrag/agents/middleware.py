"""Agent middleware for composing multiple chat models per strategy."""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)


class RoundRobinModelMiddleware(AgentMiddleware):
    """Rotate across the configured chat models, one model per call.

    Overrides the request's model on every model call so requests are
    distributed across all configured clients in order.
    """

    def __init__(self, models: list[Any]) -> None:
        """Construct the middleware.

        Args:
            models: Chat models to rotate across, in configuration
                order. Must be non-empty.

        Raises:
            ValueError: models is empty.
        """
        if not models:
            raise ValueError("RoundRobinModelMiddleware needs at least one model.")
        self._models = models
        self._next_index = 0

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> Any:
        """Run the call against the next model in rotation."""
        return handler(request.override(model=self._next_model()))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> Any:
        """Run the call against the next model in rotation."""
        return await handler(request.override(model=self._next_model()))

    def _next_model(self) -> Any:
        """Return the next model in rotation, wrapping at the end."""
        model = self._models[self._next_index % len(self._models)]
        self._next_index += 1
        return model
