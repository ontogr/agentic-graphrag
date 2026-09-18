"""Tests for resolved-entity retrieval hydration."""

from uuid import uuid4

from agrag.retrieval.resolved_entities import parse_resolved_entity_node


class TestParseResolvedEntityNode:
    """Resolved graph nodes retain their derived result type."""

    def test_parses_graph_node_properties(self) -> None:
        """Graph node wrappers hydrate a resolved entity."""
        resolved_id, member_id = uuid4(), uuid4()

        entity = parse_resolved_entity_node(
            {
                "properties": {
                    "id": str(resolved_id),
                    "label": "Person",
                    "name": "Ada Lovelace",
                    "member_ids": [str(member_id)],
                    "created_at": "2026-01-01T00:00:00+00:00",
                }
            }
        )

        assert entity is not None
        assert entity.id == resolved_id
        assert entity.member_ids == [member_id]

    def test_rejects_malformed_nodes(self) -> None:
        """A partial graph record never becomes a fake retrieval result."""
        assert parse_resolved_entity_node({"properties": {"name": "Ada"}}) is None
