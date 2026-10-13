"""Tests for document version lifecycle graph helpers."""

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agrag.common.schema_fingerprint import RunRecord
from agrag.ingestion._document_lifecycle import (
    DocumentLookup,
    UpdateDecision,
    find_document,
)


_RUN = RunRecord(
    schema_name="demo",
    schema_version="1",
    schema_fingerprint="s" * 16,
    extraction_fingerprint="e" * 16,
)

_STORED: dict[str, Any] = {
    "current_content_hash": "h",
    "has_open_chunks": True,
    "current_chunker_hash": "c",
    "current_schema_fingerprint": "s" * 16,
    "current_extraction_fingerprint": "e" * 16,
}


def _lookup(**overrides: Any) -> DocumentLookup:
    return DocumentLookup(document_node_id=uuid4(), **(_STORED | overrides))


async def test_find_document_ignores_malformed_rows() -> None:
    """Malformed persistence data does not escape the lookup boundary."""
    store = AsyncMock()
    store.execute_read.return_value = [{"id": "not-a-uuid"}]

    assert await find_document(store, document_key="doc") is None


class TestDocumentLookupDecide:
    """The stored stamps pick between no-op, in-place re-extract and new version."""

    def test_no_op_when_the_stored_version_matches_every_stamp(self) -> None:
        """Identical content, chunker, schema and extraction setup change nothing."""
        decision = _lookup().decide(content_hash="h", chunker_hash="c", run=_RUN)

        assert decision is UpdateDecision.NO_OP

    def test_in_place_when_only_the_extraction_setup_differs(self) -> None:
        """A changed extraction setup re-extracts and keeps the same chunks."""
        lookup = _lookup(current_extraction_fingerprint="x" * 16)

        decision = lookup.decide(content_hash="h", chunker_hash="c", run=_RUN)

        assert decision is UpdateDecision.IN_PLACE

    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"current_content_hash": "other"}, id="content-changed"),
            pytest.param({"current_chunker_hash": "other"}, id="chunker-changed"),
            pytest.param({"current_chunker_hash": None}, id="chunker-unrecorded"),
            pytest.param({"current_schema_fingerprint": "x" * 16}, id="schema-changed"),
            pytest.param({"current_schema_fingerprint": None}, id="schema-unrecorded"),
            pytest.param(
                {"current_extraction_fingerprint": None}, id="extraction-unrecorded"
            ),
            pytest.param({"has_open_chunks": False}, id="no-open-chunk"),
        ],
    )
    def test_new_version_when_content_chunking_schema_or_stamps_are_missing(
        self, overrides: dict[str, Any]
    ) -> None:
        """A changed or unrecorded input rewrites the document as a new version."""
        lookup = _lookup(**overrides)

        decision = lookup.decide(content_hash="h", chunker_hash="c", run=_RUN)

        assert decision is UpdateDecision.NEW_VERSION
