"""Tests the compose commands the harness issues and the service table.

A fake command runner records the commands, so no test starts Docker.
"""

import pytest

from benchmarks.harness import services
from benchmarks.harness.services import (
    COMPOSE_FILE,
    BenchSettings,
    Services,
    neo4j_settings,
)


def _services() -> tuple[Services, list[list[str]]]:
    calls: list[list[str]] = []
    return Services(runner=lambda command: calls.append(list(command))), calls


class TestServices:
    """Compose commands issued through a fake command runner."""

    def test_up_waits_for_the_service_to_be_healthy(self):
        """Up waits for the service to be healthy."""
        manager, calls = _services()

        manager.up("fake")

        assert calls[0][4:] == ["up", "-d", "--wait", "fake"]

    def test_stop_keeps_the_volume_and_remove_deletes_it(self):
        """Stop keeps the volume and remove deletes it."""
        manager, calls = _services()

        manager.stop("fake")
        manager.remove("fake")

        assert calls[0][4:] == ["stop", "fake"]
        assert calls[1][4:] == ["down", "-v", "fake"]

    def test_every_command_names_the_benchmark_compose_file(self):
        """Every command names the benchmark compose file."""
        manager, calls = _services()

        manager.up("fake")

        assert calls[0][:4] == ["docker", "compose", "-f", str(COMPOSE_FILE)]

    def test_connection_settings_use_the_loopback_address_and_the_service_port(
        self, monkeypatch
    ):
        """Connection settings use the loopback address and the service port."""
        monkeypatch.setenv(services.PASSWORD_VARIABLE, "from-the-environment")

        settings = neo4j_settings("fake")

        assert settings.uri == f"bolt://127.0.0.1:{services.SERVICE_PORTS['fake']}"
        assert settings.password.get_secret_value() == "from-the-environment"

    def test_connection_settings_require_the_password_variable(self, monkeypatch):
        """Connection settings require the password variable."""
        monkeypatch.delenv(services.PASSWORD_VARIABLE, raising=False)

        with pytest.raises(RuntimeError, match=services.PASSWORD_VARIABLE):
            neo4j_settings("fake")


class TestComposeFile:
    """The compose file agrees with the service table."""

    def test_the_fake_service_port_and_the_password_variable_match_the_compose_file(
        self,
    ):
        """The fake service port and the password variable match the compose file."""
        text = COMPOSE_FILE.read_text()

        assert f"neo4j/${{{services.PASSWORD_VARIABLE}:?" in text
        assert f'"127.0.0.1:{services.SERVICE_PORTS["fake"]}:7687"' in text


class TestBenchSettings:
    """Harness settings read from the ``BENCH_`` environment."""

    def test_trace_repo_comes_from_the_environment(self, monkeypatch):
        """The trace repo is read from ``BENCH_TRACE_REPO``."""
        monkeypatch.setenv("BENCH_TRACE_REPO", "me/traces")

        assert BenchSettings().trace_repo == "me/traces"

    def test_trace_repo_is_none_when_unset(self, monkeypatch):
        """An unset ``BENCH_TRACE_REPO`` leaves the trace repo empty."""
        monkeypatch.delenv("BENCH_TRACE_REPO", raising=False)

        assert BenchSettings(_env_file=None).trace_repo is None
