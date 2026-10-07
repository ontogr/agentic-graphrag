"""Tests for the per-request LLM spans in agrag.llm.tracing.

Drives ``record_requests`` with fake collector logs built from plain
namespaces, so each provider behavior is exercised without a network or a BAML
runtime. The ``call_with_retry`` tests use the real OpenTelemetry SDK to check
which spans a traced call emits and whether the collector reaches the call.

Failure modes covered: a missing tracer, a collector per attempt, newest-first
call order, absent usage, HTTP errors, cached-token counts, non-JSON bodies,
empty collectors, clock skew between BAML and the attempt, and a broken
collector that must not mask the call's own exception.
"""

import json
import types
from typing import Any, get_args

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from agrag.llm.client_config import LLMProvider, RetryConfig
from agrag.llm.retry import NO_RETRY, call_with_retry
from agrag.llm.tracing import record_requests


_NS_PER_MS = 1_000_000


def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a recording tracer and the exporter that collects its spans."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _body(payload: str, *, parseable: bool = True) -> Any:
    """Return a body whose ``text`` is the payload and ``json`` parses it."""
    if parseable:
        return types.SimpleNamespace(
            text=lambda: payload, json=lambda: json.loads(payload)
        )
    return types.SimpleNamespace(
        text=lambda: payload,
        json=lambda: (_ for _ in ()).throw(ValueError("not json")),
    )


def _call(
    *,
    client: str = "primary",
    provider: str = "openai-generic",
    selected: bool = True,
    start_ms: int = 1_000,
    duration_ms: int = 20,
    request: str = '{"model": "requested-model"}',
    response: str | None = '{"model": "served-model"}',
    status: int = 200,
    input_tokens: int | None = 11,
    output_tokens: int | None = 7,
    cached_tokens: int | None = None,
    response_is_json: bool = True,
) -> Any:
    """Build one fake BAML call log."""
    http_response = (
        None
        if response is None
        else types.SimpleNamespace(
            body=_body(response, parseable=response_is_json), status=status
        )
    )
    return types.SimpleNamespace(
        client_name=client,
        provider=provider,
        selected=selected,
        timing=types.SimpleNamespace(
            start_time_utc_ms=start_ms, duration_ms=duration_ms
        ),
        http_request=types.SimpleNamespace(body=_body(request)),
        http_response=http_response,
        usage=types.SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_tokens,
        ),
    )


def _collector(*calls: Any) -> Any:
    """Wrap calls in a fake collector with a single function log."""
    return types.SimpleNamespace(logs=[types.SimpleNamespace(calls=list(calls))])


def _record(calls: list[Any]) -> list[ReadableSpan]:
    """Record the calls with a generous window and return the request spans."""
    provider, exporter = _provider()
    record_requests(
        provider.get_tracer("t"),
        _collector(*calls),
        window=(0, 10_000 * _NS_PER_MS * _NS_PER_MS),
    )
    return [
        span
        for span in exporter.get_finished_spans()
        if span.name == "agrag.llm.request"
    ]


def _record_with_window(
    calls: list[Any], window: tuple[int, int]
) -> list[ReadableSpan]:
    """Record the calls inside an explicit window and return the spans."""
    provider, exporter = _provider()
    record_requests(provider.get_tracer("t"), _collector(*calls), window=window)
    return [
        span
        for span in exporter.get_finished_spans()
        if span.name == "agrag.llm.request"
    ]


def _attributes(span: ReadableSpan) -> dict[str, Any]:
    """Return the span's attributes."""
    return dict(span.attributes or {})


def _by_name(exporter: InMemorySpanExporter, name: str) -> ReadableSpan:
    """Return the single finished span with that name."""
    matches = [span for span in exporter.get_finished_spans() if span.name == name]
    assert len(matches) == 1, f"expected one {name} span, got {len(matches)}"
    return matches[0]


async def _no_sleep(seconds: float) -> None:
    """Return without waiting."""
    return


class TestProviderTable:
    """Every configured provider maps to an OpenInference provider value."""

    def test_every_configured_provider_has_a_mapping(self) -> None:
        """A new provider fails this test until the table names it."""
        from agrag.llm.tracing import _PROVIDERS  # noqa: PLC0415

        missing = [p for p in get_args(LLMProvider) if p not in _PROVIDERS]
        assert missing == []

    def test_unknown_provider_falls_back_to_the_raw_id(self) -> None:
        """A provider outside the table still records its BAML id."""
        (span,) = _record([_call(provider="some-new-provider")])

        attributes = _attributes(span)
        assert attributes["llm.provider"] == "some-new-provider"
        assert attributes["agrag.llm.baml_provider"] == "some-new-provider"


class TestRequestSpanAttributes:
    """One request span carries the bodies, model, client and token counts."""

    def test_request_and_response_bodies_are_recorded(self) -> None:
        """The raw HTTP bodies reach input.value and output.value."""
        (span,) = _record([_call()])

        attributes = _attributes(span)
        assert attributes["input.value"] == '{"model": "requested-model"}'
        assert attributes["output.value"] == '{"model": "served-model"}'
        assert attributes["output.mime_type"] == "application/json"

    def test_request_headers_are_never_recorded(self) -> None:
        """Nothing on the span carries the authorization header."""
        (span,) = _record([_call()])

        blob = repr(_attributes(span)).lower()
        assert "authorization" not in blob
        assert "api_key" not in blob

    def test_served_model_wins_and_the_requested_one_is_kept(self) -> None:
        """The response model names the span; the request model is recorded too."""
        (span,) = _record([_call()])

        attributes = _attributes(span)
        assert attributes["llm.model_name"] == "served-model"
        assert attributes["agrag.llm.requested_model"] == "requested-model"

    def test_requested_model_is_used_when_the_response_names_none(self) -> None:
        """A response without a model still leaves the span named."""
        (span,) = _record([_call(response="{}")])

        assert _attributes(span)["llm.model_name"] == "requested-model"

    def test_span_is_an_llm_kind_client_span(self) -> None:
        """Only request spans carry the OpenInference LLM kind."""
        (span,) = _record([_call()])

        assert _attributes(span)["openinference.span.kind"] == "LLM"
        assert span.kind.name == "CLIENT"

    def test_token_counts_and_total_are_recorded(self) -> None:
        """Prompt, completion and their sum come from BAML's usage."""
        (span,) = _record([_call(input_tokens=11, output_tokens=7)])

        attributes = _attributes(span)
        assert attributes["llm.token_count.prompt"] == 11
        assert attributes["llm.token_count.completion"] == 7
        assert attributes["llm.token_count.total"] == 18

    def test_cached_tokens_are_recorded_when_present(self) -> None:
        """A positive cache-read count is recorded."""
        (span,) = _record([_call(cached_tokens=5)])

        attributes = _attributes(span)
        assert attributes["llm.token_count.prompt_details.cache_read"] == 5

    def test_zero_cached_tokens_are_not_recorded(self) -> None:
        """A zero cache-read count means no caching, so the attribute is absent."""
        (span,) = _record([_call(cached_tokens=0)])

        assert "llm.token_count.prompt_details.cache_read" not in _attributes(span)

    def test_success_without_usage_is_flagged(self) -> None:
        """A 200 with no usage sets the flag and records no token counts."""
        (span,) = _record([_call(input_tokens=None, output_tokens=None)])

        attributes = _attributes(span)
        assert attributes["agrag.llm.usage_missing"] is True
        assert "llm.token_count.prompt" not in attributes
        assert "llm.token_count.total" not in attributes

    def test_non_json_response_is_text_and_names_no_model(self) -> None:
        """An HTML error body keeps its text and yields no served model."""
        (span,) = _record(
            [
                _call(
                    response="<html>Bad Gateway</html>",
                    status=502,
                    response_is_json=False,
                )
            ]
        )

        attributes = _attributes(span)
        assert attributes["output.mime_type"] == "text/plain"
        assert attributes["output.value"] == "<html>Bad Gateway</html>"
        assert attributes["llm.model_name"] == "requested-model"

    def test_no_response_marks_the_span_failed(self) -> None:
        """A call that got no response at all is an error span."""
        (span,) = _record([_call(response=None)])

        assert span.status.status_code is StatusCode.ERROR
        assert "output.value" not in _attributes(span)

    def test_client_name_and_selection_are_recorded(self) -> None:
        """Which client ran and whether it was selected are both recorded."""
        (span,) = _record([_call(client="secondary", selected=False)])

        attributes = _attributes(span)
        assert attributes["agrag.llm.client_name"] == "secondary"
        assert attributes["agrag.llm.selected"] is False


class TestFailureSpans:
    """HTTP error responses are marked without token counts."""

    def test_rate_limited_response_marks_the_span_error(self) -> None:
        """A 429 records the status and error.type, and has no usage to report."""
        (span,) = _record(
            [
                _call(
                    status=429,
                    response='{"error": "slow down"}',
                    input_tokens=None,
                    output_tokens=None,
                )
            ]
        )

        attributes = _attributes(span)
        assert span.status.status_code is StatusCode.ERROR
        assert attributes["error.type"] == "429"
        assert attributes["http.response.status_code"] == 429
        assert "llm.token_count.prompt" not in attributes
        assert "agrag.llm.usage_missing" not in attributes

    def test_a_failed_response_is_not_flagged_as_missing_usage(self) -> None:
        """A failure is not the same as a success whose usage never arrived."""
        (span,) = _record(
            [_call(status=500, response="boom", input_tokens=None, output_tokens=None)]
        )

        assert span.status.status_code is StatusCode.ERROR
        assert "agrag.llm.usage_missing" not in _attributes(span)


class TestOrderingAndWindow:
    """Calls are written in request order, clamped into the attempt window."""

    def test_newest_first_calls_are_sorted_by_start(self) -> None:
        """BAML reports newest first; the spans come out oldest first."""
        spans = _record(
            [
                _call(client="third", start_ms=3_000),
                _call(client="first", start_ms=1_000),
                _call(client="second", start_ms=2_000),
            ]
        )

        names = [_attributes(span)["agrag.llm.client_name"] for span in spans]
        assert names == ["first", "second", "third"]

    def test_request_before_the_window_start_is_clamped(self) -> None:
        """A start time before the attempt is pulled up to the attempt start."""
        (span,) = _record_with_window(
            [_call(start_ms=0, duration_ms=5)],
            (1_000 * _NS_PER_MS, 2_000 * _NS_PER_MS),
        )

        assert span.start_time == 1_000 * _NS_PER_MS

    def test_request_ending_after_the_window_is_clamped(self) -> None:
        """An end time past the attempt is pulled down to the attempt end."""
        (span,) = _record_with_window(
            [_call(start_ms=1_500, duration_ms=9_000)],
            (1_000 * _NS_PER_MS, 2_000 * _NS_PER_MS),
        )

        assert span.end_time == 2_000 * _NS_PER_MS

    def test_request_spans_nest_under_the_attempt_span(self) -> None:
        """The attempt span is current while the request spans are written."""
        provider, exporter = _provider()
        tracer = provider.get_tracer("t")

        with tracer.start_as_current_span("agrag.llm.attempt") as attempt:
            record_requests(
                tracer,
                _collector(_call()),
                window=(0, 10_000 * _NS_PER_MS * _NS_PER_MS),
            )
            attempt_id = attempt.get_span_context().span_id

        request = _by_name(exporter, "agrag.llm.request")
        assert request.parent is not None
        assert request.parent.span_id == attempt_id


class TestEmptyCollectors:
    """A collector with nothing in it writes nothing and raises nothing."""

    def test_collector_without_calls_writes_no_spans(self) -> None:
        """No calls means no request spans."""
        provider, exporter = _provider()

        record_requests(
            provider.get_tracer("t"),
            _collector(),
            window=(0, 10_000 * _NS_PER_MS * _NS_PER_MS),
        )

        assert list(exporter.get_finished_spans()) == []

    def test_collector_without_logs_writes_no_spans(self) -> None:
        """No logs at all is not an error."""
        provider, exporter = _provider()

        record_requests(
            provider.get_tracer("t"),
            types.SimpleNamespace(logs=[]),
            window=(0, 10_000 * _NS_PER_MS * _NS_PER_MS),
        )

        assert list(exporter.get_finished_spans()) == []

    def test_a_broken_collector_is_logged_not_raised(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A collector that cannot be read is logged and swallowed."""
        provider, _ = _provider()

        with caplog.at_level("WARNING"):
            record_requests(
                provider.get_tracer("t"),
                types.SimpleNamespace(logs="not a list of logs"),
                window=(0, 10_000 * _NS_PER_MS * _NS_PER_MS),
            )

        assert "Could not record LLM request spans" in caplog.text


class TestCallWithRetryCollector:
    """The primitive hands a fresh collector to each attempt."""

    async def test_no_tracer_means_no_collector_in_the_options(self) -> None:
        """An untraced call receives no collector key."""
        seen: list[dict[str, Any]] = []

        async def call(options: dict[str, Any]) -> str:
            seen.append(options)
            return "ok"

        await call_with_retry(call, NO_RETRY, options={"existing": 1})

        assert seen == [{"existing": 1}]

    async def test_no_tracer_leaves_the_host_span_untouched(self) -> None:
        """An untraced call adds no exception to the caller's active span."""
        provider, exporter = _provider()

        async def call(options: dict[str, Any]) -> str:
            raise RuntimeError("boom")

        with (
            provider.get_tracer("t").start_as_current_span("host") as host,
            pytest.raises(RuntimeError, match="boom"),
        ):
            await call_with_retry(call, NO_RETRY)

        assert host.status.status_code is StatusCode.UNSET
        assert not host.events
        assert [span.name for span in exporter.get_finished_spans()] == ["host"]

    async def test_each_attempt_receives_its_own_collector(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Collectors are per attempt, so retries cannot mix their calls."""
        monkeypatch.setattr("agrag.llm.retry.sleep", _no_sleep)
        collectors: list[Any] = []

        async def call(options: dict[str, Any]) -> str:
            collectors.append(options.get("collector"))
            if len(collectors) < 2:
                raise RuntimeError("transient")
            return "ok"

        provider, _ = _provider()
        await call_with_retry(
            call, RetryConfig(max_retries=1), tracer=provider.get_tracer("t")
        )

        assert len(collectors) == 2
        assert all(collector is not None for collector in collectors)
        assert collectors[0] is not collectors[1]

    async def test_traced_call_emits_call_and_attempt_spans(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A traced call opens one call span and one span per attempt."""
        monkeypatch.setattr("agrag.llm.retry.sleep", _no_sleep)
        provider, exporter = _provider()

        async def call(options: dict[str, Any]) -> str:
            return "ok"

        await call_with_retry(
            call,
            RetryConfig(max_retries=0),
            tracer=provider.get_tracer("t"),
            function="SummarizeDescriptions",
        )

        assert [span.name for span in exporter.get_finished_spans()] == [
            "agrag.llm.attempt",
            "agrag.llm.call",
        ]
        attributes = _attributes(_by_name(exporter, "agrag.llm.call"))
        assert attributes["agrag.llm.function"] == "SummarizeDescriptions"
        assert attributes["agrag.llm.attempt_count"] == 1

    async def test_a_failing_call_marks_the_call_span_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The last attempt's failure surfaces as an error call span."""
        monkeypatch.setattr("agrag.llm.retry.sleep", _no_sleep)
        provider, exporter = _provider()

        async def call(options: dict[str, Any]) -> str:
            raise RuntimeError("still failing")

        with pytest.raises(RuntimeError, match="still failing"):
            await call_with_retry(
                call, RetryConfig(max_retries=1), tracer=provider.get_tracer("t")
            )

        call_span = _by_name(exporter, "agrag.llm.call")
        assert call_span.status.status_code is StatusCode.ERROR
        assert (call_span.attributes or {})["agrag.llm.attempt_count"] == 2

    async def test_a_broken_collector_does_not_mask_the_call_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A collector BAML left unreadable never replaces the call's error."""
        monkeypatch.setattr(
            "agrag.llm.retry.new_collector",
            lambda: types.SimpleNamespace(logs="not a list of logs"),
        )
        provider, _ = _provider()

        async def call(options: dict[str, Any]) -> str:
            raise RuntimeError("the real failure")

        with pytest.raises(RuntimeError, match="the real failure"):
            await call_with_retry(
                call, RetryConfig(max_retries=0), tracer=provider.get_tracer("t")
            )

    async def test_the_retry_loop_keeps_its_delays_and_attempt_count(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tracing does not change the backoff schedule or the attempt count."""
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr("agrag.llm.retry.sleep", fake_sleep)
        monkeypatch.setattr("agrag.llm.retry.random.uniform", lambda low, high: high)
        provider, exporter = _provider()
        attempts = 0

        async def call(options: dict[str, Any]) -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RuntimeError("transient")
            return "ok"

        await call_with_retry(
            call,
            RetryConfig(max_retries=3, delay_ms=100, multiplier=2, max_delay_ms=10_000),
            tracer=provider.get_tracer("t"),
        )

        assert sleeps == [0.1, 0.2]
        assert attempts == 3
        attempt_spans = [
            span
            for span in exporter.get_finished_spans()
            if span.name == "agrag.llm.attempt"
        ]
        assert len(attempt_spans) == 3
        attributes = _attributes(_by_name(exporter, "agrag.llm.call"))
        assert attributes["agrag.llm.attempt_count"] == 3
