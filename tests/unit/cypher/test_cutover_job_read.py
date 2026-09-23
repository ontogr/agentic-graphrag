"""Tests for the Cutover Job read query builder.

Covers the incomplete-job scan the ``Graph.open()`` resume hook uses to
find jobs left behind by a crash. Assertions are substring checks,
matching this repo's query-builder test convention.
"""

from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL
from agrag.cypher.cutover_job_read import find_incomplete_jobs_query


class TestFindIncompleteJobsQuery:
    """find_incomplete_jobs_query shape."""

    def test_returns_only_non_terminal_jobs(self) -> None:
        """The scan matches pending, committed, and cleaning jobs."""
        query = find_incomplete_jobs_query()
        assert f"MATCH (job:{CUTOVER_JOB_LABEL})" in query
        assert "job.status IN ['pending', 'committed', 'cleaning']" in query
        assert "RETURN job" in query
        assert "done" not in query
        assert "rolled_back" not in query
