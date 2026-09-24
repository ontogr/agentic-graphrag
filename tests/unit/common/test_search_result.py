"""Tests for the SearchResult data model's identity_key property.

Covers the ``(kind, id)`` identity key shape for Entity, Chunk, and Relation
items, which fusion and the citation ledger rely on to deduplicate across
retrieval methods.
"""

from uuid import uuid4

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.relation import Relation
from agrag.common.data_models.search_result import SearchResult


def _make_entity(**overrides) -> Entity:
    defaults = {
        "id": uuid4(),
        "label": "Person",
        "name": "Alice",
    }
    defaults.update(overrides)
    return Entity(**defaults)


def _make_chunk(**overrides) -> Chunk:
    defaults = {
        "id": uuid4(),
        "document_id": uuid4(),
        "index": 0,
        "text": "Some text here.",
        "provenance": TextProvenance(char_start=0, char_end=14),
    }
    defaults.update(overrides)
    return Chunk(**defaults)


class TestSearchResult:
    """SearchResult carries an item, score, and method."""

    def test_identity_key_entity(self) -> None:
        """Entity results key by ('Entity', id)."""
        ent = _make_entity()
        result = SearchResult(item=ent, score=0.9, method="entity")
        assert result.identity_key == ("Entity", ent.id)

    def test_identity_key_chunk(self) -> None:
        """Chunk results key by ('Chunk', id)."""
        ch = _make_chunk()
        result = SearchResult(item=ch, score=0.8, method="chunk")
        assert result.identity_key == ("Chunk", ch.id)

    def test_identity_key_relation(self) -> None:
        """Relation results key by ('Relation', id)."""
        rel_id = uuid4()
        rel = Relation(
            id=rel_id,
            type="RELATED_TO",
            source_id=uuid4(),
            target_id=uuid4(),
        )
        result = SearchResult(item=rel, score=0.7, method="bfs")
        assert result.identity_key == ("Relation", rel_id)
