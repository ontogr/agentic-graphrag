"""Tests for the Cypher read builders in agrag.cypher.resolution_read.

Each builder is asserted against a fixed expected string, so any change
to the generated Cypher fails loudly here.
"""

from agrag.cypher.resolution_read import (
    fetch_active_component_members_query,
    fetch_active_matches_among_ids_query,
    fetch_active_resolved_member_ids_query,
    fetch_entities_with_open_evidence_query,
    fetch_entity_cluster_memberships_query,
    fetch_match_endpoints_query,
    hydrate_resolved_entities_by_id_query,
)


class TestResolutionReadQueries:
    """Resolution read builders emit fixed Cypher."""

    def test_fetch_match_endpoints_query(self) -> None:
        """A match correction looks up both entities on either side."""
        assert fetch_match_endpoints_query() == (
            "MATCH (a:_AgragNode)-"
            "[match:MATCHES {id: $match_id}]->"
            "(b:_AgragNode) RETURN a, b"
        )

    def test_fetch_active_component_members_query(self) -> None:
        """A component recomputation traverses active matches only."""
        assert fetch_active_component_members_query() == (
            "UNWIND $seed_ids AS seed_id "
            "MATCH (seed:_AgragNode {id: seed_id})"
            "-[matches:MATCHES*0..]-(member:_AgragNode) "
            "WHERE ALL(match IN matches WHERE match.active = true) "
            "AND ALL(match IN matches WHERE match._pending_job_id IS NULL "
            "OR match._pending_job_id = $job_id) "
            "AND (seed._pending_job_id IS NULL OR seed._pending_job_id = $job_id) "
            "AND (member._pending_job_id IS NULL OR member._pending_job_id = $job_id) "
            "RETURN DISTINCT seed_id, member"
        )

    def test_hydrate_resolved_entities_by_id_query(self) -> None:
        """Hydration only surfaces synced, committed materializations."""
        assert hydrate_resolved_entities_by_id_query() == (
            "UNWIND $ids AS resolved_entity_id "
            "MATCH (resolved:ResolvedEntity {id: resolved_entity_id}) "
            "WHERE resolved.vector_sync_status = 'synced' "
            "AND (resolved._pending_job_id IS NULL "
            "OR resolved._pending_job_id = $job_id) "
            "RETURN resolved"
        )

    def test_fetch_active_resolved_member_ids_query(self) -> None:
        """A raw hit is suppressed only by a synced, committed materialization."""
        assert fetch_active_resolved_member_ids_query() == (
            "UNWIND $ids AS entity_id "
            "MATCH (entity:_AgragNode {id: entity_id})"
            "-[edge:RESOLVED_AS]->(resolved:ResolvedEntity) "
            "WHERE resolved.vector_sync_status = 'synced' "
            "AND (edge._pending_job_id IS NULL "
            "OR edge._pending_job_id = $job_id) "
            "AND (resolved._pending_job_id IS NULL "
            "OR resolved._pending_job_id = $job_id) "
            "RETURN entity_id"
        )

    def test_fetch_active_matches_among_ids_query(self) -> None:
        """Reevaluation reads only active edges with both ends in the set."""
        assert fetch_active_matches_among_ids_query() == (
            "UNWIND $ids AS entity_id "
            "MATCH (a:_AgragNode {id: entity_id})"
            "-[match:MATCHES]->(b:_AgragNode) "
            "WHERE match.active = true AND b.id IN $ids "
            "AND (a._pending_job_id IS NULL OR a._pending_job_id = $job_id) "
            "AND (b._pending_job_id IS NULL OR b._pending_job_id = $job_id) "
            "AND (match._pending_job_id IS NULL "
            "OR match._pending_job_id = $job_id) "
            "RETURN match.id AS match_id, a.id AS a_id, b.id AS b_id"
        )

    def test_fetch_entities_with_open_evidence_query(self) -> None:
        """Pruning only treats open-chunk mentions as surviving evidence."""
        assert fetch_entities_with_open_evidence_query() == (
            "UNWIND $ids AS entity_id "
            "MATCH (chunk:_AgragNode:Chunk)-[mention:MENTIONED_IN]->"
            "(entity:_AgragNode {id: entity_id}) "
            "MATCH (document:_AgragNode:Document)-[part:PART_OF]->(chunk) "
            "WHERE part.invalid_at IS NULL "
            "RETURN DISTINCT entity.id AS id"
        )

    def test_fetch_entity_cluster_memberships_query(self) -> None:
        """Pruning finds each orphan's cluster before deleting its node."""
        assert fetch_entity_cluster_memberships_query() == (
            "UNWIND $ids AS entity_id "
            "MATCH (entity:_AgragNode {id: entity_id})"
            "-[membership:RESOLVED_AS]->(resolved:ResolvedEntity) "
            "WHERE (entity._pending_job_id IS NULL "
            "OR entity._pending_job_id = $job_id) "
            "AND (membership._pending_job_id IS NULL "
            "OR membership._pending_job_id = $job_id) "
            "AND (resolved._pending_job_id IS NULL "
            "OR resolved._pending_job_id = $job_id) "
            "RETURN entity_id, resolved.id AS resolved_id, "
            "resolved.member_ids AS member_ids"
        )
