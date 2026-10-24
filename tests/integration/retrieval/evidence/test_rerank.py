"""Integration tests for the rerank stage inside hybrid evidence search.

Rerank is not a tool: it reorders the fused hits of one hybrid search when a
reranker is injected. The rerankers here are deterministic fakes, so no model
downloads and the fused baseline is comparable across runs.
"""

import asyncio
import re
from collections.abc import Sequence

from agrag.common.data_models.evidence import (
    EvidenceSearchLeg,
    EvidenceSearchMode,
    EvidenceSearchStatus,
    LegFailure,
)
from agrag.evidence import search_evidence
from agrag.retrieval.settings import RetrievalSettings
from tests.integration.retrieval.evidence._corpus import (
    GOLD_SENTENCE,
    BagOfWordsEmbedder,
)
from tests.integration.retrieval.evidence.conftest import EvidenceEnv


_QUERY = "do you keep and upload my activity to your database"


def _full_scope(env: EvidenceEnv) -> frozenset[str]:
    """Return the scope of all three authored documents."""
    return frozenset({env.keep, env.viber, env.harbor})


class _WordOverlapReranker:
    """Reranker that scores a passage by its word overlap with a phrase."""

    def __init__(self, phrase: str) -> None:
        self._words = frozenset(re.findall(r"[a-z]+", phrase.lower()))

    async def __call__(self, query: str, texts: Sequence[str]) -> list[float]:
        """Return one overlap count per text, higher for closer passages."""
        return [
            float(len(self._words & set(re.findall(r"[a-z]+", text.lower()))))
            for text in texts
        ]


class _ExplodingReranker:
    """Reranker whose backend crashes on every call."""

    async def __call__(self, query: str, texts: Sequence[str]) -> list[float]:
        """Raise with an error that carries backend details."""
        raise RuntimeError("cross-encoder endpoint crashed at 10.0.0.7")


class _SlowReranker:
    """Reranker that takes longer than any test timeout."""

    async def __call__(self, query: str, texts: Sequence[str]) -> list[float]:
        """Sleep, then return uniform scores that are never used."""
        await asyncio.sleep(2)
        return [1.0 for _ in texts]


def _evidence_ids(result_hits: list) -> list[str]:
    """Return the evidence ids of hits, best first."""
    return [hit.evidence_id for hit in result_hits]


class TestRerankInHybrid:
    """A reranker reorders fused hybrid hits and reports itself."""

    async def test_reranker_puts_the_gold_passage_first(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """The passage matching the reranker phrase ranks first and reranked is set."""
        result = await search_evidence(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _QUERY,
            mode=EvidenceSearchMode.HYBRID,
            limit=5,
            scope=_full_scope(evidence_env),
            reranker=_WordOverlapReranker(GOLD_SENTENCE),
        )

        assert result.status is EvidenceSearchStatus.OK
        assert result.reranked is True
        assert result.hits[0].document_key == evidence_env.keep
        location = result.hits[0].location
        assert location.char_start is not None and location.char_end is not None
        assert result.hits[0].legs == [
            EvidenceSearchLeg.LEXICAL,
            EvidenceSearchLeg.SEMANTIC,
        ]

    async def test_reranked_scores_come_from_the_reranker(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Each hit's score is the reranker score of its own text."""
        reranker = _WordOverlapReranker(GOLD_SENTENCE)
        result = await search_evidence(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _QUERY,
            mode=EvidenceSearchMode.HYBRID,
            limit=5,
            scope=_full_scope(evidence_env),
            reranker=reranker,
        )

        assert result.reranked is True
        scores = [hit.score for hit in result.hits]
        assert scores == sorted(scores, reverse=True)
        assert result.hits[0].score > 0

    async def test_lexical_mode_ignores_the_reranker(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Lexical search returns the same order with and without a reranker."""
        without = await search_evidence(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _QUERY,
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=_full_scope(evidence_env),
        )
        with_reranker = await search_evidence(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _QUERY,
            mode=EvidenceSearchMode.LEXICAL,
            limit=5,
            scope=_full_scope(evidence_env),
            reranker=_WordOverlapReranker(GOLD_SENTENCE),
        )

        assert with_reranker.reranked is False
        assert _evidence_ids(with_reranker.hits) == _evidence_ids(without.hits)

    async def test_semantic_mode_ignores_the_reranker(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Semantic search returns the same order with and without a reranker."""
        without = await search_evidence(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _QUERY,
            mode=EvidenceSearchMode.SEMANTIC,
            limit=5,
            scope=_full_scope(evidence_env),
        )
        with_reranker = await search_evidence(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _QUERY,
            mode=EvidenceSearchMode.SEMANTIC,
            limit=5,
            scope=_full_scope(evidence_env),
            reranker=_WordOverlapReranker(GOLD_SENTENCE),
        )

        assert with_reranker.reranked is False
        assert _evidence_ids(with_reranker.hits) == _evidence_ids(without.hits)


class TestRerankFailure:
    """A failed or slow reranker keeps the fused result and reports one failure."""

    async def test_crashing_reranker_keeps_the_fused_order(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """The fused order stands, the status stays ok, and the stage is recorded."""
        baseline = await search_evidence(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _QUERY,
            mode=EvidenceSearchMode.HYBRID,
            limit=5,
            scope=_full_scope(evidence_env),
        )
        failed = await search_evidence(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _QUERY,
            mode=EvidenceSearchMode.HYBRID,
            limit=5,
            scope=_full_scope(evidence_env),
            reranker=_ExplodingReranker(),
            settings=RetrievalSettings(rerank_candidates=5),
        )

        assert failed.status is EvidenceSearchStatus.OK
        assert failed.reranked is False
        assert failed.failures == [
            LegFailure(leg=EvidenceSearchLeg.RERANK, message="rerank failed")
        ]
        assert _evidence_ids(failed.hits) == _evidence_ids(baseline.hits)
        assert "10.0.0.7" not in failed.model_dump_json()

    async def test_slow_reranker_times_out_and_keeps_the_fused_order(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """A rerank past its timeout is dropped, not waited for."""
        baseline = await search_evidence(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _QUERY,
            mode=EvidenceSearchMode.HYBRID,
            limit=5,
            scope=_full_scope(evidence_env),
        )
        settings = RetrievalSettings(rerank_candidates=5, rerank_timeout_seconds=0.05)
        slow = await search_evidence(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _QUERY,
            mode=EvidenceSearchMode.HYBRID,
            limit=5,
            scope=_full_scope(evidence_env),
            reranker=_SlowReranker(),
            settings=settings,
        )

        assert slow.status is EvidenceSearchStatus.OK
        assert slow.reranked is False
        assert slow.failures == [
            LegFailure(leg=EvidenceSearchLeg.RERANK, message="rerank failed")
        ]
        assert _evidence_ids(slow.hits) == _evidence_ids(baseline.hits)

    async def test_single_hit_is_never_reranked(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """One fused hit is returned as is, even with a reranker configured."""
        result = await search_evidence(
            evidence_env.store,
            BagOfWordsEmbedder(),
            _QUERY,
            mode=EvidenceSearchMode.HYBRID,
            limit=1,
            scope=_full_scope(evidence_env),
            reranker=_WordOverlapReranker("viber messaging app calls"),
            settings=RetrievalSettings(rerank_candidates=1),
        )

        assert result.status is EvidenceSearchStatus.OK
        assert result.reranked is False
        assert result.failures == []
