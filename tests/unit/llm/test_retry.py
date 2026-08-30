"""Tests for the async retry-with-backoff helper."""

import pytest
from pydantic import ValidationError

from agrag.llm.client_config import RetryConfig
from agrag.llm.retry import NO_RETRY, call_with_retry


class TestRetryConfig:
    """RetryConfig rejects negative backoff settings at construction."""

    @pytest.mark.parametrize(
        "field", ["max_retries", "delay_ms", "multiplier", "max_delay_ms"]
    )
    def test_rejects_negative_value(self, field: str) -> None:
        """A negative value for any backoff field raises ValidationError."""
        with pytest.raises(ValidationError):
            RetryConfig(**{field: -1})


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


class TestPermanentBamlFailures:
    """A BAML error that would fail identically on retry is not retried."""

    async def test_invalid_argument_error_is_not_retried(self) -> None:
        """A malformed call argument fails once, not four times."""
        from baml_py.errors import BamlInvalidArgumentError  # noqa: PLC0415

        calls = 0

        async def call() -> str:
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

        async def call() -> str:
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

        async def call() -> str:
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

        async def call() -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise BamlClientHttpError("client", "server error", 500, "detail")
            return "ok"

        result = await call_with_retry(call, RetryConfig(max_retries=3))
        assert result == "ok"
        assert calls == 2


class TestNoRetry:
    """NO_RETRY is a RetryConfig that makes exactly one attempt."""

    def test_no_retry_has_zero_max_retries(self) -> None:
        """NO_RETRY disables retrying entirely."""
        assert NO_RETRY.max_retries == 0
