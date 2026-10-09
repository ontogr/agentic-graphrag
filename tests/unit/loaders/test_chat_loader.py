"""Tests for ChatLoader in agrag.loaders.chat.

The loader turns a JSON Lines or JSON file of chat messages into one prose document
whose text holds one ``[role] content`` block per message, with a section for each
block.
"""

import json
from io import BytesIO

import pytest

from agrag.common.data_models.document import DocumentFamily, SourceFormat
from agrag.loaders.errors import MalformedRecordError
from agrag.loaders.chat import ChatLoader
from agrag.loaders.types import ReadOptions, SourceRef


def _load(raw: str | bytes, extension: str = ".jsonl", opts: ReadOptions | None = None):
    data = raw.encode() if isinstance(raw, str) else raw
    ref = SourceRef(uri=f"chat{extension}", extension=extension, byte_size=len(data))
    return list(ChatLoader().load(ref, BytesIO(data), opts or ReadOptions()))


def _jsonl(*messages: object) -> str:
    return "\n".join(json.dumps(m) for m in messages) + "\n"


class TestChatLoader:
    """Messages become blocks and sections."""

    def test_builds_one_document_with_a_section_per_message(self) -> None:
        """Each section holds exactly its ``[role] content`` block."""
        (doc,) = _load(
            _jsonl(
                {"role": "user", "content": "Hi there", "id": 7},
                {"role": "assistant", "content": "Hello!\nHow can I help?"},
            )
        )

        blocks = [s.units[0].text for s in doc.sections]
        assert blocks == ["[user] Hi there", "[assistant] Hello!\nHow can I help?"]
        assert doc.text == "\n\n".join(blocks)
        assert [s.heading for s in doc.sections] == ["user", "assistant"]
        assert [s.source_id for s in doc.sections] == ["7", None]
        assert {s.depth for s in doc.sections} == {1}
        assert doc.family is DocumentFamily.PROSE
        assert doc.loader_name == "chat"
        assert doc.source_format is SourceFormat.JSONL

    def test_reads_a_json_array(self) -> None:
        """A .json file holds the messages in one array."""
        (doc,) = _load(
            json.dumps([{"role": "user", "content": "a"}]), extension=".json"
        )

        assert doc.source_format is SourceFormat.JSON
        assert doc.text == "[user] a"

    def test_skips_blank_lines(self) -> None:
        """Blank lines between messages are ignored."""
        (doc,) = _load('\n{"role": "user", "content": "a"}\n\n\n')

        assert len(doc.sections) == 1

    def test_empty_file_gives_no_document(self) -> None:
        """A source with no messages makes no document."""
        assert _load("") == []
        assert _load("\n\n") == []
        assert _load("[]", extension=".json") == []

    def test_normalizes_unicode_before_parsing(self) -> None:
        """NFKC applies to the content like it does for other text loaders."""
        (doc,) = _load(_jsonl({"role": "user", "content": "ﬁx"}))

        assert doc.text == "[user] fix"

    def test_normalizes_escaped_message_fields_after_parsing(self) -> None:
        """Message fields use the configured BOM, newline and Unicode normalization."""
        (doc,) = _load(_jsonl({"role": "\ufeffuſer", "content": "\ufeffﬁrst\r\nline"}))

        assert doc.text == "[user] first\nline"
        assert doc.sections[0].heading == "user"

    def test_keeps_non_ascii_roles_and_content(self) -> None:
        """Unicode survives and spans index characters, not bytes."""
        (doc,) = _load(_jsonl({"role": "usuário", "content": "日本語"}))

        (unit,) = doc.sections[0].units
        assert doc.text[unit.char_start : unit.char_end] == "[usuário] 日本語"

    def test_keeps_a_very_large_message_whole(self) -> None:
        """A large message is one section with one unit."""
        (doc,) = _load(_jsonl({"role": "assistant", "content": "x" * 200_000}))

        assert len(doc.sections) == 1
        (unit,) = doc.sections[0].units
        assert unit.char_end - unit.char_start == 200_000 + len("[assistant] ")

    def test_store_text_false_keeps_no_text(self) -> None:
        """With store_text off, the text and the sections are empty."""
        (doc,) = _load(
            _jsonl({"role": "user", "content": "a"}), opts=ReadOptions(store_text=False)
        )

        assert doc.text == ""
        assert doc.sections == []

    @pytest.mark.parametrize(
        "raw",
        [
            "not json\n",
            _jsonl({"role": "user"}),
            _jsonl({"role": "user", "content": 5}),
            _jsonl({"content": "a"}),
            _jsonl({"role": "", "content": "a"}),
            _jsonl(["role", "content"]),
            _jsonl(
                {"role": "user", "content": "a", "id": 1},
                {"role": "user", "content": "b", "id": 1},
            ),
        ],
        ids=[
            "not-json",
            "no-content",
            "non-string-content",
            "no-role",
            "empty-role",
            "not-an-object",
            "duplicate-id",
        ],
    )
    def test_rejects_malformed_messages(self, raw: str) -> None:
        """A bad line raises the record error the other readers raise."""
        with pytest.raises(MalformedRecordError):
            _load(raw)

    def test_rejects_a_json_object_that_is_not_an_array(self) -> None:
        """A .json file must hold an array of messages."""
        with pytest.raises(MalformedRecordError):
            _load('{"role": "user", "content": "a"}', extension=".json")
