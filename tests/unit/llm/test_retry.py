"""Tests for the async retry-with-backoff helper."""

import pytest

from agrag.llm.client_config import RetryConfig
from agrag.llm.retry import NO_RETRY, call_with_retry


class TestCallWithRetry:
    """call_with_retry retries failures with exponential backoff, then gives up."""

    async def test_returns_first_success_without_retrying(self) -> None:
        """A call that succeeds immediately runs exactly once."""
        calls = 0

        async def call() -> str:
            nonlocal calls
            calls += 1
            return "ok"

        result = await call_with_retry(call, RetryConfig(max_retries=3))
        assert result == "ok"
        assert calls == 1

    async def test_retries_transient_failures_then_succeeds(self, monkeypatch) -> None:
        """A call that fails twice then succeeds is retried, not aborted."""
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr("agrag.llm.retry.sleep", fake_sleep)

        calls = 0

        async def call() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError("transient")
            return "ok"

        result = await call_with_retry(
            call,
            RetryConfig(max_retries=3, delay_ms=100, multiplier=2, max_delay_ms=10_000),
        )
        assert result == "ok"
        assert calls == 3
        assert sleeps == [0.1, 0.2]

    async def test_raises_the_last_exception_after_exhausting_retries(
        self, monkeypatch
    ) -> None:
        """Every attempt failing raises the final attempt's exception."""

        async def fake_sleep(seconds: float) -> None:
            return None

        monkeypatch.setattr("agrag.llm.retry.sleep", fake_sleep)

        async def call() -> str:
            raise RuntimeError("still failing")

        with pytest.raises(RuntimeError, match="still failing"):
            await call_with_retry(call, RetryConfig(max_retries=2, delay_ms=1))

    async def test_zero_max_retries_calls_once_and_raises_immediately(self) -> None:
        """max_retries=0 means one attempt, no sleep, immediate failure."""
        calls = 0

        async def call() -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await call_with_retry(call, RetryConfig(max_retries=0))
        assert calls == 1

    async def test_negative_max_retries_is_treated_as_zero(self) -> None:
        """A negative max_retries still makes exactly one attempt."""
        calls = 0

        async def call() -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await call_with_retry(call, RetryConfig(max_retries=-1))
        assert calls == 1

    async def test_delay_is_capped_at_max_delay_ms(self, monkeypatch) -> None:
        """Backoff delay never exceeds max_delay_ms, even after growth."""
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr("agrag.llm.retry.sleep", fake_sleep)

        calls = 0

        async def call() -> str:
            nonlocal calls
            calls += 1
            if calls <= 3:
                raise RuntimeError("transient")
            return "ok"

        await call_with_retry(
            call,
            RetryConfig(max_retries=3, delay_ms=1000, multiplier=10, max_delay_ms=1500),
        )
        assert sleeps == [1.0, 1.5, 1.5]


class TestNoRetry:
    """NO_RETRY is a RetryConfig that makes exactly one attempt."""

    def test_no_retry_has_zero_max_retries(self) -> None:
        """NO_RETRY disables retrying entirely."""
        assert NO_RETRY.max_retries == 0
