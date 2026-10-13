"""Cypher writes for the Cutover Job crash-recovery machine."""

from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL
from agrag.common.data_models.graph_record import PENDING_JOB_ID_PROPERTY
from agrag.cypher.entities import validate_identifier, validate_identifier_syntax


def _job_lock_clause() -> str:
    """Build Cypher that locks a job before its fencing guard runs."""
    return "SET job.lease_token = job.lease_token + '' WITH job "


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
        $lease_token, $lease_expires_at (ISO-8601 string, stored as a
        native datetime for expiry comparison), $affected_entity_ids
        (list of string ids, snapshotted before any pending write), and
        $created_at. Returns the job id, lease token, status, and whether
        its lease has expired.
    """
    return (
        f"MERGE (job:{CUTOVER_JOB_LABEL} {{document_key: $document_key}}) "
        "ON CREATE SET job.id = $job_id, job.status = 'pending', "
        "job.verb = $verb, job.lease_token = $lease_token, "
        "job.lease_expires_at = datetime($lease_expires_at), "
        "job.affected_entity_ids = $affected_entity_ids, "
        "job.created_at = $created_at "
        "RETURN job.id AS id, job.lease_token AS lease_token, job.status AS status, "
        "job.lease_expires_at < datetime() AS lease_expired"
    )


def steal_terminal_job_query() -> str:
    """Build Cypher taking over a job already in a terminal state.

    Matches a job for ``$document_key`` only when it is ``done`` or
    ``rolled_back``, meaning a previous run left the node behind, and
    resets it to pending under the caller's identity and token. A pending
    or rolling_back job with an expired lease never matches: its worker
    died while its tagged rows and staged vectors still exist, so the
    caller rolls it back first (see ``_acquire_lease``). Committed and
    cleaning jobs never match either: they are mid-roll-forward under the
    resume hook, and stealing one would fork the cleanup phase.

    The steal adopts ``$job_id`` as well as ``$lease_token``: every later
    step of this job's run — commit, clean, done — fences on the new
    job's id, so a node still carrying the previous run's id would fence
    the whole run out at its first transition.

    Returns:
        Parameterized Cypher expecting $job_id, $document_key, $verb,
        $expected_lease_token, $lease_token, $affected_entity_ids (the new
        run's snapshot, empty until the caller needs it), $created_at, and
        $lease_expires_at
        (ISO-8601 string). Returns the node's lease_token when the steal
        succeeded, no row otherwise.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{document_key: $document_key}}) "
        f"{_job_lock_clause()}"
        "WHERE job.lease_token = $expected_lease_token "
        "AND job.status IN ['done', 'rolled_back'] "
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
        f"{_job_lock_clause()}"
        "WHERE job.status IN ['committed', 'cleaning'] "
        "AND job.lease_token = $expected_lease_token "
        "AND job.lease_expires_at < datetime() "
        "SET job.status = 'cleaning', job.lease_token = $lease_token, "
        "job.lease_expires_at = datetime($lease_expires_at) "
        "RETURN job.status AS status"
    )


def claim_pending_job_query() -> str:
    """Claim an expired pending or rolling-back job before rollback.

    The recovery scan can become stale before it starts deleting pending
    graph or vector writes. This compare-and-swap claim rechecks the
    pending or rolling-back status, original token, and expiry while holding
    the job lock,
    then gives recovery a fresh lease for the destructive phase.

    Returns:
        Parameterized Cypher expecting $job_id, $expected_lease_token,
        $lease_token, and $lease_expires_at. Returns the job id when the
        claim applied, no row when another worker renewed or changed it.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        f"{_job_lock_clause()}"
        "WHERE job.status IN ['pending', 'rolling_back'] "
        "AND job.lease_token = $expected_lease_token "
        "AND job.lease_expires_at < datetime() "
        "SET job.status = 'rolling_back', job.lease_token = $lease_token, "
        "job.lease_expires_at = datetime($lease_expires_at) "
        "RETURN job.id AS id"
    )


def begin_rollback_query() -> str:
    """Move a pending job into rollback under the current lease token."""
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        f"{_job_lock_clause()}"
        "WHERE job.lease_token = $lease_token AND job.status = 'pending' "
        "SET job.status = 'rolling_back' "
        "RETURN job.id AS id"
    )


def job_status_query() -> str:
    """Read a job's status, lease token, and recorded closed-edge count."""
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        "RETURN job.status AS status, job.lease_token AS lease_token, "
        "job.parts_closed AS parts_closed"
    )


def record_parts_closed_query() -> str:
    """Record the number of document edges closed by a job commit."""
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        "SET job.parts_closed = $parts_closed"
    )


def commit_job_query() -> str:
    """Build Cypher flipping a job from pending to committed, fenced by lease.

    Follows ``set_embedding_query``'s compare-and-swap shape: the write
    applies only while the ``WHERE`` guard (caller's fencing token still
    current, job still pending, and lease still live) holds, so a worker
    that lost its lease cannot complete a stale commit even if it is still
    alive and slow.

    The flip also records ``$component_seed_ids``, so the post-commit
    cleanup can rebuild the job's components after a crash.

    Returns:
        Parameterized Cypher expecting $job_id, $lease_token, and
        $component_seed_ids (list of string ids, one per rebuilt
        component). Returns the job id when the flip applied, no row on
        fencing failure.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        f"{_job_lock_clause()}"
        "WHERE job.lease_token = $lease_token "
        "AND job.lease_expires_at >= datetime() "
        "AND job.status = 'pending' "
        "SET job.status = 'committed', "
        "job.component_seed_ids = $component_seed_ids "
        "RETURN job.id AS id"
    )


def clear_pending_node_tags_query(label: str) -> str:
    """Build Cypher clearing the pending tag off a job's nodes with ``label``.

    Runs once per label in ``PENDING_TAGGED_NODE_LABELS``, inside the same
    transaction as ``commit_job_query``: the commit flip and the tag removal
    land atomically, so a crash between them is impossible. The label in the
    ``MATCH`` lets the per-label pending index serve the lookup. External
    vector-store payloads carry the mirrored ``_pending`` boolean and are
    cleared through the VectorStore API by the caller, not here; the native
    vector-index path reads node properties, so it sees this same removal.

    Args:
        label: The node label. Must be a well-formed identifier; the
            candidate label is accepted.

    Returns:
        Parameterized Cypher expecting $job_id. Returns ``cleared``, the
        number of nodes whose tag was removed.

    Raises:
        ValueError: ``label`` is not a well-formed identifier.
    """
    safe_label = validate_identifier_syntax(label)
    return (
        f"MATCH (n:{safe_label}) WHERE n.{PENDING_JOB_ID_PROPERTY} = $job_id "
        f"REMOVE n.{PENDING_JOB_ID_PROPERTY} "
        "RETURN count(n) AS cleared"
    )


def clear_pending_relation_tags_query(rel_type: str) -> str:
    """Build Cypher clearing the pending bookkeeping off a job's relationships.

    Removes the job tag together with the creation flag and the previous
    ``active`` value, since a relationship that survives commit no longer
    needs any of them. Runs in the same commit transaction as
    ``clear_pending_node_tags_query``.

    Args:
        rel_type: The relationship type. Must be a safe identifier.

    Returns:
        Parameterized Cypher expecting $job_id. Returns ``cleared``, the
        number of relationships whose tag was removed.

    Raises:
        ValueError: ``rel_type`` is not a safe identifier.
    """
    safe_type = validate_identifier(rel_type)
    return (
        f"MATCH ()-[r:{safe_type}]->() WHERE r.{PENDING_JOB_ID_PROPERTY} = $job_id "
        f"REMOVE r.{PENDING_JOB_ID_PROPERTY}, r._pending_created, "
        "r._pending_previous_active "
        "RETURN count(r) AS cleared"
    )


def delete_pending_relations_query(rel_type: str) -> str:
    """Build Cypher deleting the relationships a job created.

    Only relationships the job created are deleted; a relationship it merely
    updated is left for ``restore_pending_relations_query`` to revert.

    Args:
        rel_type: The relationship type. Must be a safe identifier.

    Returns:
        Parameterized Cypher expecting $job_id. Returns ``deleted``, the
        number of relationships removed.

    Raises:
        ValueError: ``rel_type`` is not a safe identifier.
    """
    safe_type = validate_identifier(rel_type)
    return (
        f"MATCH ()-[r:{safe_type}]->() "
        f"WHERE r.{PENDING_JOB_ID_PROPERTY} = $job_id AND r._pending_created = true "
        "DELETE r RETURN count(r) AS deleted"
    )


def restore_pending_relations_query(rel_type: str) -> str:
    """Build Cypher reverting a job's updates to pre-existing relationships.

    Sets ``active`` back to the value saved before the job touched the
    relationship, then removes the pending bookkeeping. A relationship with
    no saved value keeps its current ``active``.

    Args:
        rel_type: The relationship type. Must be a safe identifier.

    Returns:
        Parameterized Cypher expecting $job_id. Returns no rows; the caller
        needs only the side effect.

    Raises:
        ValueError: ``rel_type`` is not a safe identifier.
    """
    safe_type = validate_identifier(rel_type)
    return (
        f"MATCH ()-[r:{safe_type}]->() WHERE r.{PENDING_JOB_ID_PROPERTY} = $job_id "
        "SET r.active = coalesce(r._pending_previous_active, r.active) "
        f"REMOVE r.{PENDING_JOB_ID_PROPERTY}, r._pending_created, "
        "r._pending_previous_active"
    )


def delete_pending_nodes_query(label: str) -> str:
    """Build Cypher deleting the nodes a job created with ``label``.

    ``DETACH DELETE`` also removes every relationship on the node, tagged or
    not.

    Args:
        label: The node label. Must be a well-formed identifier; the
            candidate label is accepted.

    Returns:
        Parameterized Cypher expecting $job_id. Returns ``deleted``, the
        number of nodes removed.

    Raises:
        ValueError: ``label`` is not a well-formed identifier.
    """
    safe_label = validate_identifier_syntax(label)
    return (
        f"MATCH (n:{safe_label}) WHERE n.{PENDING_JOB_ID_PROPERTY} = $job_id "
        "DETACH DELETE n RETURN count(n) AS deleted"
    )


def start_cleaning_query() -> str:
    """Build Cypher moving a committed job into cleaning, fenced by lease.

    Same compare-and-swap shape as ``commit_job_query``: only the current
    lease holder that committed the job may start its cleanup. The lease
    expiry is left as the holder last renewed it: cleanup is live work, so
    resetting it to now would make a running job look abandoned and let a
    concurrent resume take it over.

    Returns:
        Parameterized Cypher expecting $job_id and $lease_token. Returns
        the job id when the transition applied, no row otherwise.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        f"{_job_lock_clause()}"
        "WHERE job.lease_token = $lease_token "
        "AND job.lease_expires_at >= datetime() "
        "AND job.status = 'committed' "
        "SET job.status = 'cleaning' "
        "RETURN job.id AS id"
    )


def renew_lease_query() -> str:
    """Build Cypher extending a live job's lease, fenced by its token.

    Applies in every non-terminal phase (pending, rolling_back, committed,
    cleaning) only
    while the lease remains live and the caller's fencing token is still
    current, so a worker that lost its lease cannot revive it.

    Returns:
        Parameterized Cypher expecting $job_id, $lease_token, and
        $lease_expires_at (ISO-8601 string). Returns the job id when the
        lease was extended, no row on fencing failure.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        f"{_job_lock_clause()}"
        "WHERE job.lease_token = $lease_token "
        "AND job.lease_expires_at >= datetime() "
        "AND job.status IN ['pending', 'rolling_back', 'committed', 'cleaning'] "
        "SET job.lease_expires_at = datetime($lease_expires_at) "
        "RETURN job.id AS id"
    )


def finish_cleaning_query() -> str:
    """Build Cypher marking a job done after its cleanup phase completes.

    Same compare-and-swap shape as ``commit_job_query``: only the current
    lease holder that started cleaning may finish it.

    Returns:
        Parameterized Cypher expecting $job_id and $lease_token. Returns
        the job id when the transition applied, no row otherwise.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        f"{_job_lock_clause()}"
        "WHERE job.lease_token = $lease_token "
        "AND job.lease_expires_at >= datetime() "
        "AND job.status = 'cleaning' "
        "SET job.status = 'done' "
        "RETURN job.id AS id"
    )


def lock_rolling_back_job_query() -> str:
    """Lock a rolling-back job's node and confirm its fencing token.

    Takes the job's write lock before reading the token, so the rollback
    transaction waits out any concurrent lease change instead of racing it.
    Run it first in the rollback transaction, before the per-label deletes.

    Returns:
        Parameterized Cypher expecting $job_id and $lease_token. Returns the
        job id when the job is still ``rolling_back`` under that token, no
        row otherwise.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        f"{_job_lock_clause()}"
        "WHERE job.lease_token = $lease_token AND job.status = 'rolling_back' "
        "RETURN job.id AS id"
    )


def rollback_job_query() -> str:
    """Delete a rolling-back job's node under its lease token.

    Removes only the job node. The job's tagged nodes and relationships are
    removed by the per-label and per-type statements in the same
    transaction, so this runs last and the job node stays as the fence
    until then.

    Returns:
        Parameterized Cypher expecting $job_id and $lease_token. Returns one
        row with ``id`` when the fence holds, no row otherwise.
    """
    return (
        f"MATCH (job:{CUTOVER_JOB_LABEL} {{id: $job_id}}) "
        "WHERE job.lease_token = $lease_token AND job.status = 'rolling_back' "
        "DETACH DELETE job "
        "RETURN $job_id AS id"
    )
