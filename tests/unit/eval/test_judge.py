"""Tests for ChatModelJudge.

The chat model is a real ``ChatOpenAI`` whose HTTP clients use an
``httpx.MockTransport``, so requests go through the real structured-output path
and the request body shows what reaches the wire. No network is used.
"""

import json
import os

import httpx
import pytest
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams
from pydantic import BaseModel

from agrag.eval.judge import ChatModelJudge
from agrag.eval.settings import EvalJudgeSettings
from agrag.llm.client_config import LLMClientConfig


os.environ.setdefault("LANGCHAIN_OPENAI_TCP_KEEPALIVE", "0")

from langchain_openai import ChatOpenAI  # noqa: E402


class Verdict(BaseModel):
    """A structured judge reply."""

    reason: str
    score: int


def _tool_arguments(properties: dict) -> dict:
    """Answer a tool schema the way a cooperative judge would."""
    if "steps" in properties:
        return {"steps": ["Check the facts.", "Check the wording."]}
    return {"reason": "It matches.", "score": 8}


class FakeEndpoint:
    """An OpenAI-compatible endpoint that records every request body."""

    def __init__(self, ignore_tools: bool = False) -> None:
        """Start with no recorded requests.

        Args:
            ignore_tools: Answer in fenced JSON prose, as endpoints do that
                do not support tool calls.
        """
        self.ignore_tools = ignore_tools
        self.bodies: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        """Answer a chat completion, calling the requested tool if there is one."""
        body = json.loads(request.content)
        self.bodies.append(body)
        message: dict = {"role": "assistant", "content": "plain reply"}
        if body.get("tools") and self.ignore_tools:
            message["content"] = '```json\n{"reason": "In prose.", "score": 5}\n```'
        elif body.get("tools"):
            function = body["tools"][0]["function"]
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": function["name"],
                            "arguments": json.dumps(
                                _tool_arguments(function["parameters"]["properties"])
                            ),
                        },
                    }
                ],
            }
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "fake",
                "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            },
        )


def _chat_model(endpoint: FakeEndpoint) -> ChatOpenAI:
    transport = httpx.MockTransport(endpoint)
    return ChatOpenAI(
        model="fake",
        api_key="x",
        base_url="http://fake/v1",
        http_client=httpx.Client(transport=transport),
        http_async_client=httpx.AsyncClient(transport=transport),
    )


def _settings(temperature: float | None) -> EvalJudgeSettings:
    client = LLMClientConfig(name="j", provider="openai-generic", model="fake")
    return EvalJudgeSettings(client=client, temperature=temperature)


@pytest.fixture
def endpoint(monkeypatch: pytest.MonkeyPatch) -> FakeEndpoint:
    """A fake endpoint that build_chat_model reaches through a mock transport."""
    fake = FakeEndpoint()
    monkeypatch.setattr(
        "agrag.eval.judge.build_chat_model", lambda client: _chat_model(fake)
    )
    return fake


class TestChatModelJudge:
    """ChatModelJudge follows the settings and DeepEval's model contract."""

    async def test_sends_temperature_zero_on_the_wire(
        self, endpoint: FakeEndpoint
    ) -> None:
        """The request body carries temperature 0, not just a model attribute."""
        judge = ChatModelJudge.from_settings(_settings(0.0))

        await judge.a_generate("hi")

        assert endpoint.bodies[0]["temperature"] == 0

    def test_sends_temperature_zero_on_the_wire_sync(
        self, endpoint: FakeEndpoint
    ) -> None:
        """The sync path sends the same temperature."""
        judge = ChatModelJudge.from_settings(_settings(0.0))

        judge.generate("hi")

        assert endpoint.bodies[0]["temperature"] == 0

    async def test_sends_no_temperature_when_none(self, endpoint: FakeEndpoint) -> None:
        """A None temperature leaves the key out of the request."""
        judge = ChatModelJudge.from_settings(_settings(None))

        await judge.a_generate("hi")

        assert "temperature" not in endpoint.bodies[0]

    async def test_schema_returns_an_instance_async(
        self, endpoint: FakeEndpoint
    ) -> None:
        """With a schema, a_generate returns a schema instance."""
        judge = ChatModelJudge.from_settings(_settings(0.0))

        result = await judge.a_generate("rate it", schema=Verdict)

        assert result == Verdict(reason="It matches.", score=8)

    def test_schema_returns_an_instance_sync(self, endpoint: FakeEndpoint) -> None:
        """With a schema, generate returns a schema instance."""
        judge = ChatModelJudge.from_settings(_settings(0.0))

        assert judge.generate("rate it", schema=Verdict) == Verdict(
            reason="It matches.", score=8
        )

    async def test_parses_json_from_prose_when_tools_are_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A reply in fenced JSON still yields a schema instance."""
        fake = FakeEndpoint(ignore_tools=True)
        monkeypatch.setattr(
            "agrag.eval.judge.build_chat_model", lambda client: _chat_model(fake)
        )
        judge = ChatModelJudge.from_settings(_settings(0.0))

        assert await judge.a_generate("rate it", schema=Verdict) == Verdict(
            reason="In prose.", score=5
        )
        assert judge.generate("rate it", schema=Verdict).score == 5

    def test_without_schema_returns_text(self, endpoint: FakeEndpoint) -> None:
        """Without a schema, generate returns the reply text."""
        judge = ChatModelJudge.from_settings(_settings(0.0))

        assert judge.generate("hi") == "plain reply"

    def test_reports_the_client_model_id(self, endpoint: FakeEndpoint) -> None:
        """get_model_name returns the model id from the settings."""
        assert ChatModelJudge.from_settings(_settings(0.0)).get_model_name() == "fake"

    def test_scores_a_real_geval(self, endpoint: FakeEndpoint) -> None:
        """The judge works as model= on a GEval and yields a normalized score."""
        judge = ChatModelJudge.from_settings(_settings(0.0))
        metric = GEval(
            name="Correctness",
            criteria="The answer matches the expected output.",
            evaluation_params=[
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
            ],
            model=judge,
            async_mode=False,
        )

        metric.measure(LLMTestCase(input="q", actual_output="a", expected_output="a"))

        assert metric.score == pytest.approx(0.8)
        assert metric.reason
