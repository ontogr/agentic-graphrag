"""Tests for document version lifecycle graph helpers."""

from unittest.mock import AsyncMock
from uuid import uuid4

from agrag.ingestion._document_lifecycle import (
    close_open_part_of_edges,
    find_document,
)


async def test_find_document_ignores_malformed_rows() -> None:
    """Malformed persistence data does not escape the lookup boundary."""
    store = AsyncMock()
    store.execute_read.return_value = [{"id": "not-a-uuid"}]

    assert await find_document(store, document_key="doc") is None


async def test_close_open_part_of_edges_returns_zero_without_rows() -> None:
    """A store that changes no edges reports zero closed edges."""
    store = AsyncMock()
    store.execute_write.return_value = []

    assert await close_open_part_of_edges(store, document_node_id=uuid4()) == 0
    store.execute_write.assert_awaited_once()


async def test_close_open_part_of_edges_targets_the_requested_document() -> None:
    """The close operation uses the requested document id and query."""
    store = AsyncMock()
    store.execute_write.return_value = [{"closed": 1}]
    document_node_id = uuid4()

    assert await close_open_part_of_edges(store, document_node_id=document_node_id) == 1

    query, parameters = store.execute_write.await_args.args
    assert "MATCH (d:_AgragNode:Document {id: $document_node_id})" in query
    assert "r.invalid_at IS NULL" in query
    assert parameters == {"document_node_id": str(document_node_id)}
