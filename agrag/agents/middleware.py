"""Agent middleware for composing models and bounding the research loop."""

import re
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
    hook_config,
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from agrag.agents.ledger import Ledger


_VERDICT_REMINDER = "Answer only by calling the VerificationResult tool."

# The prefixes of the citation keys that Ledger assigns.
_CITATION_KEY = re.compile(r"\b[EGRCVX]\d+\b")


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


class VerifierEvidenceMiddleware(AgentMiddleware):
    """Give the verifier the evidence text behind each key a task cites.

    The planner writes the verifier's task from the researcher's summary, so the
    task carries citation keys and no evidence. The verifier has no tools, so it
    cannot check that a key supports a claim. This middleware appends the ledger
    text of every key in a verifier task, and marks a key that this run never
    retrieved. Tasks for other subagents pass through unchanged.

    Holds a run's ``Ledger``, so construct one per ``ainvoke`` call.
    """

    def __init__(self, ledger: Ledger) -> None:
        """Construct the middleware.

        Args:
            ledger: The ledger of the run whose keys the planner cites.
        """
        self._ledger = ledger

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        """Append an Evidence block to a verifier task, then run the call.

        Args:
            request: The intercepted tool call request.
            handler: The rest of the tool-call pipeline.

        Returns:
            The handler's result.
        """
        args = request.tool_call.get("args", {})
        if request.tool_call.get("name") != "task" or (
            args.get("subagent_type") != "verifier"
        ):
            return await handler(request)
        description = args.get("description", "")
        keys = list(dict.fromkeys(_CITATION_KEY.findall(description)))
        if not keys:
            return await handler(request)
        evidence = "\n".join(self._evidence_line(key) for key in keys)
        task = {**args, "description": f"{description}\n\nEvidence:\n{evidence}"}
        return await handler(
            request.override(tool_call={**request.tool_call, "args": task})
        )

    def _evidence_line(self, key: str) -> str:
        """Return the ledger text for a key, or a note that it is missing."""
        result = self._ledger.resolve(key)
        if result is None:
            return f"[{key}] Not in the evidence retrieved in this run."
        return self._ledger.render(result)


class HideToolsMiddleware(AgentMiddleware):
    """Remove tools by name from every model request.

    DeepAgents gives each subagent its filesystem tools, even when the spec
    lists none. A role that needs no tools, such as the verifier, hides them so
    the model can only answer through its structured output.
    """

    def __init__(self, names: frozenset[str]) -> None:
        """Construct the middleware.

        Args:
            names: The tool names to remove.
        """
        self._names = names

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> Any:
        """Run the call with the named tools removed from the request."""
        kept = [t for t in request.tools if getattr(t, "name", None) not in self._names]
        return await handler(request.override(tools=kept))


class RequireVerdictMiddleware(AgentMiddleware):
    """Ask again when the verifier answers in prose instead of with its verdict.

    A subagent that has tools stops as soon as the model replies without a tool
    call, even when the reply is not the structured response. The planner then
    reads prose where it expects a ``VerificationResult``. This middleware sends a
    short reminder and calls the model again, up to ``max_reminders`` times in one
    subagent run, and then lets the run end as before.
    """

    def __init__(self, max_reminders: int = 2) -> None:
        """Construct the middleware.

        Args:
            max_reminders: How many reminders one subagent run may send.
        """
        self._max_reminders = max_reminders

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        """Send a reminder and jump back to the model after a prose reply."""
        if state.get("structured_response") is not None:
            return None
        messages = state["messages"]
        last = messages[-1]
        if not isinstance(last, AIMessage) or last.tool_calls:
            return None
        reminders = sum(
            isinstance(m, HumanMessage) and m.content == _VERDICT_REMINDER
            for m in messages
        )
        if reminders >= self._max_reminders:
            return None
        return {"messages": [HumanMessage(_VERDICT_REMINDER)], "jump_to": "model"}
