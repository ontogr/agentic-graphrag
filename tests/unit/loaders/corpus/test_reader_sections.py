"""Tests for the sections that the text, XML and chat readers put on a Document."""

import io
import json

import pytest

from agrag.common.data_models.document import Document, UnitKind
from agrag.loaders.corpus.base import ProseLoader
from agrag.loaders.corpus.readers.chat import ChatLoader
from agrag.loaders.corpus.readers.prose import TextLoader, XmlLoader
from agrag.loaders.corpus.types import ReadOptions, SourceRef


def _load(loader: ProseLoader, name: str, raw: bytes, **options: object) -> Document:
    source = SourceRef(uri=name, extension="." + name.rsplit(".", 1)[1])
    stream = io.BytesIO(raw)
    return next(iter(loader.load(source, stream, ReadOptions(**options))))


class TestTextSections:
    """A text file is one section whose units are its paragraphs."""

    def test_paragraphs_become_units_that_match_the_text(self) -> None:
        """Each unit is an exact slice of the document text."""
        raw = b"First paragraph.\nSame paragraph.\n\n\n  Second one.  \n\nThird."

        document = _load(TextLoader(), "a.txt", raw)

        (section,) = document.sections
        assert section.heading == ""
        assert section.depth == 0
        assert [u.text for u in section.units] == [
            "First paragraph.\nSame paragraph.",
            "Second one.",
            "Third.",
        ]
        for unit in section.units:
            assert document.text[unit.char_start : unit.char_end] == unit.text

    def test_blank_text_has_no_sections(self) -> None:
        """A file with no text has nothing to chunk."""
        assert _load(TextLoader(), "a.txt", b" \n\n ").sections == []

    def test_no_sections_when_text_is_not_stored(self) -> None:
        """Units point into the text, so they go when the text goes."""
        document = _load(TextLoader(), "a.txt", b"Some text.", store_text=False)

        assert document.text == ""
        assert document.sections == []


class TestXmlSections:
    """An XML file is read as the text of its elements."""

    def test_tags_are_dropped_and_each_element_is_a_line(self) -> None:
        """The text of nested elements stays in order, one line each."""
        raw = b"<doc><title>Report</title><p>One.</p><p>Two.</p></doc>"

        document = _load(XmlLoader(), "a.xml", raw)

        assert document.text == "Report\nOne.\nTwo."
        assert document.source_format.value == "xml"
        assert [u.text for u in document.sections[0].units] == ["Report\nOne.\nTwo."]

    def test_text_of_a_cdata_section_is_not_kept(self) -> None:
        """The reader documents this limit."""
        document = _load(XmlLoader(), "a.xml", b"<a><![CDATA[hidden]]><b>shown</b></a>")

        assert "hidden" not in document.text
        assert "shown" in document.text


class TestChatSections:
    """A chat file has one section for each message."""

    def test_each_message_is_a_section_with_its_role_and_id(self) -> None:
        """The section holds the message block as its unit."""
        lines = [
            {"role": "user", "content": "Hi there", "id": "m1"},
            {"role": "assistant", "content": "Hello.\n\nHow can I help?", "id": "m2"},
        ]
        raw = "\n".join(json.dumps(line) for line in lines).encode()

        document = _load(ChatLoader(), "chat.jsonl", raw)

        assert [
            (s.heading, s.depth, s.parent, s.source_id) for s in document.sections
        ] == [
            ("user", 1, None, "m1"),
            ("assistant", 1, None, "m2"),
        ]
        assert [u.text for u in document.sections[1].units] == [
            "[assistant] Hello.",
            "How can I help?",
        ]
        assert all(
            u.kind == UnitKind.PARAGRAPH for s in document.sections for u in s.units
        )

    @pytest.mark.parametrize("store_text", [True, False])
    def test_sections_follow_the_store_text_option(self, store_text: bool) -> None:
        """Without the text there are no units to point into it."""
        raw = json.dumps({"role": "user", "content": "x"}).encode()

        document = _load(ChatLoader(), "c.jsonl", raw, store_text=store_text)

        assert bool(document.sections) is store_text
