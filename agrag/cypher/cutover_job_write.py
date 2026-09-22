"""Cypher writes for the Cutover Job crash-recovery machine."""

from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL


def acquire_lease_query() -> str:
    """Build Cypher tentatively creating a job node and returning its lease.

    Follows ``upsert_merge_alias_query``'s tentative-create shape: ``MERGE``
    on ``document_key`` (backed by the ``CutoverJob.document_key``
    uniqueness constraint) creates the node for the first claimant and
    matches it for everyone else, so concurrent acquirers converge instead
    of duplicating. The caller compares the returned ``lease_token``
    against its own: equality means it won the lease (created the node),
    anything else means a live job already holds it.

    Returns:
        Parameterized Cypher expecting $job_id, $document_key, $verb,
        $expected_lease_token,
        $lease_token, $lease_expires_at (ISO-8601 string, stored as a
        native datetime for expiry comparison), $affected_entity_ids
        (list of string ids, snapshotted before any pending write), and
        $created_at. Returns the node's lease_token and status.
    """
    return (
        f"MERGE (job:{CUTOVER_JOB_LABEL} {{document_key: $document_key}}) "
        "ON CREATE SET job.id = $job_id, job.status = 'pending', "
        "job.verb = $verb, job.lease_token = $lease_token, "
        "job.lease_expires_at = datetime($lease_expires_at), "
        "job.affected_entity_ids = $affected_entity_ids, "
        "job.created_at = $created_at "
        "RETURN job.lease_token AS lease_token, job.status AS status"
    )


def steal_expired_lease_query() -> str:
    """Build Cypher taking over a job whose lease lapsed or went terminal.

    Matches a job for ``$document_key`` that is either still pending with
    an expired lease (its worker died without committing) or already in a
    terminal state (a previous run finished and left the node behind), and
    resets it to pending under the caller's identity and token. Committed
    and cleaning jobs never match: they are mid-roll-forward under the
    resume hook, and stealing one would fork the cleanup phase.

    The steal adopts ``$job_id`` as well as ``$lease_token``: every later
    step of this job's run — commit, clean, done — fences on the new
    job's id, so a node still carrying the previous run's id would fence
    the whole run out at its first transition.

    Returns:
        Parameterized Cypher expecting $job_id, $document_key, $verb,
        $lease_token, $affected_entity_ids (the new run's snapshot, empty
        until the caller needs it), $created_at, and $lease_expires_at
        (ISO-8601 string). Returns the node's lease_token when the steal
        succeeded, no row otherwise.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{document_key: $document_key}}) "
        "WHERE job.lease_token = $expected_lease_token AND ("
        "job.status IN ['done', 'rolled_back'] "
        "OR (job.status = 'pending' AND job.lease_expires_at < datetime())) "
        "SET job.id = $job_id, job.status = 'pending', job.verb = $verb, "
        "job.lease_token = $lease_token, "
        "job.lease_expires_at = datetime($lease_expires_at), "
        "job.affected_entity_ids = $affected_entity_ids, "
        "job.created_at = $created_at "
        "RETURN job.lease_token AS lease_token"
    )


def claim_job_query() -> str:
    """Build Cypher taking over an interrupted job for resume-on-open.

    The ``Graph.open()`` resume hook runs this after
    ``find_incomplete_jobs_query``: it flips one incomplete job to
    ``cleaning`` under a fresh fencing token if the job is committed
    (roll forward) or cleaning (a previous resume died mid-cleanup), and
    is refused for a pending job, which the caller rolls back instead —
    a pending job's worker may still be alive, so taking over its writes
    would fork the pipeline. The flip is fenced against the token read
    in the same query, so two simultaneous opens converge: exactly one
    claimant gets back its own token, and the loser sees no row and
    skips the job as claimed.

    Returns:
        Parameterized Cypher expecting $job_id, $expected_lease_token,
        $lease_token (the claimant's fresh token), and $lease_expires_at.
        Returns the job's new status when the
        claim applied, no row when the job is pending or was claimed by
        another open first.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        "WHERE job.status IN ['committed', 'cleaning'] "
        "AND job.lease_token = $expected_lease_token "
        "SET job.status = 'cleaning', job.lease_token = $lease_token, "
        "job.lease_expires_at = datetime($lease_expires_at) "
        "RETURN job.status AS status"
    )


def commit_job_query() -> str:
    """Build Cypher flipping a job from pending to committed, fenced by lease.

    Follows ``set_embedding_query``'s compare-and-swap shape: the write
    applies only while the ``WHERE`` guard (caller's fencing token still
    current, job still pending) holds, so a worker that lost its lease
    cannot complete a stale commit even if it is still alive and slow.

    Returns:
        Parameterized Cypher expecting $job_id and $lease_token. Returns
        the job id when the flip applied, no row on fencing failure.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        "WHERE job.lease_token = $lease_token AND job.status = 'pending' "
        "SET job.status = 'committed' "
        "RETURN job.id AS id"
    )


def clear_pending_tag_query() -> str:
    """Build Cypher clearing the pending tag off everything a job created.

    Runs inside the same transaction as ``commit_job_query``: the commit
    flip and the tag removal land atomically, so a crash between them is
    impossible. External vector-store payloads carry the mirrored
    ``_pending`` boolean and are cleared through the VectorStore API by
    the caller, not here; the native vector-index path reads node
    properties, so it sees this same removal.

    Returns:
        Parameterized Cypher expecting $job_id. Returns the count of
        nodes and relationships cleared.
    """
    return (
        "MATCH (n) WHERE n._pending_job_id = $job_id "
        "REMOVE n._pending_job_id "
        "WITH count(n) AS cleared_nodes "
        "OPTIONAL MATCH ()-[r]->() WHERE r._pending_job_id = $job_id "
        "REMOVE r._pending_job_id "
        "RETURN cleared_nodes, count(r) AS cleared_relationships"
    )


def start_cleaning_query() -> str:
    """Build Cypher moving a committed job into cleaning, fenced by lease.

    Same compare-and-swap shape as ``commit_job_query``: only the lease
    holder that committed the job may start its cleanup.

    Returns:
        Parameterized Cypher expecting $job_id and $lease_token. Returns
        the job id when the transition applied, no row otherwise.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        "WHERE job.lease_token = $lease_token AND job.status = 'committed' "
        "SET job.status = 'cleaning' "
        "RETURN job.id AS id"
    )


def finish_cleaning_query() -> str:
    """Build Cypher marking a job done after its cleanup phase completes.

    Same compare-and-swap shape as ``commit_job_query``: only the lease
    holder that started cleaning may finish it.

    Returns:
        Parameterized Cypher expecting $job_id and $lease_token. Returns
        the job id when the transition applied, no row otherwise.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        "WHERE job.lease_token = $lease_token AND job.status = 'cleaning' "
        "SET job.status = 'done' "
        "RETURN job.id AS id"
    )


def rollback_job_query() -> str:
    """Build Cypher deleting everything a job created, then the job itself.

    Only rows this job created carry its tag, so rollback is pure
    deletion of the job's own additions: every tagged node (detaching its
    edges) and every tagged edge between committed endpoints goes first,
    then the job node. Nothing a caller committed earlier is reachable
    from here, because a row that already existed when the job wrote over
    it was never tagged. Reaching this terminal state is observed as the
    job node's absence, which also frees ``document_key`` for the next job
    without a reuse path.

    Returns:
        Parameterized Cypher expecting $job_id. Returns the count of
        deleted nodes and relationships.
    """
    return (
        "MATCH (n) WHERE n._pending_job_id = $job_id "
        "DETACH DELETE n "
        "WITH count(n) AS deleted_nodes "
        "OPTIONAL MATCH ()-[r]->() WHERE r._pending_job_id = $job_id "
        "DELETE r "
        "WITH deleted_nodes, count(r) AS deleted_relationships "
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        "DETACH DELETE job "
        "RETURN deleted_nodes, deleted_relationships"
    )
