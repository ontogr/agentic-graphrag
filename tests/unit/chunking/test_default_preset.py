"""Golden test: DEFAULT_CHUNKING gives the chunks the pre-contract chunker gave.

``tests/fixtures/chunking/golden_default.json`` holds documents and the chunks that
the earlier hardcoded character chunker made for them: ids, offsets, text, line
numbers, headings. The default preset must reproduce every field except the two
chunker fields, which are new.
"""

import json
from pathlib import Path

import pytest

from agrag.chunking import DEFAULT_CHUNKING
from agrag.common.data_models.document import Document, HeadingRef


_GOLDEN = json.loads(
    (
        Path(__file__).parents[2] / "fixtures" / "chunking" / "golden_default.json"
    ).read_text(encoding="utf-8")
)


def _document(fields: dict) -> Document:
    outline = [HeadingRef(**heading) for heading in fields["heading_outline"]]
    return Document(**{**fields, "heading_outline": outline})


class TestDefaultPreset:
    """DEFAULT_CHUNKING reproduces the frozen chunks byte for byte."""

    @pytest.mark.parametrize(
        "case", _GOLDEN, ids=[case["document"]["title"] for case in _GOLDEN]
    )
    def test_reproduces_frozen_chunks(self, case: dict) -> None:
        """Each field of each chunk equals the golden value."""
        document = _document(case["document"])

        _, chunker = DEFAULT_CHUNKING.select(document)
        chunks = chunker.chunk(document)

        actual = [
            {
                "id": str(chunk.id),
                "index": chunk.index,
                "text": chunk.text,
                "provenance": chunk.provenance.model_dump(mode="json"),
                "heading_path": chunk.heading_path,
                "content_kind": chunk.content_kind,
            }
            for chunk in chunks
        ]
        assert actual == case["chunks"]

    def test_golden_covers_a_heading_outline_and_an_empty_document(self) -> None:
        """The fixture holds the cases that could hide a difference."""
        assert any(
            chunk["heading_path"] for case in _GOLDEN for chunk in case["chunks"]
        )
        assert any(not case["chunks"] for case in _GOLDEN)
