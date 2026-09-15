"""Tests for _parse_community_node."""

from uuid import uuid4

from agrag.retrieval.community_context import _parse_community_node


class TestParseCommunityNode:
    """_parse_community_node handles neo4j and mock dict forms."""

    def test_well_formed(self) -> None:
        """Well-formed row returns a Community."""
        cid = uuid4()
        node = {
            "properties": {
                "id": str(cid),
                "title": "T",
                "summary": "S",
                "rating": 5.0,
                "rating_explanation": "e",
                "findings": ["f"],
                "member_ids": [str(uuid4())],
                "internal_weight": 2.0,
            },
            "id": str(cid),
        }
        comm = _parse_community_node(node)
        assert comm is not None
        assert comm.title == "T"
        assert comm.embedding is None

    def test_missing_id_returns_none(self) -> None:
        """Missing id returns None."""
        assert _parse_community_node({"properties": {"title": "x"}}) is None

    def test_no_embedding_leaves_none(self) -> None:
        """No embedding property leaves embedding None."""
        cid = uuid4()
        node = {
            "id": str(cid),
            "title": "T",
            "summary": "S",
            "rating": 5,
            "rating_explanation": "e",
        }
        comm = _parse_community_node(node)
        assert comm is not None
        assert comm.embedding is None

    def test_with_embedding(self) -> None:
        """Embedding property is preserved."""
        cid = uuid4()
        node = {
            "id": str(cid),
            "title": "T",
            "summary": "S",
            "rating": 5,
            "rating_explanation": "e",
            "embedding": [0.1, 0.2],
        }
        comm = _parse_community_node(node)
        assert comm is not None
        assert comm.embedding == [0.1, 0.2]
