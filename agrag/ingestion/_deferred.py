"""Run a guarded write now, or hold the rows it did not apply until commit.

A job writes only the rows it created. A write that reaches a committed row
reports ``written`` false, and the record is kept in a ``DeferredWrites`` list.
The commit transaction replays that list after the job flips to committed, so
committed rows change only together with the commit.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from agrag.common.data_models.graph_record import DeferredWrites
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.graphdb.errors import GraphStoreWriteConflictError


_REPLAY_BATCH_SIZE = 256


async def write_or_defer(
    executor: GraphStore | GraphStoreTransaction,
    query: str,
    records: Sequence[Mapping[str, Any]],
    *,
    deferred: DeferredWrites | None,
) -> list[dict[str, Any]]:
    """Run a batched guarded write and defer the records it did not apply.

    Args:
        executor: Where the write runs. A store or a transaction.
        query: A query whose rows carry ``id`` and ``written``.
        records: The ``$records`` for the query. Each record carries the
            ``pending_job_id`` the query compares against.
        deferred: Where the unapplied records go. None when there is no job,
            in which case no record can be reported unwritten.

    Returns:
        The rows the query returned, so callers can read the matched ids.
    """
    rows = await executor.execute_write(query, {"records": list(records)})
    if deferred is not None:
        deferred.add_unwritten(query, records, rows, require_all=False)
    return rows


async def replay_deferred(txn: GraphStoreTransaction, deferred: DeferredWrites) -> None:
    """Run a job's deferred writes inside its commit transaction.

    The records carry ``pending_job_id`` None, so a committed row is owned by
    the replay and is written. Entries without a ``records`` key are run as
    given, with ``require_all`` removed from their parameters.

    Args:
        txn: The commit transaction. A raised error rolls it back.
        deferred: The writes the job held back, in write order.

    Raises:
        GraphStoreWriteConflictError: A replayed write reached a row that
            another in-flight job owns, or a row that a replay requires is
            missing.
    """
    for query, parameters in deferred.entries:
        if "records" not in parameters:
            rows = await txn.execute_write(query, _without_require_all(parameters))
            _require_written(rows)
            continue
        records = parameters["records"]
        require_all = bool(parameters.get("require_all", True))
        for start in range(0, len(records), _REPLAY_BATCH_SIZE):
            batch = records[start : start + _REPLAY_BATCH_SIZE]
            rows = await txn.execute_write(query, {"records": batch})
            _require_written(rows)
            if require_all and len(rows) != len(batch):
                raise GraphStoreWriteConflictError(
                    "a deferred write lost its target row"
                )


def _without_require_all(parameters: Mapping[str, Any]) -> dict[str, Any]:
    """Return the parameters that a statement receives, without the flag."""
    return {key: value for key, value in parameters.items() if key != "require_all"}


def _require_written(rows: Sequence[Mapping[str, Any]]) -> None:
    """Raise when a replayed write reports that a row belongs to another job."""
    if any(row.get("written") is False for row in rows):
        raise GraphStoreWriteConflictError(
            "a deferred write reached a row that another job owns"
        )
