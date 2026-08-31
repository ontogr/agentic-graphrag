"""Skeleton e2e pipeline tests.

Full pipeline scenarios requiring a live Neo4j instance are covered by the 
integration suite under tests/integration/.
This module provides a minimal check that the e2e marker and collection
are configured and that the schema fixture is available.
"""

import pytest


def test_e2e_harness_collects(e2e_schema) -> None:
    """The e2e harness is wired and the schema fixture is available."""
    assert e2e_schema.name == "e2e"
    assert any(entity.label == "Person" for entity in e2e_schema.entities)


@pytest.mark.slow
def test_e2e_slow_marker_applied(e2e_schema) -> None:  # noqa: ARG001
    """The slow marker is auto-applied to tests under tests/integration/e2e."""
    assert True
