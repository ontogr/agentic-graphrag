"""Tests for graph storage record data models.

Covers NodeRecord and RelationRecord rejecting the internal pending job-id
tag, which only the Cutover Job machinery can write.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from agrag.common.data_models.graph_record import (
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
