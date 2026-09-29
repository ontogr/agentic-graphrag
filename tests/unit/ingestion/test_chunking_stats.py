"""Tests for ChunkingStats, the per-call summary of which chunker each document got."""

from agrag.ingestion.stats.chunking import (
    MAX_CHUNKING_MATCHES,
    ChunkingMatch,
    ChunkingStats,
)


def _match(key: str, rule: int | None, strategy: str, chunks: int) -> ChunkingMatch:
    return ChunkingMatch(
        document_key=key,
        rule=rule,
        strategy=strategy,
        chunker_hash="h",
        chunks=chunks,
    )


class TestChunkingStats:
    """from_matches counts chunks per strategy and documents per rule."""

    def test_counts_chunks_per_strategy_and_documents_per_rule(self) -> None:
        """Rule and fallback documents are counted under separate keys."""
        stats = ChunkingStats.from_matches(
            [
                _match("a", 0, "token", 3),
                _match("b", None, "recursive", 2),
                _match("c", None, "recursive", 4),
            ]
        )

        assert stats.chunks_by_strategy == {"token": 3, "recursive": 6}
        assert stats.documents_by_rule == {"rule 0": 1, "fallback": 2}
        assert stats.matches_total == 3
        assert not stats.matches_truncated

    def test_caps_matches_but_keeps_true_counts(self) -> None:
        """Matches beyond the cap are dropped; the counters still include them."""
        total = MAX_CHUNKING_MATCHES + 5
        stats = ChunkingStats.from_matches(
            [_match(f"d{i}", None, "recursive", 1) for i in range(total)]
        )

        assert len(stats.matches) == MAX_CHUNKING_MATCHES
        assert stats.matches_total == total
        assert stats.matches_truncated
        assert stats.chunks_by_strategy == {"recursive": total}
