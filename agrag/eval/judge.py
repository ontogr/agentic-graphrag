"""A DeepEval judge model backed by an agrag chat model."""

from typing import Any

from deepeval.metrics.utils import trimAndLoadJson
from deepeval.models import DeepEvalBaseLLM
from opentelemetry.trace import Tracer
from pydantic import BaseModel

from agrag.agents.model import build_chat_model
from agrag.agents.tracing import run_callbacks
from agrag.eval.settings import EvalJudgeSettings
from agrag.observability import get_tracer


def _to_schema(reply: dict, schema: type[BaseModel]) -> BaseModel:
    """Return the parsed tool call, or parse JSON from the reply text.

    Some OpenAI-compatible endpoints ignore tools and answer in prose when the
    prompt asks for JSON. Deepeval's prompts do.
    """
    if reply["parsed"] is not None:
        return reply["parsed"]
    return schema.model_validate(trimAndLoadJson(reply["raw"].text))


class ChatModelJudge(DeepEvalBaseLLM):
    """Wrap a LangChain chat model as a DeepEval judge.

    Pass an instance as ``model=`` to any DeepEval metric. With a ``schema``,
    ``generate`` returns an instance of it. Without one, it returns the reply
    text. Provider errors surface unchanged.
    """

    def __init__(
        self, chat_model: Any, name: str, *, tracer: Tracer | None = None
    ) -> None:
        """Bind the chat model and the model id reported in DeepEval results."""
        self._chat_model = chat_model
        self._model_name = name
        self._tracer = tracer
        super().__init__(name)

    @classmethod
    def from_settings(
        cls, settings: EvalJudgeSettings, *, tracer: Tracer | None = None
    ) -> "ChatModelJudge":
        """Build a judge from settings.

        The chat model is copied with ``settings.temperature`` set. When that
        is ``None``, no temperature is set. A model that rejects the
        parameter then needs ``EVAL_JUDGE_TEMPERATURE`` empty.

        Args:
            settings: The judge client config and temperature.
            tracer: Receives OpenInference spans for every judge call.
                None emits no spans.
        """
        chat_model = build_chat_model(settings.client)
        if settings.temperature is not None:
            chat_model = chat_model.model_copy(
                update={"temperature": settings.temperature}
            )
        return cls(chat_model, settings.client.model, tracer=tracer)

    def load_model(self) -> Any:
        """Return the wrapped chat model."""
        return self._chat_model

    def get_model_name(self) -> str:
        """Return the judge's model id."""
        return self._model_name

    def generate(self, prompt: str, schema: type[BaseModel] | None = None) -> Any:
        """Run one judge call, returning a ``schema`` instance or the reply text."""
        with self._judge_span():
            config = {"callbacks": run_callbacks(self._tracer)}
            if schema is None:
                return self._chat_model.invoke(prompt, config=config).text
            return _to_schema(
                self._structured(schema).invoke(prompt, config=config), schema
            )

    async def a_generate(
        self, prompt: str, schema: type[BaseModel] | None = None
    ) -> Any:
        """Run one judge call asynchronously. See ``generate``."""
        with self._judge_span():
            config = {"callbacks": run_callbacks(self._tracer)}
            if schema is None:
                return (await self._chat_model.ainvoke(prompt, config=config)).text
            return _to_schema(
                await self._structured(schema).ainvoke(prompt, config=config), schema
            )

    def _judge_span(self) -> Any:
        """Open the ``agrag.eval.judge`` span for one judge call."""
        return get_tracer(self._tracer).start_as_current_span(
            "agrag.eval.judge",
            attributes={"agrag.eval.judge_model": self._model_name},
        )

    def _structured(self, schema: type[BaseModel]) -> Any:
        # Tool calling works on OpenAI-compatible endpoints that ignore
        # response_format=json_schema and reply in prose.
        return self._chat_model.with_structured_output(
            schema, method="function_calling", include_raw=True
        )
