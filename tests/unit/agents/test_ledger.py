"""Tests for Ledger in agrag.agents.ledger.

Covers markdown rendering via render() for resolved entities, query values,
and communities. Key assignment and resolve() are covered by the integration
tests in tests/integration/agents.
"""

from uuid import uuid4

import pytest

from agrag.agents.ledger import Ledger
from agrag.common.data_models.community import Community
from agrag.common.data_models.query_value import QueryValue
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.search_result import SearchResult


class TestLedger:
    """Ledger assigns and tracks stable citation keys."""

    def test_render_resolved_entity(self) -> None:
        """Resolved entities use entity citation keys and details."""
        item = ResolvedEntity(id=uuid4(), label="Person", name="Alice")
        text = Ledger().render(SearchResult(item=item, score=1.0, method="entity"))

        assert text == "[E1] Entity: Alice (Person)"

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(3, "[V1] Value: 3"), ({"count": 3}, "[V1] Value: {'count': 3}")],
    )
    def test_render_query_value(self, value: object, expected: str) -> None:
        """Query values use value citation keys and render their complete row."""
        result = SearchResult(item=QueryValue(value=value), score=1.0, method="cypher")

        assert Ledger().render(result) == expected

    def test_render_community(self) -> None:
        """render() returns markdown with title and summary for a community."""
        comm = Community(
            id=uuid4(),
            title="Aspirin research",
            summary="A community about headache treatments and dosage.",
            rating=7.0,
            rating_explanation="e",
        )
        ledger = Ledger()
        r = SearchResult(item=comm, score=0.9, method="community")
        text = ledger.render(r)
        assert text.startswith("[")
        assert "Aspirin research" in text
        assert "headache treatments" in text
