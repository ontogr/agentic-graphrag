"""Tests for Cypher write builders used by entity-resolution materialization."""

from agrag.cypher.resolution_read import fetch_active_component_members_query
from agrag.cypher.resolution_write import (
    replace_component_materializations_query,
    set_resolved_entity_sync_status_query,
)


class TestResolutionWriteQueries:
    """Resolution write queries retain ids and synchronization diagnostics."""

    def test_collects_removed_ids_before_deleting_resolved_nodes(self) -> None:
        """Stale vector cleanup can use ids after the derived nodes are deleted."""
        query = replace_component_materializations_query()

        assert query.index("collect(DISTINCT resolved.id)") < query.index(
            "DETACH DELETE"
        )
        assert "RETURN removed_resolved_entity_ids" in query

    def test_sync_status_persists_or_clears_the_error(self) -> None:
        """A success clears prior diagnostics while a failure stores its reason."""
        query = set_resolved_entity_sync_status_query()

        assert "resolved.vector_sync_status = record.status" in query
        assert "resolved.vector_sync_error = record.error" in query

    def test_fetches_components_using_only_active_matches(self) -> None:
        """A deactivation recomputes components from active edges only."""
        query = fetch_active_component_members_query()

        assert "match.active = true" in query
        assert "seed_ids" in query
