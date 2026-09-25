"""Shared fixtures for the agrag.eval unit tests."""

import pytest


@pytest.fixture(autouse=True)
def _deepeval_telemetry_opt_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep DeepEval from sending telemetry during unit tests."""
    monkeypatch.setenv("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
