"""Tests for Chunking rules: matching, order, fallback and fingerprints."""

import pytest

from agrag.chunking import (
    DEFAULT_CHUNKING,
    Chunking,
    ChunkingRule,
    DoclingChunker,
    RecursiveChunker,
    RuleMatch,
    TokenChunker,
)
from agrag.common.data_models.document import DocumentFamily, SourceFormat
from tests.unit.chunking._support import make_document


_FALLBACK = RecursiveChunker(chunk_size=100)
_TOKEN = TokenChunker(chunk_size=50)
_OTHER = TokenChunker(chunk_size=60)


def _chunking(*matches: RuleMatch) -> Chunking:
    rules = [
        ChunkingRule(match=match, chunker=TokenChunker(chunk_size=50 + position))
        for position, match in enumerate(matches)
    ]
    return Chunking(rules=rules, fallback=_FALLBACK)


class TestSelect:
    """select returns the first matching rule, else the fallback."""

    def test_empty_rule_list_uses_the_fallback(self) -> None:
        """No rules means every document gets the fallback."""
        rule, chunker = Chunking(fallback=_FALLBACK).select(make_document("a"))

        assert rule is None
        assert chunker is _FALLBACK

    def test_first_matching_rule_wins(self) -> None:
        """Two rules match; the earlier one is used."""
        chunking = _chunking(
            RuleMatch(source_formats=[SourceFormat.MARKDOWN]),
            RuleMatch(loader_names=["text"]),
        )
        document = make_document("a", source_format=SourceFormat.MARKDOWN)

        rule, chunker = chunking.select(document)

        assert rule == 0
        assert chunker is chunking.rules[0].chunker

    def test_rule_beats_the_fallback(self) -> None:
        """A markdown rule takes markdown documents; other formats fall through."""
        chunking = _chunking(RuleMatch(source_formats=[SourceFormat.MARKDOWN]))

        md_rule, _ = chunking.select(
            make_document("a", source_format=SourceFormat.MARKDOWN)
        )
        txt_rule, txt_chunker = chunking.select(make_document("a"))

        assert md_rule == 0
        assert (txt_rule, txt_chunker) == (None, _FALLBACK)

    def test_keys_combine_with_and(self) -> None:
        """A rule with two keys needs both to match."""
        chunking = _chunking(
            RuleMatch(loader_names=["text"], source_formats=[SourceFormat.MARKDOWN])
        )

        assert chunking.select(make_document("a"))[0] is None
        assert (
            chunking.select(make_document("a", source_format=SourceFormat.MARKDOWN))[0]
            == 0
        )

    def test_list_values_combine_with_or(self) -> None:
        """A list key matches any of its items."""
        chunking = _chunking(
            RuleMatch(source_formats=[SourceFormat.MARKDOWN, SourceFormat.HTML])
        )

        assert (
            chunking.select(make_document("a", source_format=SourceFormat.HTML))[0] == 0
        )

    @pytest.mark.parametrize(
        ("uri", "expected"),
        [
            ("docs/a.md", 0),
            ("docs/sub/a.md", 0),
            ("other/a.md", None),
            ("Docs/a.md", None),
        ],
    )
    def test_uri_glob_matches_case_sensitively(
        self, uri: str, expected: int | None
    ) -> None:
        """The glob uses fnmatch rules and is case sensitive."""
        chunking = _chunking(RuleMatch(uri_glob="docs/*.md"))

        assert chunking.select(make_document("a", uri=uri))[0] == expected

    def test_family_key_matches_record_documents(self) -> None:
        """The family key separates prose from record documents."""
        chunking = _chunking(RuleMatch(families=[DocumentFamily.RECORD]))

        assert chunking.select(make_document("a", family=DocumentFamily.RECORD))[0] == 0
        assert chunking.select(make_document("a"))[0] is None

    def test_all_none_match_takes_every_document(self) -> None:
        """A rule with no keys matches everything, so later rules never run."""
        chunking = _chunking(RuleMatch(), RuleMatch(loader_names=["text"]))

        assert chunking.select(make_document("a"))[0] == 0


class TestFingerprint:
    """The chunking fingerprint changes with every part of the rules."""

    def test_changes_when_only_the_fallback_size_changes(self) -> None:
        """Nested chunker settings are part of the hash."""
        one = Chunking(fallback=RecursiveChunker(chunk_size=100))
        two = Chunking(fallback=RecursiveChunker(chunk_size=101))

        assert one.fingerprint() != two.fingerprint()

    def test_changes_with_a_rule_match_or_a_rule_chunker(self) -> None:
        """Rule keys and rule chunker settings are part of the hash."""
        base = Chunking(
            rules=[ChunkingRule(match=RuleMatch(loader_names=["a"]), chunker=_TOKEN)],
            fallback=_FALLBACK,
        )
        other_match = base.model_copy(
            update={
                "rules": [
                    ChunkingRule(match=RuleMatch(loader_names=["b"]), chunker=_TOKEN)
                ]
            }
        )
        other_chunker = base.model_copy(
            update={
                "rules": [
                    ChunkingRule(match=RuleMatch(loader_names=["a"]), chunker=_OTHER)
                ]
            }
        )

        assert (
            len(
                {
                    base.fingerprint(),
                    other_match.fingerprint(),
                    other_chunker.fingerprint(),
                }
            )
            == 3
        )


class TestDefaultChunking:
    """DEFAULT_CHUNKING lists its rules as plain data."""

    def test_sends_docling_documents_to_the_docling_chunker(self) -> None:
        """The one shipped rule matches on the loader name."""
        document = make_document("a", loader_name="docling")

        rule, chunker = DEFAULT_CHUNKING.select(document)

        assert rule == 0
        assert isinstance(chunker, DoclingChunker)

    def test_dumps_chunker_settings_as_json(self) -> None:
        """The JSON names each strategy and shows the fallback settings."""
        dumped = DEFAULT_CHUNKING.model_dump(mode="json")

        assert dumped["rules"][0]["chunker"] == {
            "strategy": "docling",
            "tokenizer": "o200k_base",
            "max_tokens": 1024,
            "merge_peers": True,
            "repeat_table_header": True,
            "omit_header_on_overflow": False,
            "table_format": "triplet",
        }
        assert dumped["fallback"]["strategy"] == "recursive"
        assert dumped["fallback"]["chunk_size"] == 1024
        assert dumped["fallback"]["tokenizer"] == "character"
