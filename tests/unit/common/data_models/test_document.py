"""Tests for the Document domain model's graph-node identity and persistence.

Covers ``node_id_for``'s collision resistance, ``document_key`` defaulting to
``uri``, and ``to_node_record()`` omitting the document body.
"""

import pytest

from agrag.common.data_models.document import (
    Document,
    DocumentFamily,
    SourceFormat,
    TurnRef,
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


class TestTurns:
    """Document.turns holds ordered, non-overlapping spans inside the text."""

    _TEXT = "[user] hello\n\n[assistant] hi there"

    def _with_turns(
        self,
        turns: list[TurnRef],
        *,
        text: str | None = None,
        char_count: int | None = None,
    ) -> Document:
        text = self._TEXT if text is None else text
        return Document(
            text=text,
            title="t",
            uri="u",
            source_format=SourceFormat.JSONL,
            family=DocumentFamily.PROSE,
            content_hash="h",
            loader_name="chat",
            char_count=len(text) if char_count is None else char_count,
            turns=turns,
        )

    def test_accepts_ordered_turns(self) -> None:
        """Turns that follow the text in order are kept as given."""
        turns = [
            TurnRef(role="user", char_start=0, char_end=12),
            TurnRef(role="assistant", turn_id="a1", char_start=14, char_end=34),
        ]

        assert self._with_turns(turns).turns == turns

    def test_defaults_to_no_turns(self) -> None:
        """A document without chat structure has no turns."""
        assert self._with_turns([]).turns == []

    def test_rejects_turns_when_text_is_not_stored(self) -> None:
        """Turn spans require the document text that they index."""
        turns = [TurnRef(role="user", char_start=0, char_end=12)]

        with pytest.raises(ValueError, match="text"):
            self._with_turns(turns, text="", char_count=len(self._TEXT))

    @pytest.mark.parametrize(
        ("spans", "message"),
        [
            ([(14, 34), (0, 12)], "order"),
            ([(0, 20), (10, 34)], "overlap"),
            ([(0, 99)], "text"),
            ([(-1, 5)], "text"),
            ([(5, 5)], "text"),
        ],
        ids=["out-of-order", "overlap", "past-end", "negative", "empty"],
    )
    def test_rejects_bad_spans(
        self, spans: list[tuple[int, int]], message: str
    ) -> None:
        """Out-of-order, overlapping or out-of-range spans raise."""
        turns = [TurnRef(role="user", char_start=a, char_end=b) for a, b in spans]

        with pytest.raises(ValueError, match=message):
            self._with_turns(turns)

    def test_rejects_empty_role(self) -> None:
        """A turn must name its speaker."""
        with pytest.raises(ValueError, match="role"):
            TurnRef(role="", char_start=0, char_end=3)
