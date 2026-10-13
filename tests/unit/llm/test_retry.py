"""Tests for RetryConfig and call_with_retry in agrag.llm.retry.

Patches ``agrag.llm.retry.sleep`` to record delays instead of actually
sleeping, and pins ``random.uniform`` where exact schedules are asserted.
Covers immediate success without retrying, retrying transient failures with
exponential backoff up to ``max_delay_ms``, jitter bounds on every sleep, raising
the final exception after exhausting retries, ``max_retries=0`` making exactly
one attempt, the overall ``timeout_ms`` deadline cutting retries short, and
request-level timeouts cancelling slow attempts. TestPermanentBamlFailures
verifies BAML client errors: invalid-argument and HTTP 401 fail once, while
HTTP 408, 429 and 500 are retried.
"""

import asyncio

import pytest

from agrag.llm.client_config import RetryConfig
from agrag.llm.retry import call_with_retry


def test_retry_defaults_allow_longer_backoff_and_bound_requests() -> None:
    """Defaults use second-scale backoff and a five-minute attempt limit."""
    retry = RetryConfig()

    assert retry.delay_ms == 1_000
    assert retry.multiplier == 2.0
    assert retry.max_delay_ms == 30_000
    assert retry.request_timeout_ms == 300_000


def _pin_jitter(monkeypatch) -> None:
    """Make jitter deterministic by always taking the top of its range."""
    monkeypatch.setattr("agrag.llm.retry.random.uniform", lambda low, high: high)


class TestCallWithRetry:
    """call_with_retry retries failures with exponential backoff, then gives up."""

    async def test_returns_first_success_without_retrying(self) -> None:
        """A call that succeeds immediately runs exactly once."""
        calls = 0

        async def call(options) -> str:
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
        _pin_jitter(monkeypatch)

        calls = 0

        async def call(options) -> str:
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

        async def call(options) -> str:
            raise RuntimeError("still failing")

        with pytest.raises(RuntimeError, match="still failing"):
            await call_with_retry(call, RetryConfig(max_retries=2, delay_ms=1))

    async def test_zero_max_retries_calls_once_and_raises_immediately(self) -> None:
        """max_retries=0 means one attempt, no sleep, immediate failure."""
        calls = 0

        async def call(options) -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await call_with_retry(call, RetryConfig(max_retries=0))
        assert calls == 1

    async def test_delay_is_capped_at_max_delay_ms(self, monkeypatch) -> None:
        """Backoff delay never exceeds max_delay_ms, even after growth."""
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr("agrag.llm.retry.sleep", fake_sleep)
        _pin_jitter(monkeypatch)

        calls = 0

        async def call(options) -> str:
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


class TestDefaultBackoff:
    """The default retry schedule waits several seconds in total."""

    async def test_default_retries_wait_at_least_three_and_a_half_seconds(
        self, monkeypatch
    ) -> None:
        """Three default waits total at least 3.5 seconds with minimum jitter."""
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr("agrag.llm.retry.sleep", fake_sleep)
        monkeypatch.setattr("agrag.llm.retry.random.uniform", lambda low, high: low)

        async def call(options) -> str:
            raise RuntimeError("rate limited")

        with pytest.raises(RuntimeError):
            await call_with_retry(call, RetryConfig())

        assert len(sleeps) == 3
        assert sum(sleeps) >= 3.5


class TestPermanentBamlFailures:
    """A BAML error that would fail identically on retry is not retried."""

    async def test_invalid_argument_error_is_not_retried(self) -> None:
        """A malformed call argument fails once, not four times."""
        from baml_py.errors import BamlInvalidArgumentError  # noqa: PLC0415

        calls = 0

        async def call(options) -> str:
            nonlocal calls
            calls += 1
            raise BamlInvalidArgumentError("bad argument")

        with pytest.raises(BamlInvalidArgumentError):
            await call_with_retry(call, RetryConfig(max_retries=3))
        assert calls == 1

    async def test_http_401_is_not_retried(self) -> None:
        """An auth failure fails once, not four times."""
        from baml_py.errors import BamlClientHttpError  # noqa: PLC0415

        calls = 0

        async def call(options) -> str:
            nonlocal calls
            calls += 1
            raise BamlClientHttpError("client", "unauthorized", 401, "detail")

        with pytest.raises(BamlClientHttpError):
            await call_with_retry(call, RetryConfig(max_retries=3))
        assert calls == 1

    async def test_http_429_is_still_retried(self, monkeypatch) -> None:
        """A rate-limit response is retried, since it can succeed later."""
        from baml_py.errors import BamlClientHttpError  # noqa: PLC0415

        async def fake_sleep(seconds: float) -> None:
            return None

        monkeypatch.setattr("agrag.llm.retry.sleep", fake_sleep)

        calls = 0

        async def call(options) -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise BamlClientHttpError("client", "rate limited", 429, "detail")
            return "ok"

        result = await call_with_retry(call, RetryConfig(max_retries=3))
        assert result == "ok"
        assert calls == 2

    async def test_http_408_is_still_retried(self, monkeypatch) -> None:
        """A request-timeout response can succeed on the next try."""
        from baml_py.errors import BamlClientHttpError  # noqa: PLC0415

        monkeypatch.setattr("agrag.llm.retry.sleep", _no_sleep)
        calls = 0

        async def call(options) -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise BamlClientHttpError("client", "timeout", 408, "detail")
            return "ok"

        assert await call_with_retry(call, RetryConfig(max_retries=3)) == "ok"
        assert calls == 2

    async def test_http_500_is_still_retried(self, monkeypatch) -> None:
        """A server error is retried, since it may be a transient provider hiccup."""
        from baml_py.errors import BamlClientHttpError  # noqa: PLC0415

        async def fake_sleep(seconds: float) -> None:
            return None

        monkeypatch.setattr("agrag.llm.retry.sleep", fake_sleep)

        calls = 0

        async def call(options) -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise BamlClientHttpError("client", "server error", 500, "detail")
            return "ok"

        result = await call_with_retry(call, RetryConfig(max_retries=3))
        assert result == "ok"
        assert calls == 2


async def _no_sleep(seconds: float) -> None:
    """Stand-in for sleep that records nothing and waits no time."""


class TestJitter:
    """Every sleep carries jitter within half to full of the nominal delay."""

    async def test_sleeps_stay_within_jitter_bounds(self, monkeypatch) -> None:
        """Jittered sleeps never leave [0.5x, 1.0x] of the capped delay."""
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr("agrag.llm.retry.sleep", fake_sleep)

        calls = 0

        async def call(options) -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError("transient")
            return "ok"

        result = await call_with_retry(
            call,
            RetryConfig(max_retries=2, delay_ms=100, multiplier=1),
        )
        assert result == "ok"
        assert len(sleeps) == 2
        assert all(0.05 <= s <= 0.1 for s in sleeps)


class TestTimeout:
    """timeout_ms bounds the whole call without interrupting an attempt."""

    async def test_elapsed_deadline_raises_the_last_failure(self, monkeypatch) -> None:
        """A blown deadline stops retrying and raises what the call raised."""
        monkeypatch.setattr("agrag.llm.retry.sleep", _no_sleep)
        ticks = iter([0.0, 2000.0])
        monkeypatch.setattr(
            "agrag.llm.retry.time.monotonic", lambda: next(ticks, 2000.0)
        )

        calls = 0

        async def call(options) -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError("still failing")

        with pytest.raises(RuntimeError, match="still failing"):
            await call_with_retry(call, RetryConfig(max_retries=5, timeout_ms=1000))
        assert calls == 1

    async def test_zero_timeout_disables_the_deadline(self, monkeypatch) -> None:
        """timeout_ms=0 keeps the attempt budget as the only limit."""
        monkeypatch.setattr("agrag.llm.retry.sleep", _no_sleep)

        calls = 0

        async def call(options) -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError("still failing")

        with pytest.raises(RuntimeError):
            await call_with_retry(call, RetryConfig(max_retries=2, timeout_ms=0))
        assert calls == 3

    async def test_sleep_is_clamped_and_no_attempt_starts_past_deadline(
        self, monkeypatch
    ) -> None:
        """A sleep that would cross the deadline is cut short, then stops."""
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr("agrag.llm.retry.sleep", fake_sleep)
        _pin_jitter(monkeypatch)
        ticks = iter([0.0, 0.9, 1.5])
        monkeypatch.setattr("agrag.llm.retry.time.monotonic", lambda: next(ticks, 1.5))

        calls = 0

        async def call(options) -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError("still failing")

        with pytest.raises(RuntimeError, match="still failing"):
            await call_with_retry(
                call,
                RetryConfig(
                    max_retries=5,
                    delay_ms=1000,
                    timeout_ms=1000,
                    request_timeout_ms=0,
                ),
            )
        assert sleeps == [pytest.approx(0.1)]
        assert calls == 1


class TestRequestTimeout:
    """request_timeout_ms limits one attempt and can be disabled."""

    async def test_a_hung_attempt_times_out_and_is_retried(self, monkeypatch) -> None:
        """A timed-out attempt counts as a failure and permits a retry."""
        monkeypatch.setattr("agrag.llm.retry.sleep", _no_sleep)
        calls = 0
        cancelled = asyncio.Event()

        async def call(options) -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                try:
                    await asyncio.sleep(10)
                finally:
                    cancelled.set()
            return "ok"

        result = await call_with_retry(
            call, RetryConfig(max_retries=1, request_timeout_ms=20)
        )

        assert result == "ok"
        assert calls == 2
        assert cancelled.is_set()

    async def test_zero_disables_the_request_timeout(self) -> None:
        """A zero request timeout allows an attempt to finish."""

        async def call(options) -> str:
            await asyncio.sleep(0.05)
            return "ok"

        assert await call_with_retry(call, RetryConfig(request_timeout_ms=0)) == "ok"

    async def test_external_cancellation_propagates(self, monkeypatch) -> None:
        """Cancellation of the whole call is not treated as a retryable failure."""
        monkeypatch.setattr("agrag.llm.retry.sleep", _no_sleep)
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def call(options) -> str:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        task = asyncio.create_task(
            call_with_retry(call, RetryConfig(max_retries=3, request_timeout_ms=0))
        )
        await started.wait()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled.is_set()
