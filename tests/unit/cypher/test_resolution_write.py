"""Tests for the Cypher write builders in agrag.cypher.resolution_write.

Each builder is asserted against a fixed expected string, so any change
to the generated Cypher fails loudly here.
"""

from agrag.cypher.resolution_write import (
    clear_resolved_entity_vector_deletions_query,
    deactivate_match_query,
    delete_entities_query,
    delete_merge_aliases_for_entities_query,
    delete_resolved_entities_query,
    enqueue_resolved_entity_vector_deletions_query,
    fetch_resolved_entity_vector_deletions_query,
    replace_component_materializations_query,
    set_resolved_entity_sync_status_query,
    upsert_matches_query,
)


class TestResolutionWriteQueries:
    """Resolution write builders emit fixed Cypher."""

    def test_upsert_matches_query(self) -> None:
        """A pending match upsert preserves an existing committed edge."""
        assert upsert_matches_query() == (
            "MATCH (a:_AgragNode {id: $entity_a_id}), "
            "(b:_AgragNode {id: $entity_b_id}) "
            "MERGE (a)-[r:MATCHES {id: $match_id}]->(b) "
            "ON CREATE SET r.active = true, r.comparator = $comparator, "
            "r.score = $score, r.reasoning = $reasoning, "
            "r.decided_at = $decided_at, r._pending_job_id = $pending_job_id "
            "ON MATCH SET r.active = CASE WHEN $pending_job_id IS NULL "
            "THEN true ELSE r.active END, r.comparator = CASE WHEN "
            "$pending_job_id IS NULL THEN $comparator ELSE r.comparator END, "
            "r.score = CASE WHEN $pending_job_id IS NULL THEN $score ELSE r.score END, "
            "r.reasoning = CASE WHEN $pending_job_id IS NULL THEN $reasoning "
            "ELSE r.reasoning END, r.decided_at = CASE WHEN $pending_job_id IS NULL "
            "THEN $decided_at ELSE r.decided_at END "
            "RETURN r"
        )

    def test_deactivate_match_query(self) -> None:
        """A deactivation retains the edge and flips active to false."""
        assert deactivate_match_query() == (
            "MATCH ()-[r:MATCHES {id: $match_id}]->() SET r.active = false RETURN r"
        )

    def test_replace_component_materializations_query(self) -> None:
        """Only fully orphaned materializations are deleted."""
        assert replace_component_materializations_query() == (
            "UNWIND $member_ids AS member_id "
            "MATCH (member:_AgragNode {id: member_id})"
            "-[membership:RESOLVED_AS]->"
            "(resolved:ResolvedEntity) "
            "WITH collect(DISTINCT membership) AS memberships, "
            "collect(DISTINCT resolved) AS resolved_entities "
            "FOREACH (membership IN memberships | DELETE membership) "
            "UNWIND resolved_entities AS resolved "
            "WITH resolved, resolved.id AS resolved_id "
            "OPTIONAL MATCH (remaining:_AgragNode)-[:RESOLVED_AS]->(resolved) "
            "WITH resolved, resolved_id, count(remaining) AS remaining_members "
            "FOREACH (_ IN CASE WHEN remaining_members = 0 THEN [1] ELSE [] END | "
            "DETACH DELETE resolved) "
            "RETURN collect(CASE WHEN remaining_members = 0 THEN resolved_id END) "
            "AS removed_resolved_entity_ids"
        )

    def test_set_resolved_entity_sync_status_query(self) -> None:
        """A sync pass persists or clears the per-node vector diagnostics."""
        assert set_resolved_entity_sync_status_query() == (
            "UNWIND $records AS record "
            "MATCH (resolved:ResolvedEntity {id: record.id}) "
            "SET resolved.vector_sync_status = record.status, "
            "resolved.vector_sync_error = record.error"
        )

    def test_delete_entities_query(self) -> None:
        """Pruning collects edges first so multi-mention nodes delete once."""
        assert delete_entities_query() == (
            "UNWIND $ids AS entity_id "
            "MATCH (entity:_AgragNode {id: entity_id}) "
            "OPTIONAL MATCH (entity)-[mention:MENTIONED_IN]-() "
            "OPTIONAL MATCH (entity)-[membership:RESOLVED_AS]->"
            "(:ResolvedEntity) "
            "WITH entity, entity.id AS entity_id, "
            "collect(DISTINCT mention) AS mentions, "
            "collect(DISTINCT membership) AS memberships "
            "FOREACH (mention IN mentions | DELETE mention) "
            "FOREACH (membership IN memberships | DELETE membership) "
            "WITH entity, entity_id "
            "DETACH DELETE entity "
            "RETURN entity_id"
        )

    def test_delete_resolved_entities_query(self) -> None:
        """An emptied cluster node is deleted by its own id."""
        assert delete_resolved_entities_query() == (
            "UNWIND $ids AS resolved_id "
            "MATCH (resolved:ResolvedEntity {id: resolved_id}) "
            "DETACH DELETE resolved "
            "RETURN resolved_id"
        )

    def test_delete_merge_aliases_for_entities_query(self) -> None:
        """Pruned entities release their merge keys for clean re-ingest."""
        assert delete_merge_aliases_for_entities_query() == (
            "UNWIND $ids AS entity_id "
            "MATCH (alias:_AgragMergeAlias {entity_id: entity_id}) "
            "WITH alias, alias.entity_id AS entity_id "
            "DETACH DELETE alias "
            "RETURN entity_id"
        )

    def test_enqueue_resolved_entity_vector_deletions_query(self) -> None:
        """Failed vector deletions are persisted for a later retry."""
        assert enqueue_resolved_entity_vector_deletions_query() == (
            "UNWIND $records AS record "
            "MERGE (pending:ResolvedEntityVectorDeletion {id: record.id}) "
            "SET pending.collection = record.collection, "
            "pending.error = record.error, pending.updated_at = datetime()"
        )

    def test_clear_resolved_entity_vector_deletions_query(self) -> None:
        """Successfully retried vector deletions are removed."""
        assert clear_resolved_entity_vector_deletions_query() == (
            "UNWIND $ids AS pending_id "
            "MATCH (pending:ResolvedEntityVectorDeletion {id: pending_id}) "
            "DETACH DELETE pending"
        )

    def test_fetch_resolved_entity_vector_deletions_query(self) -> None:
        """A retry pass reads every pending vector deletion."""
        assert fetch_resolved_entity_vector_deletions_query() == (
            "MATCH (pending:ResolvedEntityVectorDeletion) "
            "RETURN pending.id AS id, pending.collection AS collection"
        )
