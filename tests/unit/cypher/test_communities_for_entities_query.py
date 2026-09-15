"""Tests for communities_for_entities_query."""

from agrag.common.data_models.community import COMMUNITY_LABEL, MEMBER_OF_RELATION
from agrag.cypher.community import communities_for_entities_query
from agrag.cypher.entities import NODE_IDENTITY_LABEL


class TestCommunitiesForEntitiesQuery:
    """communities_for_entities_query matches via identity label."""

    def test_matches_via_identity_label(self) -> None:
        """Query filters on NODE_IDENTITY_LABEL, not an unrestricted pattern."""
        q = communities_for_entities_query()
        assert NODE_IDENTITY_LABEL in q
        assert COMMUNITY_LABEL in q
        assert MEMBER_OF_RELATION in q
        assert "$entity_ids" in q
        assert "overlap" in q

    def test_returns_overlap_ordered(self) -> None:
        """Query orders by overlap DESC."""
        q = communities_for_entities_query()
        assert "ORDER BY overlap DESC" in q
