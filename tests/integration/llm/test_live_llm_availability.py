"""Check provider skips and the docs fixture without live credentials.

The docs fixture runs in a separate pytest process here so its conftest does not
load the docs-only model dependencies into the integration test collection.
"""

import os
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET
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


def _run_docs_pytest(
    tmp_path: Path,
    test_path: Path,
    report_path: Path,
    env: dict[str, str],
    *,
    forked: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a temporary test file with the provider and docs fixtures."""
    fork_args = ["--forked"] if forked else []
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--confcutdir",
            str(tmp_path),
            *fork_args,
            "-q",
            "-rA",
            "--junitxml",
            str(report_path),
            str(test_path),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )


def _assert_preflight_request_error_is_deferred(
    tmp_path: Path, count_path: Path, env: dict[str, str]
) -> None:
    """Check a collection-time request error reaches the fixture as a failure."""
    test_path = tmp_path / "test_preflight_request_error.py"
    test_path.write_text(
        "def test_provider_request_error_fails_in_fixture(llm_env):\n"
        "    assert llm_env is None\n",
        encoding="utf-8",
    )
    report_path = tmp_path / "request-error-results.xml"
    test_env = env | {"LLM_MODEL_ID": "request-error-model"}
    result = _run_docs_pytest(tmp_path, test_path, report_path, test_env)
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "test-secret" not in output
    case = next(ET.parse(report_path).iter("testcase"))
    assert case.attrib["name"] == "test_provider_request_error_fails_in_fixture"
    error = case.find("error")
    assert error is not None
    assert "RemoteProtocolError" in error.attrib["message"]
    assert (
        count_path.read_text(encoding="utf-8").splitlines().count("request-error-model")
        == 2
    )


def _assert_transient_provider_errors_are_retried(
    tmp_path: Path, count_path: Path, env: dict[str, str]
) -> None:
    """Check forked fixtures retry after transient collection-time failures."""
    test_path = tmp_path / "test_provider_recovery.py"
    test_path.write_text(
        "def test_provider_recovers_after_preflight(llm_env):\n"
        "    assert llm_env is None\n",
        encoding="utf-8",
    )
    for model in ("retry-connect", "retry-timeout"):
        report_path = tmp_path / f"{model}-results.xml"
        test_env = env | {"LLM_MODEL_ID": model}
        result = _run_docs_pytest(tmp_path, test_path, report_path, test_env)
        output = result.stdout + result.stderr

        assert result.returncode == 0, output
        case = next(ET.parse(report_path).iter("testcase"))
        assert case.find("failure") is None
        assert case.find("skipped") is None
        assert case.find("error") is None
        assert count_path.read_text(encoding="utf-8").splitlines().count(model) == 2


def _assert_live_integration_fixture_retries(
    tmp_path: Path, env: dict[str, str]
) -> None:
    """Check a later integration test retries after a transient provider error."""
    test_path = tmp_path / "test_integration_retry.py"
    test_path.write_text(
        "def test_first_provider_check_skips(live_extraction_llm):\n"
        "    assert live_extraction_llm is None\n\n"
        "def test_later_provider_check_retries(live_extraction_llm):\n"
        "    assert live_extraction_llm is None\n",
        encoding="utf-8",
    )
    count_path = tmp_path / "integration-provider-requests.txt"
    test_env = env | {
        "LLM_MODEL_ID": "retry-connect",
        "LLM_TEST_COUNT_FILE": str(count_path),
    }
    report_path = tmp_path / "integration-retry-results.xml"
    result = _run_docs_pytest(tmp_path, test_path, report_path, test_env, forked=False)
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    cases = {
        case.attrib["name"]: case for case in ET.parse(report_path).iter("testcase")
    }
    first = cases["test_first_provider_check_skips"]
    assert first.find("skipped") is not None
    assert "connection failed" in first.find("skipped").attrib["message"]
    later = cases["test_later_provider_check_retries"]
    assert later.find("failure") is None
    assert later.find("skipped") is None
    assert later.find("error") is None
    assert count_path.read_text(encoding="utf-8").splitlines() == [
        "retry-connect",
        "retry-connect",
    ]


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

    def test_rate_limited_provider_probe_is_reachable(self) -> None:
        """A 429 response proves access, so the probe neither skips nor raises."""
        assert (
            probe_live_llm(
                "https://provider.invalid/v1",
                "test-secret",
                "test-model",
                transport=_transport_for_status(429),
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
                        with open(
                            os.environ["LLM_TEST_COUNT_FILE"], "a+", encoding="utf-8"
                        ) as count:
                            count.seek(0)
                            call_number = count.read().splitlines().count(model) + 1
                            count.write(model + "\\n")
                        if model == "request-error-model":
                            raise httpx.RemoteProtocolError(
                                "provider protocol failed", request=request
                            )
                        if (
                            model in ("retry-connect", "retry-timeout")
                            and call_number == 1
                        ):
                            error = (
                                httpx.ConnectError
                                if model == "retry-connect"
                                else httpx.ReadTimeout
                            )
                            raise error("temporary provider outage", request=request)
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
            'pytest_plugins = ["provider_stub", "docs.conftest", '
            '"tests.integration.conftest"]\n',
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
                    ids=[
                        "success", "401", "402", "403", "404", "500",
                        "connect-error", "timeout",
                    ],
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
                    "llm_env", [provider_transport(200)], indirect=True, ids=["success"]
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
        report_path = tmp_path / "docs-fixture-results.xml"
        result = _run_docs_pytest(
            tmp_path, tmp_path / "test_docs_fixture.py", report_path, env
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

        cases = {
            case.attrib["name"]: case for case in ET.parse(report_path).iter("testcase")
        }
        expected_passes = [
            "test_extraction_fixture[success]",
            "test_agent_fixture_uses_configured_model",
        ]
        expected_skips = {
            "test_extraction_fixture[401]": "HTTP 401; credentials rejected",
            "test_extraction_fixture[402]": "HTTP 402; provider credits required",
            "test_extraction_fixture[connect-error]": "connection failed",
            "test_extraction_fixture[timeout]": "request timed out",
            "test_cached_extraction_fixture_first": "HTTP 401; credentials rejected",
            "test_cached_extraction_fixture_second": "HTTP 401; credentials rejected",
        }
        expected_failures = [
            "test_extraction_fixture[403]",
            "test_extraction_fixture[404]",
            "test_extraction_fixture[500]",
            "test_snippet_failure_after_successful_preflight[success]",
        ]
        for case_name in expected_passes:
            assert cases[case_name].find("failure") is None
            assert cases[case_name].find("skipped") is None
            assert cases[case_name].find("error") is None
        for case_name, reason in expected_skips.items():
            skipped = cases[case_name].find("skipped")
            assert skipped is not None
            assert reason in skipped.attrib["message"]
        for case_name in expected_failures:
            case = cases[case_name]
            assert case.find("failure") is not None or case.find("error") is not None

        _assert_preflight_request_error_is_deferred(tmp_path, count_path, env)
        _assert_transient_provider_errors_are_retried(tmp_path, count_path, env)
        _assert_live_integration_fixture_retries(tmp_path, env)

        requests = count_path.read_text(encoding="utf-8").splitlines()
        assert requests.count("cache-model") == 1
        assert requests.count("agent-cache-model") == 1
        assert requests.count("request-error-model") == 2
        assert len(requests) == 8
