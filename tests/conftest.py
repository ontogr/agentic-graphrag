"""Adds test markers by directory."""

import os

import pytest


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Add markers to tests under tests/integration/.

    Each collected test under tests/integration/ gets the integration,
    enable_socket, and flaky markers. Test files must not add these markers
    directly. Tests under tests/integration/e2e are skipped on xdist workers
    because they share one database with the rest of the suite.

    Args:
        config: The pytest run configuration.
        items: The collected test items.
    """
    for item in items:
        path = str(item.path).replace("\\", "/")
        if "tests/integration" in path:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.enable_socket)
            item.add_marker(
                pytest.mark.flaky(
                    reruns=3, reruns_delay=30, rerun_except=[AssertionError]
                )
            )
        if "tests/integration/e2e" in path:
            item.add_marker(pytest.mark.slow)
            if os.environ.get("PYTEST_XDIST_WORKER"):
                item.add_marker(
                    pytest.mark.skip(
                        reason="e2e tests share one database; run `make test-e2e`"
                    )
                )
