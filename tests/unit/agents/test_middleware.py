"""Tests for the agent middleware in agrag.agents.middleware.

Covers RoundRobinModelMiddleware's model rotation,
ResearchAttemptLimiter's retry budget (researcher delegations before the
first verifier call are never counted, post-verification retries are
counted and capped, and verifier or non-task calls always pass through) and
VerifierEvidenceMiddleware's evidence block on verifier tasks and
HideToolsMiddleware's removal of tools from model requests and
RequireVerdictMiddleware's reminders when a model answers without the verdict tool.
Uses minimal request builders rather than a real LangChain agent run.
"""

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware.types import ModelRequest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import ToolCallRequest

from agrag.agents.ledger import Ledger
from agrag.agents.middleware import (
    HideToolsMiddleware,
    RequireVerdictMiddleware,
    ResearchAttemptLimiter,
    RoundRobinModelMiddleware,
    VerifierEvidenceMiddleware,
)
from agrag.agents.verification import VerificationResult
from agrag.common.data_models.chunk import Chunk, TextProvenance
from agrag.common.data_models.search_result import SearchResult


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

    def test_rejects_negative_attempt_budget(self) -> None:
        """Negative budgets fail during middleware construction."""
        with pytest.raises(ValueError, match="non-negative"):
            self._middleware(-1)

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

        await limiter.awrap_tool_call(
            _tool_call_request("task", {"subagent_type": "researcher"}), handler
        )
        assert handler.await_count == 12

    def test_rejects_empty_model_list(self) -> None:
        """An empty model list raises ValueError."""
        with pytest.raises(ValueError, match="at least one model"):
            RoundRobinModelMiddleware([])


def _cited_chunk(ledger: Ledger, text: str) -> str:
    """Cite a chunk holding ``text`` in ``ledger`` and return its key."""
    chunk = Chunk(
        document_id=uuid4(),
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )
    return ledger.cite(SearchResult(item=chunk, score=1.0, method="chunk"))


class TestVerifierEvidenceMiddleware:
    """VerifierEvidenceMiddleware gives the verifier the text behind each key."""

    @staticmethod
    async def _delegate(
        ledger: Ledger, description: str, subagent_type: str = "verifier"
    ) -> str:
        """Run one task call through the middleware and return the task text."""
        handler = AsyncMock(return_value=ToolMessage(content="ran", tool_call_id="x"))
        await VerifierEvidenceMiddleware(ledger).awrap_tool_call(
            _tool_call_request(
                "task",
                {"subagent_type": subagent_type, "description": description},
            ),
            handler,
        )
        return handler.await_args.args[0].tool_call["args"]["description"]

    async def test_appends_the_text_of_each_cited_key(self) -> None:
        """A verifier task gets an Evidence block with the ledger text."""
        ledger = Ledger()
        key = _cited_chunk(ledger, "Net revenue was $5,829 million in 2015.")

        sent = await self._delegate(ledger, f"Revenue was 5829 ({key}).")

        assert sent.startswith(f"Revenue was 5829 ({key}).")
        assert sent.endswith(
            f"Evidence:\n[{key}] Chunk: Net revenue was $5,829 million in 2015."
        )

    async def test_marks_a_key_the_run_never_retrieved(self) -> None:
        """A key with no ledger entry shows as missing, not as support."""
        sent = await self._delegate(Ledger(), "Revenue was 5829 (C7).")

        assert "[C7] Not in the evidence retrieved in this run." in sent

    async def test_lists_a_repeated_key_once_in_order_of_first_use(self) -> None:
        """Each key appears once, in the order the task text first cites it."""
        ledger = Ledger()
        first = _cited_chunk(ledger, "first")
        second = _cited_chunk(ledger, "second")

        sent = await self._delegate(ledger, f"{second} then {first} then {second}")

        assert sent.split("Evidence:\n")[1].splitlines() == [
            f"[{second}] Chunk: second",
            f"[{first}] Chunk: first",
        ]

    async def test_leaves_a_task_without_keys_unchanged(self) -> None:
        """No citation means nothing to look up."""
        assert await self._delegate(Ledger(), "Check this.") == "Check this."

    async def test_leaves_researcher_tasks_unchanged(self) -> None:
        """Only verifier delegations get the evidence block."""
        ledger = Ledger()
        key = _cited_chunk(ledger, "text")

        sent = await self._delegate(ledger, f"Find more on {key}", "researcher")

        assert sent == f"Find more on {key}"


class TestHideToolsMiddleware:
    """HideToolsMiddleware removes named tools from the model request."""

    async def test_removes_only_the_named_tools(self) -> None:
        """The model sees every tool except the hidden ones, in order."""
        tools = [
            type("Tool", (), {"name": name})() for name in ("ls", "search", "grep")
        ]
        request = _request(object())
        request = request.override(tools=tools)
        handler = AsyncMock(return_value="ok")

        await HideToolsMiddleware(frozenset({"ls", "grep"})).awrap_model_call(
            request, handler
        )

        seen = handler.await_args.args[0]
        assert [tool.name for tool in seen.tools] == ["search"]


class _RepliesModel(BaseChatModel):
    """Chat model that returns queued replies in order and records its inputs."""

    replies: list[AIMessage]
    inputs: list[list[Any]] = []

    @property
    def _llm_type(self) -> str:
        """Name the fake model type."""
        return "replies"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_RepliesModel":
        """Return self; the replies are fixed."""
        return self

    def _generate(
        self,
        messages: list[Any],
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Record the messages and return the next reply, then repeat the last."""
        self.inputs.append(list(messages))
        reply = self.replies[min(len(self.inputs), len(self.replies)) - 1]
        # A new message each call, because the graph merges messages by id.
        fresh = AIMessage(content=reply.content, tool_calls=reply.tool_calls)
        return ChatResult(generations=[ChatGeneration(message=fresh)])


@tool
def _noop() -> str:
    """Do nothing. Gives the agent a tool node, as the DeepAgents tools do."""
    return ""


def _verdict_reply() -> AIMessage:
    """Build a reply that calls the verdict tool."""
    call = {
        "name": "VerificationResult",
        "args": {"reasoning": "ok", "status": "PASS"},
        "id": "call-1",
    }
    return AIMessage(content="", tool_calls=[call])


class TestRequireVerdictMiddleware:
    """RequireVerdictMiddleware asks again when the model answers in prose."""

    @staticmethod
    def _agent(model: _RepliesModel) -> Any:
        """Build a verifier-shaped agent that has a tool besides the verdict."""
        return create_agent(
            model,
            tools=[_noop],
            response_format=VerificationResult,
            middleware=[RequireVerdictMiddleware(max_reminders=2)],
        )

    async def test_asks_again_and_returns_the_verdict_it_then_gets(self) -> None:
        """A prose reply gets one reminder, and the next reply is the verdict."""
        model = _RepliesModel(
            replies=[AIMessage(content="looks fine"), _verdict_reply()], inputs=[]
        )

        state = await self._agent(model).ainvoke({"messages": [HumanMessage("check")]})

        assert state["structured_response"].status == "PASS"
        assert len(model.inputs) == 2
        assert "VerificationResult" in model.inputs[1][-1].content

    async def test_stops_after_the_reminder_budget(self) -> None:
        """A model that never calls the tool is asked twice more, then left alone."""
        model = _RepliesModel(replies=[AIMessage(content="looks fine")], inputs=[])

        state = await self._agent(model).ainvoke({"messages": [HumanMessage("check")]})

        assert len(model.inputs) == 3
        assert state.get("structured_response") is None

    async def test_does_not_interrupt_a_verdict(self) -> None:
        """A model that calls the verdict tool the first time is called once."""
        model = _RepliesModel(replies=[_verdict_reply()], inputs=[])

        await self._agent(model).ainvoke({"messages": [HumanMessage("check")]})

        assert len(model.inputs) == 1
