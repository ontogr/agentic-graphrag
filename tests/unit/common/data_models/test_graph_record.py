"""Tests for graph storage record data models.

Covers NodeRecord and RelationRecord rejecting the internal pending job-id
tag, which only the Cutover Job machinery can write.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from agrag.common.data_models.graph_record import (
    DeferredWrites,
    NodeRecord,
    RelationRecord,
)


@pytest.mark.parametrize("record_type", [NodeRecord, RelationRecord])
def test_graph_records_reject_the_internal_pending_tag(record_type: type) -> None:
    """External graph records cannot provide the job-owned pending tag."""
    fields = {
        "id": uuid4(),
        "properties": {"_pending_job_id": "foreign-job"},
    }
    if record_type is NodeRecord:
        fields["labels"] = ["Entity"]
    else:
        fields.update(type="MENTIONS", start_id=uuid4(), end_id=uuid4())

    with pytest.raises(ValidationError, match="_pending_job_id is reserved"):
        record_type(**fields)


class TestDeferredWrites:
    """Only the records a write reports as unwritten are held for the commit."""

    def test_defers_only_rows_reported_unwritten(self) -> None:
        """A record whose row was written is not replayed; an unwritten one is."""
        deferred = DeferredWrites()
        records = [
            {"id": "a", "pending_job_id": "j", "properties": {}},
            {"id": "b", "pending_job_id": "j", "properties": {}},
            {"id": "c", "pending_job_id": "j", "properties": {}},
        ]
        rows = [
            {"id": "a", "written": True},
            {"id": "b", "written": False},
        ]

        deferred.add_unwritten("Q", records, rows)

        assert deferred.entries == [
            (
                "Q",
                {
                    "records": [{"id": "b", "pending_job_id": None, "properties": {}}],
                    "require_all": True,
                },
            )
        ]

    def test_records_without_a_row_are_not_deferred(self) -> None:
        """A record the query returned no row for is not held."""
        deferred = DeferredWrites()

        deferred.add_unwritten("Q", [{"id": "c", "pending_job_id": "j"}], [])

        assert len(deferred) == 0
