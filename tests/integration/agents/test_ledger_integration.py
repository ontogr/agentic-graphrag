"""Deep integration tests for Ledger citation lifecycle.

Tests the full citation lifecycle: cite, render, resolve, keys,
and cross-type deduplication.
"""

from uuid import uuid4

import pytest

from agrag.agents.ledger import Ledger
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.relation import Relation
from agrag.common.data_models.search_result import SearchResult


@pytest.mark.integration
@pytest.mark.enable_socket
class TestLedgerCitationLifecycle:
    """Full citation lifecycle against real data models."""

    def test_entity_keys_start_with_e(self) -> None:
        """Entity citation keys start with 'E'."""
        ledger = Ledger()
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        r = SearchResult(item=ent, score=0.9, method="entity")
        key = ledger.cite(r)
        assert key.startswith("E")
        assert key[1:].isdigit()

    def test_chunk_keys_start_with_c(self) -> None:
        """Chunk citation keys start with 'C'."""
        ledger = Ledger()
        ch = Chunk(
            document_id=uuid4(),
            index=0,
            text="Some text",
            provenance=TextProvenance(char_start=0, char_end=9),
        )
        r = SearchResult(item=ch, score=0.8, method="chunk")
        key = ledger.cite(r)
        assert key.startswith("C")
        assert key[1:].isdigit()

    def test_relation_keys_start_with_r(self) -> None:
        """Relation citation keys start with 'R'."""
        ledger = Ledger()
        rel = Relation(
            id=uuid4(),
            type="WORKS_AT",
            source_id=uuid4(),
            target_id=uuid4(),
        )
        r = SearchResult(item=rel, score=0.7, method="bfs")
        key = ledger.cite(r)
        assert key.startswith("R")

    def test_same_entity_gets_same_key_every_time(self) -> None:
        """Citing the same entity twice returns the same key."""
        ledger = Ledger()
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        r1 = SearchResult(item=ent, score=0.9, method="entity")
        r2 = SearchResult(item=ent, score=0.8, method="chunk")
        assert ledger.cite(r1) == ledger.cite(r2)

    def test_different_entities_get_different_keys(self) -> None:
        """Different entities get different citation keys."""
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
        assert ledger.cite(r1) != ledger.cite(r2)

    def test_entity_and_chunk_get_different_prefixes(self) -> None:
        """An entity and a chunk get different key prefixes."""
        ledger = Ledger()
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        ch = Chunk(
            document_id=uuid4(),
            index=0,
            text="Some text",
            provenance=TextProvenance(char_start=0, char_end=9),
        )
        k1 = ledger.cite(SearchResult(item=ent, score=0.9, method="test"))
        k2 = ledger.cite(SearchResult(item=ch, score=0.8, method="test"))
        assert k1[0] != k2[0]

    def test_cite_assigns_sequential_keys(self) -> None:
        """Keys are assigned sequentially within each type."""
        ledger = Ledger()
        e1 = SearchResult(
            item=Entity(id=uuid4(), label="Person", name="A"),
            score=0.9,
            method="test",
        )
        e2 = SearchResult(
            item=Entity(id=uuid4(), label="Person", name="B"),
            score=0.8,
            method="test",
        )
        e3 = SearchResult(
            item=Entity(id=uuid4(), label="Person", name="C"),
            score=0.7,
            method="test",
        )
        k1 = ledger.cite(e1)
        k2 = ledger.cite(e2)
        k3 = ledger.cite(e3)
        assert k1 == "E1"
        assert k2 == "E2"
        assert k3 == "E3"

    def test_render_entity_includes_name_and_label(self) -> None:
        """render() for an entity includes name and label."""
        ledger = Ledger()
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        r = SearchResult(item=ent, score=0.9, method="test")
        text = ledger.render(r)
        assert "Alice" in text
        assert "Person" in text
        assert "[E1]" in text

    def test_render_chunk_includes_text_preview(self) -> None:
        """render() for a chunk includes a text preview."""
        ledger = Ledger()
        ch = Chunk(
            document_id=uuid4(),
            index=0,
            text="Aspirin treats headaches effectively",
            provenance=TextProvenance(char_start=0, char_end=36),
        )
        r = SearchResult(item=ch, score=0.8, method="test")
        text = ledger.render(r)
        assert "Aspirin" in text
        assert "[C1]" in text

    def test_render_relation_includes_type(self) -> None:
        """render() for a relation includes the relation type."""
        ledger = Ledger()
        rel = Relation(
            id=uuid4(),
            type="WORKS_AT",
            source_id=uuid4(),
            target_id=uuid4(),
        )
        r = SearchResult(item=rel, score=0.7, method="test")
        text = ledger.render(r)
        assert "WORKS_AT" in text
        assert "[R1]" in text

    def test_resolve_returns_none_for_unknown_key(self) -> None:
        """resolve() returns None for an unknown key."""
        ledger = Ledger()
        assert ledger.resolve("X999") is None

    def test_resolve_returns_search_result(self) -> None:
        """resolve() returns the original SearchResult."""
        ledger = Ledger()
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        r = SearchResult(item=ent, score=0.9, method="test")
        key = ledger.cite(r)
        resolved = ledger.resolve(key)
        assert resolved is r

    def test_keys_returns_all_assigned_keys(self) -> None:
        """Keys returns all citation keys assigned so far."""
        ledger = Ledger()
        for i in range(5):
            ledger.cite(
                SearchResult(
                    item=Entity(id=uuid4(), label="Person", name=f"Name{i}"),
                    score=0.9,
                    method="test",
                )
            )
        assert len(ledger.keys) == 5
        assert ledger.keys == ["E1", "E2", "E3", "E4", "E5"]

    def test_mixed_types_keys_interleave(self) -> None:
        """Mixed entity and chunk citations interleave correctly."""
        ledger = Ledger()
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        ch = Chunk(
            document_id=uuid4(),
            index=0,
            text="Some text",
            provenance=TextProvenance(char_start=0, char_end=9),
        )
        k1 = ledger.cite(SearchResult(item=ent, score=0.9, method="test"))
        k2 = ledger.cite(SearchResult(item=ch, score=0.8, method="test"))
        k3 = ledger.cite(
            SearchResult(
                item=Entity(id=uuid4(), label="Person", name="Bob"),
                score=0.7,
                method="test",
            )
        )
        assert k1 == "E1"
        assert k2 == "C1"
        assert k3 == "E2"

    def test_cite_same_item_from_different_methods(self) -> None:
        """Citing the same item from different methods returns same key."""
        ledger = Ledger()
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        r1 = SearchResult(item=ent, score=0.9, method="entity")
        r2 = SearchResult(item=ent, score=0.6, method="bfs")
        assert ledger.cite(r1) == ledger.cite(r2)
        assert len(ledger.keys) == 1
