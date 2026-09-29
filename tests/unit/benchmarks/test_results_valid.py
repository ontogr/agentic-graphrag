"""Checks that every committed run record still validates against ``RunRecord``.

The check passes with no records. It fails when a record on disk no longer matches
the model, so a model change must update the committed runs in the same change.
"""

from benchmarks.harness.record import RESULTS_DIR, RunRecord


def test_every_committed_record_validates():
    """Every committed record validates."""
    for path in sorted(RESULTS_DIR.glob("*/*/record.json")):
        record = RunRecord.model_validate_json(path.read_text(encoding="utf-8"))

        assert record.lands_in_results, path
        assert record.mode == path.parent.parent.name, path
        assert record.run_id == path.parent.name, path
