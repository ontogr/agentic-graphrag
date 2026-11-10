"""Check provider skips and the docs fixture without live credentials.

The docs fixture runs in a separate pytest process here so its conftest does not
load the docs-only model dependencies into the integration test collection.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import httpx
import pytest

from tests.integration._live_llm import probe_live_llm


def _transport_for_status(status_code: int) -> httpx.MockTransport:
    """Return a transport that responds with one controlled HTTP status."""

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=status_code, request=request)

    return httpx.MockTransport(respond)


def _transport_for_error(error: httpx.RequestError) -> httpx.MockTransport:
    """Return a transport that raises one controlled request error."""

    def respond(request: httpx.Request) -> httpx.Response:
        error.request = request
        raise error

    return httpx.MockTransport(respond)


class TestLiveLLMAvailability:
    """Check provider access handling at the live-test and docs boundaries."""

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

    @pytest.mark.parametrize(
        ("error", "reason"),
        [
            (
                httpx.ConnectError("connection failed: test-secret"),
                "LLM provider unavailable (connection failed)",
            ),
            (
                httpx.ReadTimeout("request timed out: test-secret"),
                "LLM provider unavailable (request timed out)",
            ),
        ],
    )
    def test_preflight_connection_errors_are_skipped_without_details(
        self, error: httpx.RequestError, reason: str
    ) -> None:
        """Connection failures and timeouts skip with secret-free reasons."""
        with pytest.raises(pytest.skip.Exception) as skipped:
            probe_live_llm(
                "https://provider.invalid/v1",
                "test-secret",
                "test-model",
                transport=_transport_for_error(error),
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

    @pytest.mark.parametrize("status_code", [403, 404, 500])
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

    def test_docs_fixture_skips_only_preflight_unavailability(
        self, tmp_path: Path
    ) -> None:
        """The docs fixture skips unavailable providers and preserves block errors."""
        repository = Path(__file__).resolve().parents[3]
        count_path = tmp_path / "provider-requests.txt"
        (tmp_path / "provider_stub.py").write_text(
            textwrap.dedent(
                """\
                import json
                import os

                import httpx

                _http_client = httpx.Client

                def _client(*args, **kwargs):
                    def respond(request):
                        model = json.loads(request.content)["model"]
                        with open(os.environ["LLM_TEST_COUNT_FILE"], "a") as count:
                            count.write(model + "\\n")
                        status = 401 if model == "cache-model" else 200
                        return httpx.Response(status, request=request)

                    if kwargs.get("transport") is None:
                        kwargs["transport"] = httpx.MockTransport(respond)
                    return _http_client(*args, **kwargs)

                httpx.Client = _client
                """
            ),
            encoding="utf-8",
        )
        (tmp_path / "conftest.py").write_text(
            'pytest_plugins = ["provider_stub", "docs.conftest"]\n',
            encoding="utf-8",
        )
        (tmp_path / "test_docs_fixture.py").write_text(
            textwrap.dedent(
                """\
                import httpx
                import pytest

                def provider_transport(status):
                    def respond(request):
                        if status == "connect-error":
                            raise httpx.ConnectError(
                                "connection failed: test-secret", request=request
                            )
                        if status == "timeout":
                            raise httpx.ReadTimeout(
                                "request timed out: test-secret", request=request
                            )
                        return httpx.Response(status, request=request)

                    return httpx.MockTransport(respond)

                @pytest.mark.parametrize(
                    "llm_env",
                    [provider_transport(status) for status in (
                        200, 401, 402, 403, 404, 500,
                        "connect-error", "timeout",
                    )],
                    indirect=True,
                )
                def test_extraction_fixture(llm_env):
                    assert llm_env is None

                def test_cached_extraction_fixture_first(llm_env):
                    assert llm_env is None

                def test_cached_extraction_fixture_second(llm_env):
                    assert llm_env is None

                def test_agent_fixture_uses_configured_model(agent_llm_env):
                    assert agent_llm_env is None

                @pytest.mark.parametrize(
                    "llm_env", [provider_transport(200)], indirect=True
                )
                def test_snippet_failure_after_successful_preflight(llm_env):
                    assert llm_env is None
                    raise AssertionError("actual snippet failure")
                """
            ),
            encoding="utf-8",
        )

        env = os.environ.copy()
        for name in (
            "LLM_BASE_URL",
            "LLM_API_KEY",
            "LLM_MODEL_ID",
            "AGENT_LLM_BASE_URL",
            "AGENT_LLM_API_KEY",
            "AGENT_LLM_MODEL_ID",
        ):
            env.pop(name, None)
        env.update(
            {
                "LLM_BASE_URL": "https://provider.invalid/v1",
                "LLM_API_KEY": "test-secret",
                "LLM_MODEL_ID": "cache-model",
                "AGENT_LLM_BASE_URL": "https://provider.invalid/v1",
                "AGENT_LLM_API_KEY": "test-secret",
                "AGENT_LLM_MODEL_ID": "agent-cache-model",
                "LLM_TEST_COUNT_FILE": str(count_path),
                "PYTHONPATH": os.pathsep.join(
                    part
                    for part in (
                        str(repository),
                        str(tmp_path),
                        os.environ.get("PYTHONPATH", ""),
                    )
                    if part
                ),
            }
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--confcutdir",
                str(tmp_path),
                "--forked",
                "-q",
                "-rs",
                str(tmp_path / "test_docs_fixture.py"),
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        output = result.stdout + result.stderr

        assert result.returncode != 0
        assert "LLM provider unavailable (HTTP 401; credentials rejected)" in output
        assert (
            "LLM provider unavailable (HTTP 402; provider credits required)" in output
        )
        assert "LLM provider unavailable (connection failed)" in output
        assert "LLM provider unavailable (request timed out)" in output
        assert "actual snippet failure" in output
        assert "test-secret" not in output

        requests = count_path.read_text(encoding="utf-8").splitlines()
        assert requests.count("cache-model") == 1
        assert requests.count("agent-cache-model") == 1
        assert len(requests) == 2
