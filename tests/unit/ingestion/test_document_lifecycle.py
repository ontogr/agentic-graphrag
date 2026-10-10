"""Tests for document version lifecycle graph helpers."""

from unittest.mock import AsyncMock

from agrag.ingestion._document_lifecycle import (
    find_document,
)


async def test_find_document_ignores_malformed_rows() -> None:
    """Malformed persistence data does not escape the lookup boundary."""
    store = AsyncMock()
    store.execute_read.return_value = [{"id": "not-a-uuid"}]

    assert await find_document(store, document_key="doc") is None
