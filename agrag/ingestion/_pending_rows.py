"""Tag clearing and rollback of one Cutover Job's rows.

Each statement names one label or one relationship type, so the pending-tag
indexes serve it and the cost follows the size of the job, not the graph.
"""

from uuid import UUID

from agrag.common.data_models.vector_record import VectorKind
from agrag.cypher.cutover_job_write import (
    clear_pending_node_tags_query,
    clear_pending_relation_tags_query,
    delete_pending_nodes_query,
    delete_pending_relations_query,
    fold_pending_relations_query,
    lock_rolling_back_job_query,
    promote_pending_relations_query,
    rollback_job_query,
)
from agrag.cypher.entities import PENDING_TAGGED_NODE_LABELS, is_safe_identifier
from agrag.cypher.schema import list_relation_types_query
from agrag.cypher.vector_cleanup import pending_vector_ids_query
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.ingestion.vector_sync import VectorSync


async def _relation_types(txn: GraphStoreTransaction) -> list[str]:
    """Return the database's relationship types that can be placed in Cypher.

    Types that fail the identifier check are skipped instead of raising, so a
    type created outside this package cannot stop a job from clearing or
    rolling back its own rows.

    Args:
        txn: The transaction to read the type list in.

    Returns:
        The safe relationship type names, sorted.
    """
    rows = await txn.execute_read(list_relation_types_query())
    names = (str(row["relationshipType"]) for row in rows)
    return sorted(name for name in names if is_safe_identifier(name))


async def fold_job_relations(txn: GraphStoreTransaction, *, job_id: UUID) -> None:
    """Fold a job's new relations into the committed ones, in the commit.

    Runs inside the commit transaction, before the tags are cleared. A
    relation the job created under a job-scoped id joins the committed
    relation with its canonical id when there is one, and takes that id
    otherwise.

    Args:
        txn: The commit transaction.
        job_id: The committing job.
    """
    params = {"job_id": str(job_id)}
    for rel_type in await _relation_types(txn):
        await txn.execute_write(fold_pending_relations_query(rel_type), params)
        await txn.execute_write(promote_pending_relations_query(rel_type), params)


async def clear_job_tags(txn: GraphStoreTransaction, *, job_id: UUID) -> None:
    """Remove one job's pending tag from every row it tagged.

    Runs inside the commit transaction, so the tags leave in the same atomic
    step that makes the job's writes visible.

    Args:
        txn: The commit transaction.
        job_id: The job whose tags are removed. Other jobs' tags are kept.
    """
    params = {"job_id": str(job_id)}
    for label in PENDING_TAGGED_NODE_LABELS:
        await txn.execute_write(clear_pending_node_tags_query(label), params)
    for rel_type in await _relation_types(txn):
        await txn.execute_write(clear_pending_relation_tags_query(rel_type), params)


async def rollback_job_rows(
    graph_store: GraphStore,
    *,
    job_id: UUID,
    token: UUID,
    vector_sync: VectorSync | None = None,
) -> bool:
    """Delete one job's tagged rows and its job node under a lease fence.

    Everything runs in one transaction, which starts by checking that the job
    is still ``rolling_back`` under ``token``. Relationships are handled before
    nodes so that no relationship is left pointing at a deleted node. A
    pre-existing relationship the job re-activated gets its previous ``active``
    value back instead of being deleted.

    Args:
        graph_store: The store to run the rollback on.
        job_id: The job to roll back.
        token: The lease token the rollback holds.
        vector_sync: Removes vectors for rows that the graph rollback deletes.

    Returns:
        ``True`` when the rows were deleted, ``False`` when the fence did not
        match and nothing changed.
    """
    job_params = {"job_id": str(job_id)}
    fenced_params = {"job_id": str(job_id), "lease_token": str(token)}
    vector_ids: dict[VectorKind, list[UUID]] = {}

    async def rollback(txn: GraphStoreTransaction) -> bool:
        locked = await txn.execute_write(lock_rolling_back_job_query(), fenced_params)
        if not locked:
            return False
        vector_ids.clear()
        if vector_sync is not None:
            rows = await txn.execute_read(
                pending_vector_ids_query(), {"job_id": str(job_id)}
            )
            for row in rows:
                try:
                    kind = VectorKind(str(row["kind"]))
                    vector_id = UUID(str(row["id"]))
                except (KeyError, TypeError, ValueError):
                    continue
                vector_ids.setdefault(kind, []).append(vector_id)
        rel_types = await _relation_types(txn)
        for rel_type in rel_types:
            await txn.execute_write(
                delete_pending_relations_query(rel_type), job_params
            )
        for label in PENDING_TAGGED_NODE_LABELS:
            await txn.execute_write(delete_pending_nodes_query(label), job_params)
        await txn.execute_write(rollback_job_query(), fenced_params)
        return True

    rolled_back = await graph_store.run_in_transaction(rollback)
    if rolled_back and vector_sync is not None:
        for kind, ids in vector_ids.items():
            await vector_sync.delete_absent(kind, ids)
    return rolled_back
