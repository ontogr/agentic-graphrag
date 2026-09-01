"""Tests for Ledger citation tracking."""

from uuid import uuid4

from agrag.agents.ledger import Ledger
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult


class TestLedger:
    """Ledger assigns and tracks stable citation keys."""

    def test_same_entity_same_key(self) -> None:
        """Two SearchResults for the same entity get the same key."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        ledger = Ledger()
        r1 = SearchResult(item=ent, score=0.9, method="entity")
        r2 = SearchResult(item=ent, score=0.8, method="chunk")
        k1 = ledger.cite(r1)
        k2 = ledger.cite(r2)
        assert k1 == k2

    def test_different_entity_different_key(self) -> None:
        """Two SearchResults for different entities get different keys."""
        ledger = Ledger()
        r1 = SearchResult(
            item=Entity(id=uuid4(), label="Person", name="Alice"),
            score=0.9,
            method="entity",
        )
        r2 = SearchResult(
            item=Entity(id=uuid4(), label="Person", name="Bob"),
            score=0.8,
            method="entity",
        )
        k1 = ledger.cite(r1)
        k2 = ledger.cite(r2)
        assert k1 != k2

    def test_entity_key_prefix(self) -> None:
        """Entity keys start with 'E'."""
        ledger = Ledger()
        r = SearchResult(
            item=Entity(id=uuid4(), label="Person", name="Alice"),
            score=1.0,
            method="test",
        )
        key = ledger.cite(r)
        assert key.startswith("E")

    def test_resolve_returns_search_result(self) -> None:
        """resolve() returns the SearchResult behind a key."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        ledger = Ledger()
        r = SearchResult(item=ent, score=0.9, method="test")
        key = ledger.cite(r)
        resolved = ledger.resolve(key)
        assert resolved is not None
        assert resolved.item.id == ent.id

    def test_resolve_unknown_key_returns_none(self) -> None:
        """resolve() returns None for unknown keys."""
        ledger = Ledger()
        assert ledger.resolve("X999") is None

    def test_render_entity(self) -> None:
        """render() returns markdown with citation key for entity."""
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        ledger = Ledger()
        r = SearchResult(item=ent, score=0.9, method="test")
        text = ledger.render(r)
        assert text.startswith("[")
        assert "Alice" in text
        assert "Person" in text

    def test_keys_property(self) -> None:
        """Keys returns all citation keys assigned."""
        ledger = Ledger()
        r1 = SearchResult(
            item=Entity(id=uuid4(), label="Person", name="A"),
            score=1.0,
            method="test",
        )
        r2 = SearchResult(
            item=Entity(id=uuid4(), label="Person", name="B"),
            score=1.0,
            method="test",
        )
        ledger.cite(r1)
        ledger.cite(r2)
        assert len(ledger.keys) == 2
