"""Tests for hydrate_entities in agrag.graphdb.entities.

Covers loading stored entities by id from ``RETURN n`` rows: batching and
deduping of the requested ids, an id with no stored entity, a stored node
that is not a valid entity, a failing read, and the hydration span.
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

from agrag.graphdb import entities as entities_module
from agrag.graphdb.entities import hydrate_entities


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


class TestHydrateEntities:
    """hydrate_entities loads stored entities by id."""

    async def test_returns_entities_by_id(self) -> None:
        """Each stored id maps to its parsed entity."""
        first, second = uuid4(), uuid4()

        result = await hydrate_entities(_store(first, second), [first, second])

        assert set(result) == {first, second}
        assert result[first].label == "Person"
        assert result[first].name == "Alice"

    async def test_omits_ids_with_no_stored_entity(self) -> None:
        """An absent id is missing from the result, not an error."""
        stored = uuid4()

        result = await hydrate_entities(_store(stored), [stored, uuid4()])

        assert set(result) == {stored}

    async def test_empty_ids_skip_the_read(self) -> None:
        """No ids returns an empty map without a query."""
        store = _store()

        assert await hydrate_entities(store, []) == {}
        store.execute_read.assert_not_called()

    async def test_reads_duplicate_ids_once(self) -> None:
        """A repeated id is requested a single time."""
        stored = uuid4()
        store = _store(stored)

        await hydrate_entities(store, [stored, stored, stored])

        assert store.execute_read.call_args.args[1]["ids"] == [str(stored)]

    async def test_reads_in_batches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ids beyond the batch size go in further reads, and all are returned."""
        monkeypatch.setattr(entities_module, "HYDRATE_BATCH_SIZE", 2)
        ids = [uuid4() for _ in range(5)]
        store = _store(*ids)

        result = await hydrate_entities(store, ids)

        assert set(result) == set(ids)
        sizes = [call.args[1]["ids"] for call in store.execute_read.call_args_list]
        assert [len(batch) for batch in sizes] == [2, 2, 1]

    async def test_stored_node_that_is_not_an_entity_raises(self) -> None:
        """A node under a requested id with no merge key is a data error."""
        entity_id = uuid4()
        store = AsyncMock()
        store.execute_read.return_value = [{"n": {"id": str(entity_id)}}]

        with pytest.raises(ValueError, match=str(entity_id)):
            await hydrate_entities(store, [entity_id])

    async def test_read_failure_propagates(self) -> None:
        """A failed read is raised, not turned into an empty result."""
        store = AsyncMock()
        store.execute_read.side_effect = ConnectionError("read failed")

        with pytest.raises(ConnectionError, match="read failed"):
            await hydrate_entities(store, [uuid4()])

    async def test_exports_a_span_with_counts(self) -> None:
        """The span records how many ids were requested and hydrated."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        stored = uuid4()

        await hydrate_entities(
            _store(stored), [stored, uuid4()], tracer=provider.get_tracer("t")
        )

        (span,) = exporter.get_finished_spans()
        assert span.name == "agrag.graphdb.hydrate_entities"
        assert span.attributes is not None
        assert span.attributes["agrag.requested_count"] == 2
        assert span.attributes["agrag.hydrated_count"] == 1
