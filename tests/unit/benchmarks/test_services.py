"""Tests the compose commands the harness issues and the service table.

A fake command runner records the commands, so no test starts Docker.
"""

import pytest

from benchmarks.harness import services
from benchmarks.harness.services import (
    COMPOSE_FILE,
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
