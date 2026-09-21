"""Agent middleware for composing models and bounding the research loop."""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
)
from langchain_core.messages import ToolMessage
from langgraph.types import Command


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


class ResearchAttemptLimiter(AgentMiddleware):
    """Cap how many times the planner may re-delegate after verification.

    Intercepts the generated ``task`` tool call and counts only
    delegations to the researcher that follow at least one prior
    delegation to the verifier. Once the cap is reached, short-circuits
    with a message telling the planner to synthesize from evidence
    already gathered, instead of letting the graph run until
    ``recursion_limit`` aborts it with an opaque ``GraphRecursionError``.

    Holds per-run state, so construct one per ``ainvoke`` call, never
    shared across runs.
    """

    def __init__(self, max_attempts: int) -> None:
        """Construct the limiter.

        Args:
            max_attempts: How many researcher re-delegations after the
                first verifier consultation the planner may make.

        Raises:
            ValueError: max_attempts is negative.
        """
        if max_attempts < 0:
            raise ValueError("max_attempts must be non-negative")
        self._max_attempts = max_attempts
        self._attempts = 0
        self._verifier_consulted = False

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        """Count or short-circuit one task tool call.

        Args:
            request: The intercepted tool call request.
            handler: The rest of the tool-call pipeline.

        Returns:
            The handler's result, or the limit-reached ToolMessage when
            the planner has spent its retry budget.
        """
        name = request.tool_call.get("name")
        subagent_type = request.tool_call.get("args", {}).get("subagent_type")

        if name == "task" and subagent_type == "verifier":
            self._verifier_consulted = True
            return await handler(request)

        is_retry_delegation = (
            name == "task"
            and subagent_type == "researcher"
            and self._verifier_consulted
        )
        if is_retry_delegation:
            if self._attempts >= self._max_attempts:
                return ToolMessage(
                    content=(
                        "Research attempt limit reached. Synthesize your "
                        "answer from the evidence already gathered."
                    ),
                    tool_call_id=request.tool_call["id"],
                )
            self._attempts += 1
        return await handler(request)
