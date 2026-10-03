"""Tests for the pending-record helpers."""

from uuid import uuid4

import pytest

from agrag.common.data_models.vector_record import VectorRecord
from agrag.vectordb.pending import stage_records


class TestStageRecords:
    """Callers cannot use the keys the stores reserve."""

    @pytest.mark.parametrize("key", ["_pending", "_pending_job_id", "_target_id"])
    @pytest.mark.parametrize("job_id", [None, uuid4()])
    def test_rejects_reserved_payload_keys(self, key: str, job_id) -> None:
        """Staged and direct writes both refuse a reserved key."""
        record = VectorRecord(id=uuid4(), vector=[1.0], payload={key: True})

        with pytest.raises(ValueError, match=key):
            stage_records([record], job_id)
