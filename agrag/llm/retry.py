"""Async retry with exponential backoff, driven by a RetryConfig.

BAML's own ``ClientRegistry.add_llm_client(retry_policy=...)`` only accepts the
name of a retry policy already declared in ``.baml`` source — there is no way
to register one with arbitrary numeric values at runtime. Retrying here in
Python is the only way an env-configured ``RetryConfig`` can actually take
effect.
"""

from asyncio import sleep
from collections.abc import Awaitable, Callable
from typing import TypeVar

from agrag.llm.client_config import RetryConfig


_T = TypeVar("_T")

NO_RETRY = RetryConfig(max_retries=0)


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


async def call_with_retry(call: Callable[[], Awaitable[_T]], retry: RetryConfig) -> _T:
    """Retry an async call with exponential backoff.

    Args:
        call: A zero-argument async callable. Invoked at least once.
        retry: Backoff settings. ``max_retries`` is the number of retries
            after the first attempt.

    Returns:
        The first successful call's result.

    Raises:
        Exception: The last attempt's exception, if every attempt fails, or
            immediately for a BAML error that would fail identically on
            retry (an invalid argument, or an HTTP 4xx other than 429).
    """
    attempts = retry.max_retries + 1
    delay_seconds = retry.delay_ms / 1000
    max_delay_seconds = retry.max_delay_ms / 1000
    for attempt in range(attempts):
        try:
            return await call()
        except Exception as exc:  # noqa: BLE001
            if attempt == attempts - 1 or _is_permanently_unretryable(exc):
                raise
            await sleep(min(delay_seconds, max_delay_seconds))
            delay_seconds = min(delay_seconds * retry.multiplier, max_delay_seconds)
    raise AssertionError("unreachable: the loop above always returns or raises")
