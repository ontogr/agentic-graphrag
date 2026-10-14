"""Tests for document version lifecycle graph helpers."""

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agrag.common.data_models.update_decision import UpdateDecision
from agrag.common.schema_fingerprint import RunRecord
from agrag.ingestion._document_lifecycle import (
    DocumentLookup,
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
    "current_version_id": "v",
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
        decision = _lookup().decide(
            content_hash="h", version_id="v", chunker_hash="c", run=_RUN
        )

        assert decision is UpdateDecision.NO_OP

    @pytest.mark.parametrize(
        "stored_extraction_fingerprint",
        [
            pytest.param("x" * 16, id="extraction-changed"),
            pytest.param(None, id="extraction-unrecorded"),
        ],
    )
    def test_in_place_when_the_extraction_stamp_differs_or_is_missing(
        self, stored_extraction_fingerprint: str | None
    ) -> None:
        """An extraction stamp that is not current re-extracts the same chunks."""
        lookup = _lookup(current_extraction_fingerprint=stored_extraction_fingerprint)

        decision = lookup.decide(
            content_hash="h", version_id="v", chunker_hash="c", run=_RUN
        )

        assert decision is UpdateDecision.IN_PLACE

    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"current_content_hash": "other"}, id="content-changed"),
            pytest.param({"current_version_id": "other"}, id="structure-changed"),
            pytest.param({"current_version_id": None}, id="version-unrecorded"),
            pytest.param({"current_chunker_hash": "other"}, id="chunker-changed"),
            pytest.param({"current_chunker_hash": None}, id="chunker-unrecorded"),
            pytest.param({"current_schema_fingerprint": "x" * 16}, id="schema-changed"),
            pytest.param({"current_schema_fingerprint": None}, id="schema-unrecorded"),
            pytest.param({"has_open_chunks": False}, id="no-open-chunk"),
        ],
    )
    def test_new_version_when_content_chunking_or_schema_differs(
        self, overrides: dict[str, Any]
    ) -> None:
        """A changed or unrecorded input rewrites the document as a new version."""
        lookup = _lookup(**overrides)

        decision = lookup.decide(
            content_hash="h", version_id="v", chunker_hash="c", run=_RUN
        )

        assert decision is UpdateDecision.NEW_VERSION
