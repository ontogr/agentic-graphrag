"""Tests for Cutover Job write query builders.

Covers the lease, commit, tag-clearing, cleaning-transition, and rollback
queries: each builder returns the compare-and-swap guard or bulk operation
its caller relies on. Assertions are substring checks, matching this
repo's query-builder test convention.
"""

from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL
from agrag.cypher.cutover_job_write import (
    acquire_lease_query,
    claim_job_query,
    clear_pending_tag_query,
    commit_job_query,
    finish_cleaning_query,
    rollback_job_query,
    start_cleaning_query,
    steal_expired_lease_query,
)


class TestAcquireLeaseQuery:
    """acquire_lease_query shape."""

    def test_merges_on_document_key_and_returns_lease(self) -> None:
        """Acquire converges on document_key and returns token and status."""
        query = acquire_lease_query()
        assert (
            f"MERGE (job:{CUTOVER_JOB_LABEL} {{document_key: $document_key}})" in query
        )
        assert "ON CREATE SET" in query
        assert "job.status = 'pending'" in query
        assert "datetime($lease_expires_at)" in query
        assert "RETURN job.lease_token AS lease_token, job.status AS status" in query


class TestStealExpiredLeaseQuery:
    """steal_expired_lease_query shape."""

    def test_steals_expired_or_terminal_jobs_only(self) -> None:
        """Steal matches expired pending and terminal jobs, nothing else."""
        query = steal_expired_lease_query()
        assert "job.lease_token = $expected_lease_token" in query
        assert "job.lease_expires_at < datetime()" in query
        assert "job.status IN ['done', 'rolled_back']" in query
        assert "job.status = 'pending'" in query
        assert "committed" not in query
        assert "cleaning" not in query
        assert "SET job.id = $job_id" in query
        assert "RETURN job.lease_token AS lease_token" in query

    def test_adopts_the_new_runs_identity_and_snapshot(self) -> None:
        """The steal re-points the node at the new run, snapshot included.

        Every later transition fences on the new job's id, so a node left
        carrying the previous run's id would fence the whole run out.
        """
        query = steal_expired_lease_query()
        assert "job.affected_entity_ids = $affected_entity_ids" in query
        assert "job.created_at = $created_at" in query


class TestClaimJobQuery:
    """claim_job_query shape."""

    def test_claim_is_fenced_and_refreshes_expiry(self) -> None:
        """Only the observed lease holder can claim and renew a job."""
        query = claim_job_query()
        assert "job.lease_token = $expected_lease_token" in query
        assert "job.status IN ['committed', 'cleaning']" in query
        assert "job.lease_expires_at = datetime($lease_expires_at)" in query


class TestCommitJobQuery:
    """commit_job_query shape."""

    def test_commit_is_fenced_by_token_and_status(self) -> None:
        """Commit applies only to a pending job the caller still leases."""
        query = commit_job_query()
        assert "job.lease_token = $lease_token" in query
        assert "job.status = 'pending'" in query
        assert "SET job.status = 'committed'" in query
        assert "RETURN job.id AS id" in query


class TestClearPendingTagQuery:
    """clear_pending_tag_query shape."""

    def test_clears_tag_from_nodes_and_relationships(self) -> None:
        """Clear removes the tag from both nodes and edges for the job."""
        query = clear_pending_tag_query()
        assert "n._pending_job_id = $job_id" in query
        assert "REMOVE n._pending_job_id" in query
        assert "r._pending_job_id = $job_id" in query
        assert "REMOVE r._pending_job_id" in query


class TestStartCleaningQuery:
    """start_cleaning_query shape."""

    def test_start_cleaning_is_fenced_by_token_and_status(self) -> None:
        """Cleaning starts only for a committed job the caller leases."""
        query = start_cleaning_query()
        assert "job.lease_token = $lease_token" in query
        assert "job.status = 'committed'" in query
        assert "SET job.status = 'cleaning'" in query
        assert "job.lease_expires_at = datetime()" in query
        assert "RETURN job.id AS id" in query


class TestFinishCleaningQuery:
    """finish_cleaning_query shape."""

    def test_finish_cleaning_is_fenced_by_token_and_status(self) -> None:
        """Done is marked only for a cleaning job the caller leases."""
        query = finish_cleaning_query()
        assert "job.lease_token = $lease_token" in query
        assert "job.status = 'cleaning'" in query
        assert "SET job.status = 'done'" in query
        assert "RETURN job.id AS id" in query


class TestRollbackJobQuery:
    """rollback_job_query shape."""

    def test_rollback_deletes_tagged_data_then_job(self) -> None:
        """Rollback removes tagged nodes and edges before the job node."""
        query = rollback_job_query()
        assert "n._pending_job_id = $job_id" in query
        assert "DETACH DELETE n" in query
        assert "r._pending_job_id = $job_id" in query
        assert query.count("OPTIONAL MATCH ()-[r]->()") == 2
        assert f"MATCH (job:{CUTOVER_JOB_LABEL} " in query
        assert "DETACH DELETE job" in query
        assert query.index("DETACH DELETE n") < query.index("DETACH DELETE job")
