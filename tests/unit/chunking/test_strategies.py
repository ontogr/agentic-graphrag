"""Tests for the recursive, token and sentence strategies.

The strategies cut boundaries with chonkie, and this suite checks what agrag
promises on top of that: chunk text is the source slice, spans are ordered, cuts
cover the text, settings are validated, and the tokenizer loads with sockets off.
"""

import random

import pytest

from agrag.chunking import (
    RecursiveChunker,
    SentenceChunker,
    SplitLevel,
    TokenChunker,
)
from agrag.common.data_models.provenance import TextProvenance
from tests.unit.chunking._support import make_document


_EMOJI_CJK = "Emoji \U0001f600\U0001f680 and 日本語 and é ä. "

_STRATEGIES = {
    "recursive": lambda size: RecursiveChunker(chunk_size=size),
    "token": lambda size: TokenChunker(chunk_size=size),
    "sentence": lambda size: SentenceChunker(chunk_size=size),
}


def _random_text(seed: int) -> str:
    rng = random.Random(seed)
    pool = "abc def. ghi\n\n日本 \U0001f600 é ! ? 12,3"
    return "".join(rng.choice(pool) for _ in range(rng.randint(0, 900)))


def _spans(chunks) -> list[tuple[int, int]]:
    result = []
    for chunk in chunks:
        assert isinstance(chunk.provenance, TextProvenance)
        result.append((chunk.provenance.char_start, chunk.provenance.char_end))
    return result


class TestTextStrategies:
    """Every text strategy keeps text equal to its source slice."""

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    @pytest.mark.parametrize("size", [8, 32, 128])
    def test_chunks_are_ordered_source_slices_that_cover_the_text(
        self, strategy: str, size: int
    ) -> None:
        """Random Unicode text: slices match, spans are ordered, gaps are blank."""
        chunker = _STRATEGIES[strategy](size)
        for seed in range(200):
            document = make_document(_random_text(seed))

            chunks = chunker.chunk(document)

            spans = _spans(chunks)
            assert [c.index for c in chunks] == list(range(len(chunks)))
            for chunk, (start, end) in zip(chunks, spans, strict=True):
                assert chunk.text == document.text[start:end]
            covered_to = 0
            for start, end in spans:
                assert start >= covered_to
                assert not document.text[covered_to:start].strip()
                covered_to = end
            assert not document.text[covered_to:].strip()

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    def test_empty_text_gives_no_chunks(self, strategy: str) -> None:
        """An empty document makes no chunks and does not raise."""
        assert _STRATEGIES[strategy](16).chunk(make_document("")) == []

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    def test_tiny_text_gives_one_chunk(self, strategy: str) -> None:
        """Text shorter than one chunk stays whole."""
        chunks = _STRATEGIES[strategy](64).chunk(make_document("short text"))

        assert [c.text for c in chunks] == ["short text"]

    @pytest.mark.parametrize("strategy", ["recursive", "token"])
    def test_one_oversized_unit_is_split(self, strategy: str) -> None:
        """A 5,000 character word with no break points is still cut."""
        document = make_document("x" * 5000)

        chunks = _STRATEGIES[strategy](64).chunk(document)

        assert len(chunks) > 1
        assert "".join(c.text for c in chunks) == document.text

    def test_sentence_strategy_keeps_one_oversized_sentence_whole(self) -> None:
        """A sentence above the budget is not cut inside the sentence."""
        document = make_document("x" * 5000)

        chunks = SentenceChunker(chunk_size=64).chunk(document)

        assert [c.text for c in chunks] == [document.text]

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    def test_non_ascii_text_keeps_exact_offsets(self, strategy: str) -> None:
        """Emoji, CJK and combining marks at cut points do not shift offsets."""
        document = make_document(_EMOJI_CJK * 40)

        chunks = _STRATEGIES[strategy](12).chunk(document)

        assert len(chunks) > 1
        for chunk, (start, end) in zip(chunks, _spans(chunks), strict=True):
            assert chunk.text == document.text[start:end]

    @pytest.mark.parametrize("strategy", _STRATEGIES)
    def test_two_runs_give_the_same_chunks(self, strategy: str) -> None:
        """Chunking is a pure function of the document and the settings."""
        document = make_document(_EMOJI_CJK * 30)
        chunker = _STRATEGIES[strategy](16)

        def identity(chunks):
            return [(c.id, c.text, c.provenance, c.chunker_hash) for c in chunks]

        assert identity(chunker.chunk(document)) == identity(chunker.chunk(document))

    def test_tokenizer_loads_without_network(self, socket_disabled) -> None:
        """The default tokenizer needs no download."""
        chunks = TokenChunker(chunk_size=8, tokenizer="o200k_base").chunk(
            make_document("one two three four five six seven eight nine ten")
        )

        assert len(chunks) > 1

    def test_token_size_bounds_the_token_count(self) -> None:
        """Chunks of a token chunker are smaller than the same text in characters."""
        text = "word " * 400
        by_token = TokenChunker(chunk_size=32).chunk(make_document(text))
        by_character = TokenChunker(chunk_size=32, tokenizer="character").chunk(
            make_document(text)
        )

        assert len(by_token) < len(by_character)
        assert max(len(c.text) for c in by_character) <= 32


class TestOverlap:
    """Overlapping chunks keep exact spans."""

    def test_token_chunks_overlap_by_the_set_amount(self) -> None:
        """With character units, neighbours share ``chunk_overlap`` characters."""
        document = make_document("0123456789" * 20)
        chunker = TokenChunker(chunk_size=20, chunk_overlap=5, tokenizer="character")

        spans = _spans(chunker.chunk(document))

        assert len(spans) > 2
        for (_, end), (start, _) in zip(spans, spans[1:], strict=False):
            assert end - start == 5

    def test_overlap_slices_still_equal_the_text(self) -> None:
        """Every overlapping chunk equals the source at its span."""
        document = make_document(_EMOJI_CJK * 20)
        chunker = SentenceChunker(
            chunk_size=40, chunk_overlap=10, tokenizer="character"
        )

        for chunk, (start, end) in zip(
            chunker.chunk(document), _spans(chunker.chunk(document)), strict=True
        ):
            assert chunk.text == document.text[start:end]


class TestSettingValidation:
    """Bad settings fail when the chunker is built."""

    @pytest.mark.parametrize("size", [0, -3])
    @pytest.mark.parametrize("strategy", _STRATEGIES)
    def test_rejects_non_positive_size(self, strategy: str, size: int) -> None:
        """Size must be above zero."""
        with pytest.raises(ValueError, match="chunk_size"):
            _STRATEGIES[strategy](size)

    @pytest.mark.parametrize(
        "build",
        [
            lambda o: TokenChunker(chunk_size=64, chunk_overlap=o),
            lambda o: SentenceChunker(chunk_size=64, chunk_overlap=o),
        ],
        ids=["token", "sentence"],
    )
    def test_rejects_overlap_not_below_size(self, build) -> None:
        """Overlap must stay smaller than the window."""
        with pytest.raises(ValueError, match="chunk_overlap"):
            build(64)

    def test_rejects_float_overlap_of_one_or_more(self) -> None:
        """A float overlap is a share of the window and stays below 1."""
        with pytest.raises(ValueError, match="chunk_overlap"):
            TokenChunker(chunk_size=64, chunk_overlap=1.0)

    def test_rejects_unknown_tokenizer(self) -> None:
        """A tokenizer that cannot load fails at construction."""
        with pytest.raises(ValueError, match="Cannot build the token chunker"):
            TokenChunker(tokenizer="no-such-tokenizer-xyz")

    def test_rejects_unknown_setting(self) -> None:
        """A misspelled setting is an error, not ignored."""
        with pytest.raises(ValueError, match="chunk_sizes"):
            RecursiveChunker(chunk_sizes=10)  # ty: ignore[unknown-argument]


class TestRecursiveLevels:
    """Custom levels change where the recursive strategy cuts."""

    def test_split_levels_are_immutable(self) -> None:
        """Split levels cannot diverge from the initialized engine settings."""
        chunker = RecursiveChunker(levels=[SplitLevel(delimiters=["|"])])

        with pytest.raises(AttributeError):
            chunker.levels.append(SplitLevel(whitespace=True))
        with pytest.raises(AttributeError):
            chunker.levels[0].delimiters.append("/")

    def test_custom_level_splits_on_its_delimiter(self) -> None:
        """A level that splits on ``|`` cuts at the bars."""
        text = ("alpha beta gamma|" * 30).rstrip("|")
        chunker = RecursiveChunker(
            chunk_size=40,
            tokenizer="character",
            levels=[SplitLevel(delimiters=["|"]), SplitLevel(whitespace=True)],
        )

        chunks = chunker.chunk(make_document(text))

        assert all(c.text.endswith("|") for c in chunks[:-1])
