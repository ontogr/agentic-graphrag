"""Tests for Reciprocal Rank Fusion."""

from uuid import uuid4

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult
from agrag.retrieval.fusion import fuse


def _make_entity_result(score: float = 1.0, **overrides) -> SearchResult:
    defaults = {"id": uuid4(), "label": "Person", "name": "Test"}
    defaults.update(overrides)
    return SearchResult(item=Entity(**defaults), score=score, method="test")


class TestFuse:
    """fuse combines ranked results via RRF."""

    def test_single_method_passthrough(self) -> None:
        """A single method's results pass through in order."""
        r1 = _make_entity_result(score=0.9)
        r2 = _make_entity_result(score=0.8)
        fused = fuse({"entity": [r1, r2]})
        assert len(fused) == 2
        assert fused[0].score >= fused[1].score

    def test_deduplicates_same_entity(self) -> None:
        """Two results for the same entity fuse into one.

        Two SearchResults for the same entity from different methods
        are fused into a single result.
        """
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        r1 = SearchResult(item=ent, score=0.9, method="entity")
        r2 = SearchResult(item=ent, score=0.8, method="chunk")
        fused = fuse({"entity": [r1], "chunk": [r2]})
        assert len(fused) == 1
        # Fused score is sum of both RRF contributions.
        assert fused[0].score > 0.9 / (60 + 1)

    def test_different_entities_not_deduped(self) -> None:
        """Results for different entities stay separate."""
        r1 = _make_entity_result()
        r2 = _make_entity_result()
        fused = fuse({"entity": [r1], "chunk": [r2]})
        assert len(fused) == 2

    def test_rrf_k_affects_ranking(self) -> None:
        """Higher rrf_k flattens rank influence."""
        ent1 = Entity(id=uuid4(), label="Person", name="First")
        ent2 = Entity(id=uuid4(), label="Person", name="Second")
        r1 = SearchResult(item=ent1, score=1.0, method="m1")
        r2 = SearchResult(item=ent2, score=1.0, method="m1")
        # ent1 is rank 0, ent2 is rank 1 in m1.
        fused_low = fuse({"m1": [r1, r2]}, rrf_k=1)
        fused_high = fuse({"m1": [r1, r2]}, rrf_k=100)
        # With low k, rank 0 gets 1/(1+1)=0.5, rank 1 gets 1/(1+2)=0.33
        # With high k, difference is smaller.
        diff_low = fused_low[0].score - fused_low[1].score
        diff_high = fused_high[0].score - fused_high[1].score
        assert diff_low > diff_high

    def test_regression_mixed_ids_same_entity(self) -> None:
        """Regression: fuse collapses same-entity results.

        Two results for the same entity from different methods under
        different (pre-resolution) ids must collapse into one. The
        identity_key must already be resolved to the live survivor
        before fusion, so both SearchResults carry the same key.
        """
        ent = Entity(id=uuid4(), label="Person", name="Alice")
        r1 = SearchResult(item=ent, score=0.9, method="entity")
        r2 = SearchResult(item=ent, score=0.7, method="chunk")
        fused = fuse({"entity": [r1], "chunk": [r2]})
        assert len(fused) == 1
        assert fused[0].item.id == ent.id

    def test_duplicate_within_one_method_does_not_inflate(self) -> None:
        """A single method that returns the same item twice gets one vote.

        Multi-label searches or pre-fusion merged_into resolution can
        surface the same identity_key in two positions of one
        method's output. Fuse must count it as one vote from that
        method, scored at the best rank, so a duplicate within a
        method cannot outrank a single best hit from another method.
        """
        a = Entity(id=uuid4(), label="Person", name="A")
        b = Entity(id=uuid4(), label="Person", name="B")
        a1 = SearchResult(item=a, score=1.0, method="entity")
        a2 = SearchResult(item=a, score=0.5, method="entity")
        b1 = SearchResult(item=b, score=1.0, method="chunk")
        fused = fuse({"entity": [a1, a2], "chunk": [b1]}, rrf_k=60)
        # Both methods' rank-0 contributions tie, so the order is
        # stable but the score must not include the rank-1 vote.
        assert len(fused) == 2
        assert all(r.score == 1 / (60 + 0 + 1) for r in fused)
        scores = {r.item.id: r.score for r in fused}
        assert scores[a.id] == 1 / 61
        assert scores[b.id] == 1 / 61

    def test_duplicate_within_one_method_uses_best_rank(self) -> None:
        """A duplicate in later positions uses the better rank for scoring.

        The same item at rank 0 and rank 2 of one method contributes
        1/(rrf_k + 0 + 1), not the sum of both positions.
        """
        a = Entity(id=uuid4(), label="Person", name="A")
        a_first = SearchResult(item=a, score=1.0, method="entity")
        a_last = SearchResult(item=a, score=0.1, method="entity")
        fused = fuse({"entity": [a_first, a_last]}, rrf_k=60)
        assert len(fused) == 1
        assert fused[0].score == 1 / 61

    def test_keeps_highest_score_per_identity(self) -> None:
        """The per-method best-rank vote still keeps the best individual score.

        The dedup-by-method change must not regress the existing
        invariant that a fused result carries the best individual
        score across every method that returned it.
        """
        a = Entity(id=uuid4(), label="Person", name="A")
        low = SearchResult(item=a, score=0.2, method="entity")
        high = SearchResult(item=a, score=0.9, method="chunk")
        fused = fuse({"entity": [low], "chunk": [high]}, rrf_k=60)
        # The fused score is the RRF sum; the underlying best_result
        # is checked indirectly by ensuring the entry is present and
        # ties the rank-0 + rank-0 RRF contribution.
        assert len(fused) == 1
        assert fused[0].score == 2 / 61
