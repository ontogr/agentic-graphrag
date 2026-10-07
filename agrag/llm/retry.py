"""Async retry with exponential backoff, driven by a RetryConfig.

BAML's own ``ClientRegistry.add_llm_client(retry_policy=...)`` only accepts the
name of a retry policy already declared in ``.baml`` source — there is no way
to register one with arbitrary numeric values at runtime. Retrying here in
Python is the only way an env-configured ``RetryConfig`` can actually take
effect.
"""

import logging
import random
import time
from asyncio import sleep
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeVar

from opentelemetry.trace import Tracer

from agrag.llm.client_config import RetryConfig
from agrag.llm.tracing import new_collector, record_requests
from agrag.observability import get_tracer


logger = logging.getLogger(__name__)

_T = TypeVar("_T")

NO_RETRY = RetryConfig(max_retries=0)


class UnusableResultError(Exception):
    """Every attempt returned a result the caller refused to accept."""

    def __init__(self, function: str | None, attempts: int) -> None:
        """Record which call kept returning unusable results.

        Args:
            function: The BAML function name, if one was given.
            attempts: How many attempts ran before giving up.
        """
        self.function = function
        self.attempts = attempts
        super().__init__(
            f"LLM call {function or '<unknown>'} returned an unusable "
            f"result on all {attempts} attempt(s)"
        )


def _is_permanently_unretryable(exc: BaseException) -> bool:
    """Return whether exc would fail identically on every retry.

    An invalid function argument or an HTTP 4xx other than 429 (rate
    limiting) reflects the request itself, not a transient provider hiccup —
    retrying it spends the whole retry budget on an error retrying cannot
    fix. Returns False, never raising, when ``baml_py`` is not installed or
    exc is not one of its typed errors, so a caller with no BAML dependency
    keeps retrying every exception exactly as before.
    """
    try:
        from baml_py.errors import (  # noqa: PLC0415
            BamlClientHttpError,
            BamlInvalidArgumentError,
        )
    except ImportError:
        return False
    if isinstance(exc, BamlInvalidArgumentError):
        return True
    if isinstance(exc, BamlClientHttpError):
        return exc.status_code != 429 and 400 <= exc.status_code < 500
    return False


async def call_with_retry(
    call: Callable[[dict[str, Any]], Awaitable[_T]],
    retry: RetryConfig,
    *,
    options: Mapping[str, Any] | None = None,
    tracer: Tracer | None = None,
    function: str | None = None,
    accept_result: Callable[[_T], bool] | None = None,
) -> _T:
    """Retry an async BAML call with exponential backoff, tracing each attempt.

    Args:
        call: Runs one attempt. It receives that attempt's own BAML options: a
            copy of ``options``, plus a fresh ``collector`` when the attempt
            span is being recorded. Pass the received dict on to BAML.
        retry: Backoff settings. ``max_retries`` is the number of retries
            after the first attempt. ``timeout_ms`` bounds the whole call when
            positive; it never interrupts an in-flight attempt.
        options: The BAML call options shared by every attempt, such as the
            client registry and the type builder.
        tracer: Opens ``agrag.llm.call``, one ``agrag.llm.attempt`` per attempt
            and one ``agrag.llm.request`` per provider request. ``None`` opens
            no recorded span.
        function: The BAML function name, recorded as ``agrag.llm.function``.
        accept_result: Return whether a successful result is usable. A result
            it rejects is retried like a transient failure. None accepts every
            result.

    Returns:
        The first successful call's result, or the first result
        ``accept_result`` accepts.

    Raises:
        Exception: The last attempt's exception, if every attempt fails, or
            immediately for a BAML error that would fail identically on
            retry (an invalid argument, or an HTTP 4xx other than 429). When
            ``timeout_ms`` elapses the last failure raises as-is instead of
            waiting out the remaining budget.
        UnusableResultError: Every attempt returned a result ``accept_result``
            rejected.
    """
    active = get_tracer(tracer)
    attempts = retry.max_retries + 1
    delay_seconds = retry.delay_ms / 1000
    max_delay_seconds = retry.max_delay_ms / 1000
    deadline = (
        time.monotonic() + retry.timeout_ms / 1000 if retry.timeout_ms > 0 else None
    )
    call_attributes = {"agrag.llm.function": function} if function else {}
    with active.start_as_current_span(
        "agrag.llm.call", attributes=call_attributes
    ) as call_span:
        attempt = 0
        while True:
            attempt += 1
            try:
                result = await _run_attempt(active, call, options, attempt)
            except Exception as exc:  # noqa: BLE001
                if (
                    attempt >= attempts
                    or _is_permanently_unretryable(exc)
                    or (deadline is not None and time.monotonic() >= deadline)
                ):
                    call_span.set_attribute("agrag.llm.attempt_count", attempt)
                    raise
            else:
                if accept_result is None or accept_result(result):
                    call_span.set_attribute("agrag.llm.attempt_count", attempt)
                    return result
                if attempt >= attempts or (
                    deadline is not None and time.monotonic() >= deadline
                ):
                    call_span.set_attribute("agrag.llm.attempt_count", attempt)
                    raise UnusableResultError(function, attempt)
            wait = min(delay_seconds, max_delay_seconds) * random.uniform(0.5, 1.0)
            logger.debug(
                "LLM call %s failed on attempt %d; retrying in %.3f seconds",
                function or "<unknown>",
                attempt,
                wait,
            )
            await sleep(wait)
            delay_seconds = min(delay_seconds * retry.multiplier, max_delay_seconds)


async def _run_attempt(
    tracer: Tracer,
    call: Callable[[dict[str, Any]], Awaitable[_T]],
    options: Mapping[str, Any] | None,
    attempt: int,
) -> _T:
    """Run one attempt under its own span and write its request spans."""
    started = time.time_ns()
    with tracer.start_as_current_span(
        "agrag.llm.attempt",
        start_time=started,
        attributes={"agrag.llm.attempt": attempt},
    ) as span:
        attempt_options = dict(options or {})
        collector = new_collector() if span.is_recording() else None
        if collector is not None:
            attempt_options["collector"] = collector
        try:
            return await call(attempt_options)
        finally:
            if collector is not None:
                record_requests(tracer, collector, window=(started, time.time_ns()))
