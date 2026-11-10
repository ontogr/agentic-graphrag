"""Exercise the live-provider availability gate with local HTTP responses.

The tests use an in-process HTTP transport, so they cover provider status handling
without making network requests or reading credentials.
"""

from functools import partial

import httpx
import pytest

import docs.conftest as docs_conftest
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

    @pytest.mark.parametrize("status_code", [200, 401, 402, 403, 500])
    def test_docs_fixture_handles_provider_responses_at_the_block_boundary(
        self, status_code: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The docs fixture skips unavailable access and propagates other errors."""
        monkeypatch.setenv("LLM_BASE_URL", "https://provider.invalid/v1")
        monkeypatch.setenv("LLM_API_KEY", "test-secret")
        monkeypatch.setenv("LLM_MODEL_ID", "test-model")
        client_class = httpx.Client
        monkeypatch.setattr(
            docs_conftest.httpx,
            "Client",
            partial(
                client_class,
                transport=_transport_for_status(status_code),
            ),
        )

        if status_code == 200:
            assert docs_conftest.llm_env.__wrapped__() is None
        elif status_code in (401, 402):
            with pytest.raises(pytest.skip.Exception) as skipped:
                docs_conftest.llm_env.__wrapped__()

            reason = (
                "credentials rejected"
                if status_code == 401
                else "provider credits required"
            )
            assert str(skipped.value) == (
                f"LLM provider unavailable (HTTP {status_code}; {reason})"
            )
            assert "test-secret" not in str(skipped.value)
        else:
            with pytest.raises(httpx.HTTPStatusError) as error:
                docs_conftest.llm_env.__wrapped__()

            assert error.value.response.status_code == status_code
