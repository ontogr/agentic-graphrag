"""Tests for RetryConfig and call_with_retry in agrag.llm.retry.

Patches ``agrag.llm.retry.sleep`` to record delays instead of actually
sleeping, and pins ``random.uniform`` where exact schedules are asserted.
Covers immediate success without retrying, retrying transient failures with
exponential backoff up to ``max_delay_ms``, jitter bounds on every sleep, raising
the final exception after exhausting retries, ``max_retries=0`` making exactly
one attempt, the overall ``timeout_ms`` deadline
cutting retries short, and ``accept_result`` retrying unusable results until
they pass or budget runs out. TestPermanentBamlFailures verifies BAML client
errors are classified correctly: invalid-argument and HTTP 401 fail once
without retrying, while HTTP 429 and 500 are retried.
"""

import pytest

from agrag.llm.client_config import RetryConfig
from agrag.llm.retry import UnusableResultError, call_with_retry


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
                call, RetryConfig(max_retries=5, delay_ms=1000, timeout_ms=1000)
            )
        assert sleeps == [pytest.approx(0.1)]
        assert calls == 1

    async def test_rejected_result_past_deadline_raises_unusable(
        self, monkeypatch
    ) -> None:
        """A rejected result past the deadline raises instead of retrying."""
        monkeypatch.setattr("agrag.llm.retry.sleep", _no_sleep)
        ticks = iter([0.0, 2000.0])
        monkeypatch.setattr(
            "agrag.llm.retry.time.monotonic", lambda: next(ticks, 2000.0)
        )

        calls = 0

        async def call(options) -> str:
            nonlocal calls
            calls += 1
            return "bad"

        with pytest.raises(UnusableResultError):
            await call_with_retry(
                call,
                RetryConfig(max_retries=5, timeout_ms=1000),
                accept_result=lambda r: False,
            )
        assert calls == 1


class TestAcceptResult:
    """accept_result retries successful calls whose result is unusable."""

    async def test_later_usable_result_is_returned(self, monkeypatch) -> None:
        """A rejected result retries; the first accepted one returns."""
        monkeypatch.setattr("agrag.llm.retry.sleep", _no_sleep)

        calls = 0

        async def call(options) -> str:
            nonlocal calls
            calls += 1
            return "bad" if calls < 2 else "good"

        result = await call_with_retry(
            call, RetryConfig(max_retries=3), accept_result=lambda r: r == "good"
        )
        assert result == "good"
        assert calls == 2

    async def test_always_rejected_result_raises_after_budget(
        self, monkeypatch
    ) -> None:
        """Rejecting every result exhausts the budget like repeated failures."""
        monkeypatch.setattr("agrag.llm.retry.sleep", _no_sleep)

        calls = 0

        async def call(options) -> str:
            nonlocal calls
            calls += 1
            return "bad"

        with pytest.raises(UnusableResultError, match="unusable"):
            await call_with_retry(
                call, RetryConfig(max_retries=2), accept_result=lambda r: False
            )
        assert calls == 3
