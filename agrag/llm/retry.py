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


async def call_with_retry(call: Callable[[], Awaitable[_T]], retry: RetryConfig) -> _T:
    """Retry an async call with exponential backoff.

    Args:
        call: A zero-argument async callable. Invoked at least once.
        retry: Backoff settings. ``max_retries`` is the number of retries
            after the first attempt.

    Returns:
        The first successful call's result.

    Raises:
        Exception: The last attempt's exception, if every attempt fails.
    """
    attempts = retry.max_retries + 1
    delay_seconds = retry.delay_ms / 1000
    max_delay_seconds = retry.max_delay_ms / 1000
    for attempt in range(attempts):
        try:
            return await call()
        except Exception:  # noqa: BLE001
            if attempt == attempts - 1:
                raise
            await sleep(min(delay_seconds, max_delay_seconds))
            delay_seconds = min(delay_seconds * retry.multiplier, max_delay_seconds)
    raise AssertionError("unreachable: the loop above always returns or raises")
