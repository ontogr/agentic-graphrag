"""Middleware for composing configured chat models."""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)

from agrag.common.data_models.task import EventKind


class RoundRobinModelMiddleware(AgentMiddleware):
    """Rotate model requests across configured clients."""

    def __init__(self, models: list[Any]) -> None:
        """Create a rotating model selector."""
        if not models:
            raise ValueError("RoundRobinModelMiddleware needs at least one model.")
        self._models = models
        self._next_index = 0

    def _next_model(self) -> Any:
        """Return the next model in configuration order."""
        model = self._models[self._next_index % len(self._models)]
        self._next_index += 1
        return model

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> Any:
        """Invoke the next model in the rotation."""
        return handler(request.override(model=self._next_model()))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> Any:
        """Invoke the next model in the rotation asynchronously."""
        return await handler(request.override(model=self._next_model()))


class TaskEventMiddleware(AgentMiddleware):
    """Persist assistant messages as the model produces them."""

    def __init__(self, memory: Any, task_name: str, run_state: Any) -> None:
        """Bind model message capture to one task run."""
        self._memory = memory
        self._task_name = task_name
        self._run_state = run_state

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Record the assistant response before any tool it requests runs."""
        response = await handler(request)
        for message in response.result:
            result = await self._memory.record_event(
                self._task_name,
                EventKind.MESSAGE,
                role="assistant",
                payload=_message_text(message),
            )
            self._run_state.recording_failed |= not result.recorded
        return response


def _message_text(message: Any) -> str:
    """Return a model message's content for the task event."""
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else str(content)
