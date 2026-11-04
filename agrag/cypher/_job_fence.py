"""Cutover Job lock and the fence that stops a lost job's pending writes."""

from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL


def job_lock_clause(alias: str = "job") -> str:
    """Build Cypher that locks a job before its fencing guard runs."""
    return f"SET {alias}.lease_token = {alias}.lease_token + '' WITH {alias} "


def _live_pending(alias: str) -> str:
    """Return the predicate that holds while a job may still write pending rows."""
    return f"{alias}.status = 'pending' AND {alias}.lease_expires_at >= timestamp()"


def fenced_write_query(query: str) -> str:
    """Prefix a pending write with a guard on its Cutover Job.

    The guard takes the job's lock, the same lock that recovery takes before
    it claims an expired job, and lets the write run only while the job is
    pending with a live lease. A worker whose job was claimed, rolled back or
    replaced therefore writes nothing, so no row is left tagged with an id
    that no rollback will ever look for.

    Args:
        query: A write query. It must not use the ``fence_job`` variable.

    Returns:
        The guarded query. It expects ``$pending_job_id`` in addition to the
        parameters of ``query``.
    """
    return (
        f"MATCH (fence_job:{CUTOVER_JOB_LABEL} {{id: $pending_job_id}}) "
        f"{job_lock_clause('fence_job')}"
        f"WHERE {_live_pending('fence_job')} "
        f"{query}"
    )


def job_live_query() -> str:
    """Build Cypher reading whether a Cutover Job may still write pending rows.

    Returns:
        Parameterized Cypher expecting ``$pending_job_id``. Returns the job id
        while the job is pending with a live lease, no row otherwise.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $pending_job_id}}) "
        f"WHERE {_live_pending('job')} "
        "RETURN job.id AS id"
    )
