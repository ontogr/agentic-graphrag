"""Cypher reads for the Cutover Job crash-recovery machine."""

from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL


def find_incomplete_jobs_query() -> str:
    """Build Cypher returning every job that still needs crash recovery.

    The ``Graph.open()`` resume hook runs this first: a pending or
    rolling-back job whose lease has lapsed rolls back. A committed or
    cleaning job rolls forward, and a pending job whose lease is still live
    is left alone because its worker may be running normally. Done and
    rolled-back jobs never match, so graphs that predate this feature or
    finished jobs whose nodes were deleted by rollback return nothing.

    ``lease_expired`` is decided in the query rather than by the caller so
    the read needs no datetime parsing at the boundary.

    Returns:
        Parameterized Cypher expecting no parameters. Returns each
        incomplete job's id, status, lease token, affected-entity snapshot,
        component seed ids and created entity ids (both set once the job
        committed), whether its commit had started, whether its document writes were
        applied, the stored commit plan, how many deferred-write steps
        it had replayed, and whether its lease has
        lapsed. The lease token is
        required to fence the subsequent recovery claim.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL}) "
        "WHERE job.status IN ['pending', 'rolling_back', 'committed', 'cleaning'] "
        "RETURN job.id AS id, job.status AS status, "
        "job.lease_token AS lease_token, "
        "job.affected_entity_ids AS affected_entity_ids, "
        "job.component_seed_ids AS component_seed_ids, "
        "job.created_entity_ids AS created_entity_ids, "
        "coalesce(job.commit_started, false) AS commit_started, "
        "coalesce(job.commit_docs_applied, false) AS commit_docs_applied, "
        "job.commit_plan AS commit_plan, "
        "coalesce(job.commit_replayed, 0) AS commit_replayed, "
        "job.lease_expires_at < timestamp() AS lease_expired"
    )
