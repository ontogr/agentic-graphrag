"""Tests for load_entities in agrag.graphdb.entities.

Covers loading stored entities by id from ``RETURN n`` rows: a stored node
that is not a valid entity, a failing read, and the loading span.
"""

from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.graphdb.entities import load_entities


def _row(entity_id: UUID, name: str = "Alice") -> dict[str, Any]:
    """Return one ``RETURN n`` row for a stored Person."""
    return {
        "n": {
            "id": str(entity_id),
            "name": name,
            "merge_key": f"Person:{name.casefold()}",
        }
    }


def _store(*stored: UUID) -> AsyncMock:
    """Return a graph store that holds ``stored`` and answers by requested ids."""
    store = AsyncMock()

    async def execute_read(query: str, params: dict[str, Any]) -> list[dict]:
        """Return a row for each requested id that is stored."""
        return [_row(UUID(i)) for i in params["ids"] if UUID(i) in stored]

    store.execute_read.side_effect = execute_read
    return store


class TestLoadEntities:
    """load_entities loads stored entities by id."""

    async def test_stored_node_that_is_not_an_entity_raises(self) -> None:
        """A node under a requested id with no merge key is a data error."""
        entity_id = uuid4()
        store = AsyncMock()
        store.execute_read.return_value = [{"n": {"id": str(entity_id)}}]

        with pytest.raises(ValueError, match=str(entity_id)):
            await load_entities(store, [entity_id])

    async def test_read_failure_propagates(self) -> None:
        """A failed read is raised, not turned into an empty result."""
        store = AsyncMock()
        store.execute_read.side_effect = ConnectionError("read failed")

        with pytest.raises(ConnectionError, match="read failed"):
            await load_entities(store, [uuid4()])

    async def test_exports_a_span_with_counts(self) -> None:
        """The span records how many ids were requested and loaded."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        stored = uuid4()

        await load_entities(
            _store(stored), [stored, uuid4()], tracer=provider.get_tracer("t")
        )

        (span,) = exporter.get_finished_spans()
        assert span.name == "agrag.graphdb.load_entities"
        assert span.attributes is not None
        assert span.attributes["agrag.requested_count"] == 2
        assert span.attributes["agrag.loaded_count"] == 1
