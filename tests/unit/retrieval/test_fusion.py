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
