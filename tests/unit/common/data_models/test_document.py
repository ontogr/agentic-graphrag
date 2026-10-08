"""Tests for the Document domain model's graph-node identity and persistence.

Covers ``node_id_for``'s collision resistance, ``document_key`` defaulting to
``uri``, and ``to_node_record()`` omitting the document body.
"""

import pytest

from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    SourceFormat,
)


def _doc(*, uri: str = "u", document_key: str | None = None) -> Document:
    return Document(
        text="hello world",
        title="t",
        uri=uri,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash="h",
        loader_name="text",
        char_count=11,
        line_count=1,
        document_key=document_key,
    )


class TestNodeIdFor:
    """node_id_for maps distinct document keys to distinct ids."""

    @pytest.mark.parametrize(
        ("key_a", "key_b"),
        [
            ("doc-a", "doc-b"),
            ("path/to/file.txt", "path/to/other.txt"),
            ("", "doc-a"),
        ],
    )
    def test_distinct_keys_never_collide(self, key_a: str, key_b: str) -> None:
        """Distinct keys never return the same id."""
        assert Document.node_id_for(document_key=key_a) != Document.node_id_for(
            document_key=key_b
        )


class TestResolvedDocumentKey:
    """resolved_document_key defaults to uri unless explicitly supplied."""

    @pytest.mark.parametrize(
        ("document_key", "expected"),
        [
            (None, "u"),
            ("explicit-key", "explicit-key"),
        ],
    )
    def test_defaults_to_uri_unless_supplied(
        self, document_key: str | None, expected: str
    ) -> None:
        """document_key defaults to uri; an explicit value is left untouched."""
        doc = _doc(uri="u", document_key=document_key)
        assert doc.document_key == expected
        assert doc.resolved_document_key == expected


class TestToNodeRecord:
    """to_node_record() builds the persisted Document node's write shape."""

    def test_excludes_text(self) -> None:
        """The record never carries the full document body."""
        record = _doc().to_node_record()
        assert "text" not in record.properties
