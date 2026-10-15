"""Middleware for composing configured chat models and capturing task events."""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)

from agrag.common.data_models.task import EventKind


@dataclass
class RunState:
    """Mutable facts accumulated by tools and middleware during one run.

    Attributes:
        max_tool_calls: Tool calls allowed in the run.
        tool_calls: Tool calls admitted so far.
        budget_exhausted: Whether the run reached its tool-call bound.
        recording_failed: Whether an event or decision write did not complete.
        recording_failures: Descriptions of the writes that did not complete.
        retrieval_failed: Whether a search leg failed or a result was truncated.
        fetched_ids: Evidence ids fetched in this run with complete text.
        fetches: Fetch outcomes by evidence id.
    """

    max_tool_calls: int
    tool_calls: int = 0
    budget_exhausted: bool = False
    recording_failed: bool = False
    recording_failures: list[str] = field(default_factory=list)
    retrieval_failed: bool = False
    fetched_ids: list[str] = field(default_factory=list)
    fetches: dict[str, Any] = field(default_factory=dict)

    def fail_recording(self, description: str) -> None:
        """Mark that a write did not complete and keep its description."""
        self.recording_failed = True
        self.recording_failures.append(description)


async def record_event_or_flag(
    memory: Any,
    task_name: str,
    run_state: RunState,
    kind: EventKind,
    *,
    payload: str,
    role: str | None = None,
    name: str | None = None,
) -> Any:
    """Append one event, retry it once, and flag the run if it still fails.

    The retry reuses one request id, so a write that committed before the
    error returns its stored result instead of a second event.

    Args:
        memory: The task memory that holds the event.
        task_name: The task the event belongs to.
        run_state: The run whose failure flag is set on a lasting error.
        kind: The kind of event.
        payload: The event text.
        role: The speaker role for a message, or None.
        name: The tool or source name for a tool event, or None.

    Returns:
        The stored event, or None when the write did not complete.
    """
    request_id = uuid4().hex
    error = "not recorded"
    for _ in range(2):
        try:
            result = await memory.record_event(
                task_name,
                kind,
                role=role,
                name=name,
                payload=payload,
                request_id=request_id,
            )
        except Exception as exc:  # noqa: BLE001 - a store error must end up in the result
            error = repr(exc)
            continue
        if result.recorded:
            return result.event
        error = str(result.error)
    run_state.fail_recording(f"{kind.value} {name or role or ''}: {error}")
    return None


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
    """Persist assistant messages, tool calls and tool results as task events."""

    def __init__(self, memory: Any, task_name: str, run_state: RunState) -> None:
        """Bind event capture to one task run."""
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
            await record_event_or_flag(
                self._memory,
                self._task_name,
                self._run_state,
                EventKind.MESSAGE,
                role="assistant",
                payload=_message_text(message),
            )
        return response

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """Record a tool call, then its result or the error that replaced it."""
        call = request.tool_call
        await record_event_or_flag(
            self._memory,
            self._task_name,
            self._run_state,
            EventKind.TOOL_CALL,
            name=call["name"],
            payload=json.dumps(call["args"], default=str),
        )
        try:
            result = await handler(request)
        except Exception as exc:
            await record_event_or_flag(
                self._memory,
                self._task_name,
                self._run_state,
                EventKind.TOOL_RESULT,
                name=call["name"],
                payload=f"error: {type(exc).__name__}: {exc}",
            )
            raise
        await record_event_or_flag(
            self._memory,
            self._task_name,
            self._run_state,
            EventKind.TOOL_RESULT,
            name=call["name"],
            payload=_tool_result_text(result),
        )
        return result


def _message_text(message: Any) -> str:
    """Return a model message's content for the task event."""
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else str(content)


def _tool_result_text(result: Any) -> str:
    """Return a tool's message content, or its text form for other returns."""
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    return str(result)
