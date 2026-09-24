"""Compares the search rankings that each vector store backend recorded.

``test_vector_backends_e2e.py`` writes one ``vector_backends_<backend>.json``
artifact per backend when that backend finishes. This test reads every such file
in the artifact directory and asserts that all backends ranked the same names in
the same order. It runs no search itself and needs no service.

The test fails, and does not skip, when fewer than two artifacts exist. A
missing artifact means a backend did not run, and a skip would hide that.

Ordering: the artifacts must exist before this file runs. In one local session,
pytest runs files in alphabetical order, so ``test_vector_backends_parity.py``
runs after ``test_vector_backends_e2e.py``. In CI, run each backend as its own
job, upload ``reports/e2e/``, then run this file in a job that downloads all the
artifacts into ``reports/e2e/`` (or into ``E2E_ARTIFACT_DIR``).
"""

import json

from tests.integration.e2e._artifact import artifact_dir


class TestVectorBackendsParity:
    """Every backend that ran returned identical rankings."""

    def test_backends_return_identical_rankings(self) -> None:
        """The ordered top results match across all recorded backends."""
        paths = sorted(artifact_dir().glob("vector_backends_*.json"))
        rankings = {
            path.stem.removeprefix("vector_backends_"): json.loads(path.read_text())[
                "rankings"
            ]
            for path in paths
        }

        assert len(rankings) >= 2, (
            f"need artifacts from at least two backends, found {sorted(rankings)}"
        )
        reference_name, *others = sorted(rankings)
        for other in others:
            assert rankings[other] == rankings[reference_name], (
                f"{other} differs from {reference_name}"
            )
