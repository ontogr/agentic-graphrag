"""Pending-record bookkeeping shared by the VectorStore adapters.

A record written for an in-flight Cutover Job lands under a staging id, so a
committed record with the real id stays searchable until the job commits and
survives the job's rollback.
"""

from collections.abc import Sequence
from uuid import UUID, uuid5

from agrag.common.data_models.graph_record import PENDING_JOB_ID_PROPERTY
from agrag.common.data_models.vector_record import VectorRecord


PENDING_FLAG = "_pending"
"""Payload boolean that is true while a record belongs to an in-flight job."""

PENDING_JOB_KEY = PENDING_JOB_ID_PROPERTY
"""Payload key holding the id of the job that wrote a staged record."""

TARGET_ID_KEY = "_target_id"
"""Payload key holding the real id a staged record is promoted to."""

RESERVED_KEYS = frozenset({PENDING_FLAG, PENDING_JOB_KEY, TARGET_ID_KEY})
"""Payload keys the stores own; a caller payload may not use them."""


def stage_records(
    records: Sequence[VectorRecord], pending_job_id: UUID | None
) -> list[VectorRecord]:
    """Return records ready to write for one job, or unchanged outside a job.

    Args:
        records: The records the caller wants to write.
        pending_job_id: The in-flight job's id. None writes the records as
            committed.

    Returns:
        With a job id, copies under staging ids that carry the pending flag,
        the job id and the real id. Without one, the records unchanged.

    Raises:
        ValueError: A record payload uses a reserved pending key.
    """
    for record in records:
        reserved = sorted(RESERVED_KEYS & record.payload.keys())
        if reserved:
            raise ValueError(
                f"Payload key '{reserved[0]}' is reserved for pending records"
            )
    if pending_job_id is None:
        return list(records)
    return [
        VectorRecord(
            id=uuid5(pending_job_id, str(record.id)),
            vector=record.vector,
            payload={
                **record.payload,
                PENDING_FLAG: True,
                PENDING_JOB_KEY: str(pending_job_id),
                TARGET_ID_KEY: str(record.id),
            },
        )
        for record in records
    ]


def promote_record(record: VectorRecord) -> VectorRecord:
    """Return the committed record a staged record stands for.

    Args:
        record: A record read back from the store with a staging id.

    Returns:
        A record under the real id, without the pending keys.

    Raises:
        KeyError: The record carries no real id, so it is not staged.
    """
    payload = {
        key: value for key, value in record.payload.items() if key not in RESERVED_KEYS
    }
    return VectorRecord(
        id=UUID(str(record.payload[TARGET_ID_KEY])),
        vector=record.vector,
        payload=payload,
    )
