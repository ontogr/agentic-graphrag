"""Exercise the live-provider availability gate with local HTTP responses.

The tests use an in-process HTTP transport, so they cover provider status handling
without making network requests or reading credentials.
"""

import httpx
import pytest

from tests.integration._live_llm import probe_live_llm


def _transport_for_status(status_code: int) -> httpx.MockTransport:
    """Return a transport that responds with one controlled HTTP status."""

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=status_code, request=request)

    return httpx.MockTransport(respond)


class TestLiveLLMAvailability:
    """Provider access errors skip only when the endpoint denies access."""

    @pytest.mark.parametrize(
        ("status_code", "reason"),
        [
            (401, "LLM provider unavailable (HTTP 401; credentials rejected)"),
            (402, "LLM provider unavailable (HTTP 402; provider credits required)"),
        ],
    )
    def test_unavailable_provider_is_skipped_without_credentials_in_reason(
        self, status_code: int, reason: str
    ) -> None:
        """401 and 402 responses skip without exposing the configured key."""
        with pytest.raises(pytest.skip.Exception) as skipped:
            probe_live_llm(
                "https://provider.invalid/v1",
                "test-secret",
                "test-model",
                transport=_transport_for_status(status_code),
            )

        assert str(skipped.value) == reason
        assert "test-secret" not in str(skipped.value)

    def test_successful_provider_probe_allows_live_tests(self) -> None:
        """A successful completion does not skip the live-provider test."""
        assert (
            probe_live_llm(
                "https://provider.invalid/v1",
                "test-secret",
                "test-model",
                transport=_transport_for_status(200),
            )
            is None
        )

    @pytest.mark.parametrize("status_code", [403, 500])
    def test_other_provider_errors_remain_failures(self, status_code: int) -> None:
        """Statuses other than 401 and 402 continue to fail the test."""
        with pytest.raises(httpx.HTTPStatusError) as error:
            probe_live_llm(
                "https://provider.invalid/v1",
                "test-secret",
                "test-model",
                transport=_transport_for_status(status_code),
            )

        assert error.value.response.status_code == status_code
