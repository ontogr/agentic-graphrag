"""Artifact writer shared by the e2e tests.

Every e2e test ends by writing one JSON file that records what the run produced
and then reads the file back to assert on it. The file is the verifiable and
repeatable record of the scenario: it holds names, counts, and ordered results,
never random ids, timestamps, or per-run label suffixes, so two runs of the same
test write identical bytes.

Files go to ``reports/e2e/`` at the repo root, or to the directory in
``E2E_ARTIFACT_DIR``. CI uploads that directory.
"""

import json
import os
from collections.abc import Mapping
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]


def artifact_dir() -> Path:
    """Return the directory that receives e2e artifacts."""
    configured = os.environ.get("E2E_ARTIFACT_DIR")
    return Path(configured) if configured else _REPO_ROOT / "reports" / "e2e"


def write_artifact(name: str, payload: Mapping[str, object]) -> dict[str, object]:
    """Write ``payload`` as ``<name>.json`` and return the parsed file content.

    Keys are sorted and the output ends with a newline, so equal payloads give
    equal files. Callers assert on the returned content, which proves the record
    survives a round trip through the file.

    Args:
        name: File stem, unique per test.
        payload: JSON-serializable record of the scenario outcome.

    Returns:
        The payload as read back from the written file.
    """
    directory = artifact_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return json.loads(path.read_text())
