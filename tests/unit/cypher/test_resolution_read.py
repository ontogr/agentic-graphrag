"""Tests for Cypher read builders used by entity-resolution materialization."""

from agrag.cypher.resolution_read import (
    fetch_active_resolved_member_ids_query,
    fetch_match_endpoints_query,
    hydrate_resolved_entities_by_id_query,
)


class TestResolutionReadQueries:
    """Resolution read queries only ever surface synced materializations."""

    def test_hydrate_only_returns_synced_resolved_entities(self) -> None:
        """A pending or failed vector sync must not be served to retrieval."""
        query = hydrate_resolved_entities_by_id_query()

        assert "UNWIND $ids AS resolved_entity_id" in query
        assert "{id: resolved_entity_id}" in query
        assert "resolved.vector_sync_status = 'synced'" in query
        assert "RETURN resolved" in query

    def test_fetches_both_match_endpoints(self) -> None:
        """A match correction can look up both entities on either side."""
        query = fetch_match_endpoints_query()

        assert "$match_id" in query
        assert "RETURN a, b" in query

    def test_active_resolved_member_ids_require_synced_status(self) -> None:
        """A raw hit is only suppressed once its materialization is synced."""
        query = fetch_active_resolved_member_ids_query()

        assert "-[:RESOLVED_AS]->(resolved:" in query
        assert "RETURN entity_id" in query
        assert "resolved.vector_sync_status = 'synced'" in query
