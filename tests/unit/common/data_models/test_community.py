"""Tests for the Community domain model."""

from uuid import uuid4

from agrag.common.data_models.community import (
    COMMUNITY_LABEL,
    MEMBER_OF_RELATION,
    Community,
)


class TestCommunity:
    """Community mirrors Entity's DataPoint shape."""

    def test_to_node_record_round_trip(self) -> None:
        """Community survives to_node_record with expected labels and props."""
        m1, m2 = uuid4(), uuid4()
        comm = Community(
            id=uuid4(),
            title="Title",
            summary="Summary",
            rating=7.5,
            rating_explanation="exp",
            findings=["f1", "f2"],
            member_ids=[m1, m2],
            internal_weight=3.5,
            embedding=[0.1, 0.2],
        )
        rec = comm.to_node_record()
        assert rec.labels == [COMMUNITY_LABEL]
        assert rec.properties["title"] == "Title"
        assert rec.properties["member_ids"] == [str(m1), str(m2)]
        assert rec.properties["embedding"] == [0.1, 0.2]

    def test_embedding_text(self) -> None:
        """embedding_text joins title and summary."""
        comm = Community(
            id=uuid4(), title="T", summary="S", rating=1, rating_explanation="e"
        )
        assert comm.embedding_text == "T: S"

    def test_constants(self) -> None:
        """Label and relation constants have expected values."""
        assert COMMUNITY_LABEL == "Community"
        assert MEMBER_OF_RELATION == "MEMBER_OF"

    def test_defaults(self) -> None:
        """Defaults are empty findings, member_ids, zero weight, no embedding."""
        comm = Community(
            id=uuid4(), title="T", summary="S", rating=0, rating_explanation=""
        )
        assert comm.findings == []
        assert comm.member_ids == []
        assert comm.internal_weight == 0.0
        assert comm.embedding is None
        rec = comm.to_node_record()
        assert "embedding" not in rec.properties
