"""Tests for TurnWindowChunker: whole turns packed to a token budget.

The tests count with the ``character`` tokenizer, so a budget is a number of
characters and each window is easy to predict.
"""

import random

import pytest

from agrag.chunking import RecursiveChunker, TurnWindowChunker
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document
from agrag.common.data_models.provenance import TextProvenance
from tests.unit.chunking._support import (
    content_for,
    make_chat_document,
    make_document,
)


def _chunker(size: int, overlap: int = 0) -> TurnWindowChunker:
    return TurnWindowChunker(
        chunk_size=size,
        turn_overlap=overlap,
        tokenizer="character",
        fallback=RecursiveChunker(chunk_size=size, tokenizer="character"),
    )


def _turn_indexes(document: Document, chunk: Chunk) -> list[int]:
    """Return the indexes of the turns that a chunk span fully holds."""
    assert isinstance(chunk.provenance, TextProvenance)
    return [
        i
        for i, t in enumerate(document.turns)
        if chunk.provenance.char_start <= t.char_start
        and t.char_end <= chunk.provenance.char_end
    ]


class TestPacking:
    """Windows hold whole turns and stay within the budget."""

    def test_packs_turns_up_to_the_budget(self) -> None:
        """Turns of 10 characters pack three to a window at a budget of 36."""
        document = make_chat_document([content_for(i, 10) for i in range(7)])

        chunks = _chunker(36).chunk(document)

        assert [_turn_indexes(document, c) for c in chunks] == [
            [0, 1, 2],
            [3, 4, 5],
            [6],
        ]

    def test_a_turn_exactly_at_the_budget_fills_a_window(self) -> None:
        """A turn whose size equals the budget is not oversized."""
        document = make_chat_document([content_for(0, 21), content_for(1, 21)])

        chunks = _chunker(21).chunk(document)

        assert [c.chunker for c in chunks] == ["turn-window", "turn-window"]
        assert [_turn_indexes(document, c) for c in chunks] == [[0], [1]]

    def test_no_turn_is_split_when_all_fit(self) -> None:
        """Every chunk boundary falls between turns."""
        document = make_chat_document([f"message number {i}" for i in range(12)])

        chunks = _chunker(80).chunk(document)

        held = [i for c in chunks for i in _turn_indexes(document, c)]
        assert held == list(range(12))

    def test_windows_overlap_by_the_set_number_of_turns(self) -> None:
        """With turn_overlap 1, each window repeats the last turn of the one before."""
        document = make_chat_document([content_for(i, 10) for i in range(7)])

        chunks = _chunker(36, overlap=1).chunk(document)

        windows = [_turn_indexes(document, c) for c in chunks]
        assert windows == [[0, 1, 2], [2, 3, 4], [4, 5, 6]]

    def test_overlap_of_one_with_one_turn_windows_still_advances(self) -> None:
        """A window of one turn moves on even when the overlap is one."""
        document = make_chat_document([content_for(i, 40) for i in range(3)])

        chunks = _chunker(50, overlap=1).chunk(document)

        assert [_turn_indexes(document, c) for c in chunks] == [[0], [1], [2]]

    def test_overlap_larger_than_the_window_still_advances(self) -> None:
        """An overlap of five with windows of two turns gives one new turn each time."""
        document = make_chat_document([content_for(i, 10) for i in range(5)])

        windows = [
            _turn_indexes(document, c) for c in _chunker(24, overlap=5).chunk(document)
        ]

        assert windows == [[0, 1], [1, 2], [2, 3], [3, 4]]

    def test_many_tiny_turns_fill_one_window(self) -> None:
        """Small turns share a window."""
        document = make_chat_document(["a"] * 4)

        assert len(_chunker(1000).chunk(document)) == 1


class TestStructureAroundTurns:
    """Text outside turns stays in the chunks."""

    def test_header_before_the_first_turn_is_in_chunk_zero(self) -> None:
        """A date line before the first turn begins the first chunk."""
        document = make_chat_document(["hello", "world"], header="Session 2024-01-01")

        chunks = _chunker(500).chunk(document)

        assert chunks[0].text.startswith("Session 2024-01-01")
        assert chunks[0].provenance.char_start == 0

    def test_text_after_the_last_turn_is_in_the_last_chunk(self) -> None:
        """A footer after the last turn ends the last chunk."""
        document = make_chat_document(["hello", "world"], trailer="\n\n-- end --")

        assert _chunker(500).chunk(document)[-1].text.endswith("-- end --")

    def test_text_between_turns_is_not_lost(self) -> None:
        """A non-blank separator stays with the turn before it."""
        document = make_chat_document(["one", "two"], separator="\n--- break ---\n")

        chunks = _chunker(15).chunk(document)

        assert "--- break ---" in "".join(c.text for c in chunks)


class TestOversizedTurns:
    """A turn above the budget is split by the fallback and flagged."""

    def test_oversized_turn_uses_the_fallback_and_is_flagged(self) -> None:
        """Only the pieces of the big turn carry the fallback label."""
        big = " ".join(f"word{i}" for i in range(80))
        document = make_chat_document(["short", big, "tail"])

        chunks = _chunker(60).chunk(document)

        flagged = [c for c in chunks if c.chunker == "turn-window:recursive"]
        assert len(flagged) > 1
        assert "".join(c.text for c in flagged).replace("\n", "").count("word") == 80
        assert chunks[0].chunker == "turn-window"
        assert chunks[-1].chunker == "turn-window"

    def test_overlap_does_not_repeat_turns_across_an_oversized_turn(self) -> None:
        """No window holds only the overlap turn before a big turn."""
        big = "x" * 300
        document = make_chat_document(["a", "b", big, "c"])

        chunks = _chunker(60, overlap=1).chunk(document)

        assert [
            _turn_indexes(document, c) for c in chunks if c.chunker == "turn-window"
        ] == [
            [0, 1],
            [3],
        ]


class TestNoTurns:
    """A document without turns is split by the fallback."""

    def test_falls_back_and_says_so(self) -> None:
        """Chunks carry the fallback label."""
        document = make_document("plain words " * 50)

        chunks = _chunker(60).chunk(document)

        assert len(chunks) > 1
        assert {c.chunker for c in chunks} == {"turn-window:recursive"}

    def test_empty_document_gives_no_chunks(self) -> None:
        """No text, no chunks, no error."""
        assert _chunker(60).chunk(make_document("")) == []


class TestProperties:
    """Random chat structures keep the contract."""

    def test_spans_cover_all_non_blank_text_in_order(self) -> None:
        """Every non-blank character sits in some chunk; slices match the source."""
        rng = random.Random(7)
        words = ["alpha", "beta", "日本", "\U0001f600", "é", "gamma delta"]
        for seed in range(100):
            rng.seed(seed)
            contents = [
                " ".join(rng.choice(words) for _ in range(rng.randint(1, 30)))
                for _ in range(rng.randint(1, 12))
            ]
            document = make_chat_document(
                contents,
                header=rng.choice(["", "Header line"]),
                trailer=rng.choice(["", "\nfooter"]),
            )
            chunker = _chunker(rng.choice([20, 60, 200]), rng.choice([0, 1, 2]))

            chunks = chunker.chunk(document)

            covered = [False] * len(document.text)
            for chunk in chunks:
                p = chunk.provenance
                assert isinstance(p, TextProvenance)
                assert chunk.text == document.text[p.char_start : p.char_end]
                for i in range(p.char_start, p.char_end):
                    covered[i] = True
            missed = [
                i
                for i, c in enumerate(covered)
                if not c and not document.text[i].isspace()
            ]
            assert not missed

    def test_same_input_gives_the_same_chunks(self) -> None:
        """Chunking is deterministic."""
        document = make_chat_document([f"turn {i} " * 5 for i in range(9)])
        chunker = _chunker(70, overlap=1)

        def ids(chunks: list[Chunk]) -> list[object]:
            return [(c.id, c.text, c.chunker) for c in chunks]

        assert ids(chunker.chunk(document)) == ids(chunker.chunk(document))


class TestSettings:
    """Settings are validated and hashed."""

    @pytest.mark.parametrize("field", ["chunk_size"])
    def test_rejects_non_positive_size(self, field: str) -> None:
        """The budget must be above zero."""
        with pytest.raises(ValueError, match=field):
            TurnWindowChunker(**{field: 0})

    def test_rejects_negative_overlap(self) -> None:
        """Overlap counts turns and cannot be negative."""
        with pytest.raises(ValueError, match="turn_overlap"):
            TurnWindowChunker(turn_overlap=-1)

    def test_fallback_settings_are_part_of_the_fingerprint(self) -> None:
        """A different fallback gives a different fingerprint."""
        one = TurnWindowChunker(fallback=RecursiveChunker(chunk_size=100))
        two = TurnWindowChunker(fallback=RecursiveChunker(chunk_size=200))

        assert one.fingerprint() != two.fingerprint()
        assert one.settings()["fallback"]["chunk_size"] == 100
