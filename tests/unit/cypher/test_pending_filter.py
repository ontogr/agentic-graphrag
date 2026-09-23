"""Tests for the pending-visibility filter clause.

Covers the shared WHERE fragment every retrieval query builder uses to
exclude nodes written by an in-flight Cutover Job. The clause is asserted
exactly because call sites interpolate it into larger queries verbatim.
"""

from agrag.cypher._pending_filter import pending_filter_clause


class TestPendingFilterClause:
    """pending_filter_clause output."""

    def test_returns_is_null_clause_for_alias(self) -> None:
        """The clause filters the given alias on the pending job key."""
        assert pending_filter_clause("n") == "n._pending_job_id IS NULL"
        assert pending_filter_clause("member") == "member._pending_job_id IS NULL"
