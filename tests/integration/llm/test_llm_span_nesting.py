"""Nesting tests for the LLM spans.

Each case drives real BAML calls against a local OpenAI-compatible server and
checks the parent/child structure of the exported spans: under
``asyncio.gather``, in a thread with a copied context, across retries, across a
provider fallback, and through DeepEval's own scheduler. Nothing below the HTTP
boundary is mocked, so a span that lost its parent fails here.
"""

import asyncio
import contextvars
from typing import Any

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.graph_schema import GENERIC
from agrag.common.data_models.provenance import TextProvenance
from agrag.ingestion.extract import BAMLExtractor, ExtractionLLMSettings
from agrag.llm.client_config import LLMClientConfig, RetryConfig
from tests.integration.llm._local_llm import (
    LocalLLM,
    span_tree_path,
    write_span_tree,
)


_DOC_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def local() -> Any:
    """A running fake OpenAI-compatible endpoint."""
    server = LocalLLM()
    yield server
    server.close()


def _settings(local: LocalLLM, mode: str = "extract") -> ExtractionLLMSettings:
    """Return extraction settings pointing at the fake endpoint."""
    return ExtractionLLMSettings(
        clients=[
            LLMClientConfig(
                name="primary",
                provider="openai-generic",
                model="requested-model",
                api_key="sk-nesting-test-key",
                base_url=local.url(mode),
            )
        ],
        retry=RetryConfig(max_retries=0),
    )


def _chunk(text: str) -> Chunk:
    """Build a minimal Chunk."""
    return Chunk(
        document_id=_DOC_ID,  # type: ignore[arg-type]
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )


def _by_id(spans: tuple[ReadableSpan, ...]) -> dict[int, ReadableSpan]:
    """Return the spans keyed by their span id."""
    return {span.context.span_id: span for span in spans}


def _ancestor_names(span: ReadableSpan, spans: tuple[ReadableSpan, ...]) -> list[str]:
    """Return the names of a span's ancestors, nearest first."""
    by_id = _by_id(spans)
    names: list[str] = []
    parent = span.parent
    seen: set[int] = set()
    while parent is not None and parent.span_id not in seen:
        seen.add(parent.span_id)
        holder = by_id.get(parent.span_id)
        if holder is None:
            break
        names.append(holder.name)
        parent = holder.parent
    return names


def _requests(spans: tuple[ReadableSpan, ...]) -> list[ReadableSpan]:
    """Return the request spans in export order."""
    return [span for span in spans if span.name == "agrag.llm.request"]


def _attempts(spans: tuple[ReadableSpan, ...]) -> list[ReadableSpan]:
    """Return the attempt spans in export order."""
    return [span for span in spans if span.name == "agrag.llm.attempt"]


class TestGather:
    """Concurrent calls each keep their own subtree."""

    async def test_four_concurrent_calls_share_one_root(self, local: LocalLLM) -> None:
        """Every request span has the root as an ancestor, four in total."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")
        extractor = BAMLExtractor(settings=_settings(local), tracer=tracer)

        async def one(index: int) -> None:
            """Run one extraction with text unique to this task."""
            await extractor.extract(
                _chunk(f"Entity number {index} was founded."), GENERIC
            )

        with tracer.start_as_current_span("root"):
            await asyncio.gather(*(one(index) for index in range(4)))

        spans = exporter.get_finished_spans()
        requests = _requests(spans)
        assert len(requests) == 4
        for span in requests:
            assert "root" in _ancestor_names(span, spans)
        assert len({span.context.trace_id for span in spans}) == 1
        write_span_tree(span_tree_path("nesting_gather.json"), spans)


class TestThreadWithCopiedContext:
    """A call in a thread keeps the caller's context."""

    async def test_a_thread_with_copied_context_stays_under_the_root(
        self, local: LocalLLM
    ) -> None:
        """The request spans nest under the root across the thread boundary."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")
        extractor = BAMLExtractor(settings=_settings(local), tracer=tracer)

        async def run() -> None:
            """Run one extraction."""
            await extractor.extract(_chunk("Ada Lovelace founded a clinic."), GENERIC)

        with tracer.start_as_current_span("root"):
            await asyncio.to_thread(contextvars.copy_context().run, asyncio.run, run())

        spans = exporter.get_finished_spans()
        requests = _requests(spans)
        assert len(requests) == 1
        assert "root" in _ancestor_names(requests[0], spans)
        write_span_tree(span_tree_path("nesting_thread.json"), spans)


class TestRetries:
    """Each attempt gets its own span under one call span."""

    async def test_three_attempts_open_three_attempt_spans(
        self, local: LocalLLM
    ) -> None:
        """Two real HTTP failures then a success, through BAML's own retry.

        The server fails the first two requests, so this drives the actual
        ``call_with_retry`` path: three attempts under one call span, and one
        request span per attempt, the first two carrying the error status.
        """
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")
        settings = ExtractionLLMSettings(
            clients=[
                LLMClientConfig(
                    name="primary",
                    provider="openai-generic",
                    model="requested-model",
                    api_key="sk-nesting-test-key",
                    base_url=local.url("flaky"),
                )
            ],
            retry=RetryConfig(max_retries=2, delay_ms=1),
        )

        await BAMLExtractor(settings=settings, tracer=tracer).extract(
            _chunk("Ada Lovelace founded a clinic."), GENERIC
        )

        spans = exporter.get_finished_spans()
        attempts = _attempts(spans)
        requests = _requests(spans)
        assert len(attempts) == 3
        assert len(requests) == 3
        call_span = next(span for span in spans if span.name == "agrag.llm.call")
        assert (call_span.attributes or {})["agrag.llm.attempt_count"] == 3
        for attempt in attempts:
            assert attempt.parent is not None
            assert attempt.parent.span_id == call_span.context.span_id
        for request in requests:
            assert request.parent is not None
            assert request.parent.span_id in {a.context.span_id for a in attempts}
        for request in requests[:2]:
            assert request.status.status_code.name == "ERROR"
            assert (request.attributes or {})["http.response.status_code"] == 500
        assert requests[2].status.status_code.name == "UNSET"
        write_span_tree(span_tree_path("nesting_retries.json"), spans)


class TestFallback:
    """A failed primary and a served fallback share one attempt span."""

    async def test_two_request_spans_land_under_one_attempt(
        self, local: LocalLLM
    ) -> None:
        """The failed and the selected call are siblings under one attempt."""
        from agrag.llm.retry import call_with_retry  # noqa: PLC0415
        from tests.integration.llm._local_llm import fallback_registry  # noqa: PLC0415

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")

        async def call(options: dict[str, Any]) -> Any:
            """Run the community summarizer over the fallback registry."""
            from agrag.llm.baml_client import b as client  # noqa: PLC0415

            return await client.SummarizeCommunities(
                communities=[], baml_options=options
            )

        await call_with_retry(
            call,
            RetryConfig(max_retries=0),
            options={"client_registry": fallback_registry(local)},
            tracer=tracer,
            function="SummarizeCommunities",
        )

        spans = exporter.get_finished_spans()
        requests = _requests(spans)
        assert len(requests) == 2
        attempts = _attempts(spans)
        assert len(attempts) == 1
        for span in requests:
            assert span.parent is not None
            assert span.parent.span_id == attempts[0].context.span_id
        names = {
            dict(item.attributes or {})["agrag.llm.client_name"] for item in requests
        }
        assert names == {"primary", "secondary"}
        served = next(
            item
            for item in requests
            if dict(item.attributes or {})["agrag.llm.client_name"] == "secondary"
        )
        assert dict(served.attributes or {})["agrag.llm.selected"] is True
        failed = next(
            item
            for item in requests
            if dict(item.attributes or {})["agrag.llm.client_name"] == "primary"
        )
        assert dict(failed.attributes or {})["agrag.llm.selected"] is False
        write_span_tree(span_tree_path("nesting_fallback.json"), spans)


class TestJudgeUnderDeepEvalScheduler:
    """Judge spans nest under the caller's span through DeepEval's scheduler.

    The tests are deliberately synchronous: ``deepeval.evaluate`` calls
    ``loop.run_until_complete``, which cannot run inside the event loop
    pytest-asyncio gives an ``async def`` test.
    """

    def _judge(self, local: LocalLLM, tracer: Any) -> Any:
        """Return a judge pointed at the fake endpoint."""
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        from agrag.eval.judge import ChatModelJudge  # noqa: PLC0415

        return ChatModelJudge(
            ChatOpenAI(
                model="requested-model",
                api_key="sk-nesting-test-key",
                base_url=local.url("ok"),
                max_retries=0,
            ),
            "requested-model",
            tracer=tracer,
        )

    def _metric(self, judge: Any) -> Any:
        """Return a custom metric that calls the judge once per case."""
        from deepeval.metrics import BaseMetric  # noqa: PLC0415
        from deepeval.test_case import LLMTestCase  # noqa: PLC0415

        class _JudgeMetric(BaseMetric):
            """Call the judge and report success."""

            def __init__(self) -> None:
                """Build with no model of DeepEval's own."""
                super().__init__()
                self.threshold = 0.5

            def _fill(self, *, is_async: bool) -> None:
                """Record the score DeepEval reads off the metric."""
                self.score = 1.0
                self.success = True
                self.reason = "judged"
                self.evaluation_steps = []
                self.evaluation_model = "requested-model"
                self.strict_mode = False
                self.async_mode = is_async
                self.strict_thresh = 0.5
                self.include_reason = True

            def measure(self, test_case: LLMTestCase) -> Any:
                """Run one judge call synchronously."""
                judge.generate("rate this")
                self._fill(is_async=False)
                return self.score

            async def a_measure(self, test_case: LLMTestCase) -> Any:
                """Run one judge call asynchronously."""
                await judge.a_generate("rate this")
                self._fill(is_async=True)
                return self.score

        return _JudgeMetric()

    @staticmethod
    def _cases() -> list[Any]:
        """Return two minimal test cases for the scheduler to run."""
        from deepeval.test_case import LLMTestCase  # noqa: PLC0415

        return [
            LLMTestCase(input="q1", actual_output="a1"),
            LLMTestCase(input="q2", actual_output="a2"),
        ]

    @staticmethod
    def _assert_judges_nested(
        exporter: InMemorySpanExporter, expected: int
    ) -> tuple[ReadableSpan, ...]:
        """Assert the judge spans hang under the root, and count them."""
        spans = exporter.get_finished_spans()
        judges = [span for span in spans if span.name == "agrag.eval.judge"]
        assert len(judges) == expected
        for span in judges:
            assert "root" in _ancestor_names(span, spans)
        return spans

    def test_sync_evaluation_nests_the_judge_spans(self, local: LocalLLM) -> None:
        """deepeval.evaluate with run_async=False keeps the nesting."""
        from deepeval import evaluate  # noqa: PLC0415
        from deepeval.evaluate.configs import AsyncConfig  # noqa: PLC0415

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")
        metric = self._metric(self._judge(local, tracer))

        with tracer.start_as_current_span("root"):
            evaluate(
                test_cases=self._cases(),
                metrics=[metric],
                async_config=AsyncConfig(run_async=False),
            )

        spans = self._assert_judges_nested(exporter, 2)
        write_span_tree(span_tree_path("nesting_judge_sync.json"), spans)

    def test_async_evaluation_nests_the_judge_spans(self, local: LocalLLM) -> None:
        """deepeval.evaluate with run_async=True keeps the nesting too."""
        from deepeval import evaluate  # noqa: PLC0415
        from deepeval.evaluate.configs import AsyncConfig  # noqa: PLC0415

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")
        metric = self._metric(self._judge(local, tracer))

        with tracer.start_as_current_span("root"):
            evaluate(
                test_cases=self._cases(),
                metrics=[metric],
                async_config=AsyncConfig(run_async=True),
            )

        spans = self._assert_judges_nested(exporter, 2)
        write_span_tree(span_tree_path("nesting_judge_async.json"), spans)
