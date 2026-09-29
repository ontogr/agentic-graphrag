"""Chunking-stage stats."""

from __future__ import annotations

from pydantic import BaseModel, Field


MAX_CHUNKING_MATCHES = 1000


class ChunkingMatch(BaseModel):
    """The chunker that one document got, and what it produced.

    Attributes:
        document_key: The key of the chunked document.
        rule: The index of the matching rule, or ``None`` for the fallback.
        strategy: The strategy name of the chunker.
        chunker_hash: The fingerprint of the chunker settings.
        chunks: The number of chunks the chunker produced.
    """

    document_key: str
    rule: int | None
    strategy: str
    chunker_hash: str
    chunks: int


class ChunkingStats(BaseModel):
    """Chunking-stage results.

    Attributes:
        chunks_by_strategy: Chunk counts per strategy name.
        documents_by_rule: Document counts per rule, keyed ``"rule 0"``,
            ``"rule 1"`` and so on, and ``"fallback"``.
        matches: One entry per chunked document, capped at 1000.
        matches_total: Matches recorded before capping.
        matches_truncated: Whether ``matches`` was cut to the cap.
    """

    chunks_by_strategy: dict[str, int] = Field(default_factory=dict)
    documents_by_rule: dict[str, int] = Field(default_factory=dict)
    matches: list[ChunkingMatch] = Field(default_factory=list)
    matches_total: int = 0
    matches_truncated: bool = False

    @classmethod
    def from_matches(cls, matches: list[ChunkingMatch]) -> ChunkingStats:
        """Summarize per-document matches.

        Args:
            matches: One match per chunked document, in chunking order.

        Returns:
            The counters over all matches and the matches up to the cap.
        """
        by_strategy: dict[str, int] = {}
        by_rule: dict[str, int] = {}
        for match in matches:
            by_strategy[match.strategy] = (
                by_strategy.get(match.strategy, 0) + match.chunks
            )
            rule = "fallback" if match.rule is None else f"rule {match.rule}"
            by_rule[rule] = by_rule.get(rule, 0) + 1
        return cls(
            chunks_by_strategy=by_strategy,
            documents_by_rule=by_rule,
            matches=matches[:MAX_CHUNKING_MATCHES],
            matches_total=len(matches),
            matches_truncated=len(matches) > MAX_CHUNKING_MATCHES,
        )
