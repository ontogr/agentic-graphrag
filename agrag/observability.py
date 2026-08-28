"""OpenTelemetry wiring for the ingestion layer.

This module imports only ``opentelemetry-api``. The SDK and exporters stay in
the optional ``observability`` extra and are never imported here; a caller
wires them before opening a graph. The tracer is constructor-injected, never
ambient.
"""

import asyncio
import inspect
from contextlib import ExitStack
from functools import wraps
from typing import Any, Callable

from opentelemetry import trace
from opentelemetry.trace import Tracer


def get_tracer(tracer: Tracer | None) -> Tracer:
    """Return a usable tracer.

    Args:
        tracer: A caller-supplied tracer, or ``None`` to use OpenTelemetry's
            global no-op tracer.

    Returns:
        The supplied tracer, or the global no-op tracer when the caller passed ``None``.
    """
    if tracer is None:
        return trace.get_tracer("agrag")
    return tracer


def traced(tracer: Tracer | None) -> Callable[[Callable], Callable]:
    """Wrap a call in a span on the given tracer.

    Use this at each pipeline call site (loader, chunker). It works on both
    sync and async functions; the span name is the wrapped callable's
    qualified name.

    Args:
        tracer: The tracer to record on, or ``None`` for a no-op span.

    Returns:
        A decorator that wraps the target callable in a span.
    """
    use_tracer = get_tracer(tracer)

    def decorator(func: Callable) -> Callable:
        name = getattr(func, "__qualname__", getattr(func, "__name__", "call"))

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with use_tracer.start_as_current_span(name):
                    return await func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if inspect.isgeneratorfunction(func):
                result = func(*args, **kwargs)

                def _gen() -> Any:
                    with use_tracer.start_as_current_span(name):
                        yield from result

                return _gen()

            # A plain function can also return a generator it built internally
            # (e.g. ``return self._inner_gen(x)``). Keep the span open through
            # its iteration too, instead of closing it the instant the call
            # returns the still-unconsumed generator.
            stack = ExitStack()
            stack.enter_context(use_tracer.start_as_current_span(name))
            try:
                result = func(*args, **kwargs)
            except BaseException:
                stack.close()
                raise
            if not inspect.isgenerator(result):
                stack.close()
                return result

            def _gen() -> Any:
                with stack:
                    yield from result

            return _gen()

        return sync_wrapper

    return decorator
