"""Cypher reads for the Cutover Job crash-recovery machine."""

from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL


def find_incomplete_jobs_query() -> str:
    """Build Cypher returning every job that still needs crash recovery.

    The ``Graph.open()`` resume hook runs this first: a pending job whose
    lease has lapsed rolls back, a committed or cleaning job rolls
    forward, and a pending job whose lease is still live is left alone
    because its worker may be running normally. Done and rolled-back jobs
    never match, so graphs that predate this feature — or finished jobs
    whose nodes were deleted by rollback — simply return nothing.

    ``lease_expired`` is decided in the query rather than by the caller so
    the read needs no datetime parsing at the boundary.

    Returns:
        Parameterized Cypher expecting no parameters. Returns each
        incomplete job's id, status, affected-entity snapshot, and whether
        its lease has lapsed.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL}) "
        "WHERE job.status IN ['pending', 'committed', 'cleaning'] "
        "RETURN job.id AS id, job.status AS status, "
        "job.affected_entity_ids AS affected_entity_ids, "
        "job.lease_expires_at < datetime() AS lease_expired"
    )
