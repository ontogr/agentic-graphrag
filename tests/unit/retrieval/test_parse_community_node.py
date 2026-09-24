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

    def test_non_dict_mapping_node_is_parsed(self) -> None:
        """A Mapping-like node without dict identity still parses via keys()."""
        cid = uuid4()

        class KeysOnly:
            def __init__(self, data: dict) -> None:
                self._data = data

            def keys(self):
                return self._data.keys()

            def __getitem__(self, key):
                return self._data[key]

        node = KeysOnly(
            {
                "id": str(cid),
                "title": "T",
                "summary": "S",
                "rating": 5,
                "rating_explanation": "e",
            }
        )
        comm = _parse_community_node(node)
        assert comm is not None
        assert comm.title == "T"

    def test_node_without_keys_returns_none(self) -> None:
        """A node with no dict form and no keys() attribute returns None."""
        assert _parse_community_node(object()) is None

    def test_malformed_id_returns_none(self) -> None:
        """An id that fails UUID parsing returns None instead of raising."""
        node = {
            "id": "not-a-uuid",
            "title": "T",
            "summary": "S",
            "rating": 5,
            "rating_explanation": "e",
        }
        assert _parse_community_node(node) is None

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
