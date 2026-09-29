"""Spans for BAML calls: one ``agrag.llm.request`` span per provider request.

BAML records every provider request of a call in a ``Collector``. This module
reads a collector after an attempt ends and writes one span per request. The
spans carry the raw request and response bodies. They never carry the request
headers, which hold the provider key, or the request URL.
"""

import logging
from collections.abc import Mapping
from typing import Any

from openinference.semconv.trace import (
    OpenInferenceMimeTypeValues,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)
from opentelemetry.trace import SpanKind, Status, StatusCode, Tracer
from opentelemetry.util.types import AttributeValue


logger = logging.getLogger(__name__)

_NS_PER_MS = 1_000_000

_PROVIDERS = {
    "openai": "openai",
    "openai-generic": "openai",
    "openai-responses": "openai",
    "azure-openai": "azure",
    "anthropic": "anthropic",
    "google-ai": "google",
    "vertex-ai": "google",
    "aws-bedrock": "aws",
}


def _model_of(body: Any) -> str | None:
    """Return the model id from a request or response body, if present."""
    try:
        data = body.json()
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, Mapping):
        return None
    model = data.get("model")
    if isinstance(model, str) and model:
        return model
    return None


def _is_json(body: Any) -> bool:
    """Return whether the body parses as JSON."""
    try:
        body.json()
    except Exception:  # noqa: BLE001
        return False
    return True


def _token_attributes(usage: Any, *, succeeded: bool) -> dict[str, AttributeValue]:
    """Return token attributes from BAML usage, omitting missing counts."""
    attributes: dict[str, AttributeValue] = {}
    prompt = getattr(usage, "input_tokens", None) if usage is not None else None
    completion = getattr(usage, "output_tokens", None) if usage is not None else None
    cached = getattr(usage, "cached_input_tokens", None) if usage is not None else None
    if prompt is not None:
        attributes[SpanAttributes.LLM_TOKEN_COUNT_PROMPT] = prompt
    if completion is not None:
        attributes[SpanAttributes.LLM_TOKEN_COUNT_COMPLETION] = completion
    if prompt is not None and completion is not None:
        attributes[SpanAttributes.LLM_TOKEN_COUNT_TOTAL] = prompt + completion
    if isinstance(cached, int) and cached > 0:
        attributes[SpanAttributes.LLM_TOKEN_COUNT_PROMPT_DETAILS_CACHE_READ] = cached
    if succeeded and prompt is None and completion is None and cached is None:
        attributes["agrag.llm.usage_missing"] = True
    return attributes


def new_collector() -> Any | None:
    """Return a fresh BAML collector, or None when ``baml_py`` is not installed."""
    try:
        from baml_py import Collector  # noqa: PLC0415
    except ImportError:
        return None
    return Collector()


def record_requests(tracer: Tracer, collector: Any, *, window: tuple[int, int]) -> None:
    """Write one ``agrag.llm.request`` span per provider request in ``collector``.

    Call it once, after the attempt's BAML call returned or raised, while the
    attempt span is still current. It never raises: a failure to read BAML's
    data is logged, so it cannot replace the exception of the call it observes.

    Args:
        tracer: Opens the spans.
        collector: The collector that was passed to exactly one BAML call.
        window: The attempt's start and end in nanoseconds. Request times from
            BAML have millisecond resolution, so each span is clamped into it.
    """
    try:
        calls = [call for log in collector.logs for call in log.calls]
        calls.sort(key=lambda call: call.timing.start_time_utc_ms)
        for call in calls:
            _write_request_span(tracer, call, window)
    except Exception:  # noqa: BLE001
        logger.warning("Could not record LLM request spans.", exc_info=True)


def _write_request_span(tracer: Tracer, call: Any, window: tuple[int, int]) -> None:
    """Write the span for one provider request."""
    floor, ceiling = window
    start = min(max(call.timing.start_time_utc_ms * _NS_PER_MS, floor), ceiling)
    end_ms = call.timing.start_time_utc_ms + (call.timing.duration_ms or 0)
    end = min(max(end_ms * _NS_PER_MS, start), ceiling)

    request = call.http_request
    response = call.http_response
    requested_model = _model_of(request.body)
    served_model = _model_of(response.body) if response is not None else None
    attributes: dict[str, AttributeValue] = {
        SpanAttributes.OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.LLM.value,
        SpanAttributes.LLM_PROVIDER: _PROVIDERS.get(call.provider, call.provider),
        SpanAttributes.INPUT_VALUE: request.body.text(),
        SpanAttributes.INPUT_MIME_TYPE: OpenInferenceMimeTypeValues.JSON.value,
        "agrag.llm.baml_provider": call.provider,
        "agrag.llm.client_name": call.client_name,
        "agrag.llm.selected": call.selected,
    }
    model = served_model or requested_model
    if model is not None:
        attributes[SpanAttributes.LLM_MODEL_NAME] = model
    if requested_model is not None:
        attributes["agrag.llm.requested_model"] = requested_model
    failed = response is None
    if response is not None:
        attributes[SpanAttributes.OUTPUT_VALUE] = response.body.text()
        attributes[SpanAttributes.OUTPUT_MIME_TYPE] = (
            OpenInferenceMimeTypeValues.JSON.value
            if _is_json(response.body)
            else OpenInferenceMimeTypeValues.TEXT.value
        )
        attributes["http.response.status_code"] = response.status
        failed = response.status >= 400
        if failed:
            attributes["error.type"] = str(response.status)
    attributes.update(_token_attributes(call.usage, succeeded=not failed))

    span = tracer.start_span(
        "agrag.llm.request",
        kind=SpanKind.CLIENT,
        start_time=start,
        attributes=attributes,
    )
    if failed:
        span.set_status(Status(StatusCode.ERROR))
    span.end(end_time=end)
