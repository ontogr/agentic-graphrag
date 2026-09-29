"""Adds the fake compose services to the port table for the whole suite."""

import pytest

from benchmarks.harness import services


@pytest.fixture(autouse=True)
def fake_services(monkeypatch: pytest.MonkeyPatch) -> None:
    """Register the two fake services that the fake domain uses."""
    monkeypatch.setitem(services.SERVICE_PORTS, "fake", 7700)
    monkeypatch.setitem(services.SERVICE_PORTS, "fake2", 7701)
