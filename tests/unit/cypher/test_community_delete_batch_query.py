"""Tests for delete_communities_batch_query."""

from agrag.common.data_models.community import COMMUNITY_LABEL
from agrag.cypher.community_write import delete_communities_batch_query


class TestDeleteCommunitiesBatchQuery:
    """delete_communities_batch_query is batched and bounded."""

    def test_expects_limit_and_returns_deleted(self) -> None:
        """Query expects $limit and returns deleted count."""
        q = delete_communities_batch_query()
        assert "$limit" in q
        assert "LIMIT $limit" in q
        assert "RETURN count(n) AS deleted" in q
        assert COMMUNITY_LABEL in q
        assert "DETACH DELETE" in q
