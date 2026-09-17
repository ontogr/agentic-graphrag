"""Tests for compute_communities clustering and importance signals."""

from collections import namedtuple
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from agrag.ingestion.community import (
    CommunityDetectionMissingExtraError,
    compute_communities,
)


HC = namedtuple(  # type: ignore[misc]
    "HC",
    ["node", "cluster", "parent_cluster", "level", "is_final_cluster"],
)


def _mock_leiden(mock_clusters: list) -> MagicMock:
    """Return a mocked graspologic_native module yielding mock_clusters."""
    return MagicMock(hierarchical_leiden=MagicMock(return_value=mock_clusters))


class TestComputeCommunities:
    """compute_communities level filtering, singleton exclusion, weights, ordering."""

    def test_level_filtering_and_singleton_exclusion(self) -> None:
        """Only level 0 kept; singleton clusters excluded."""
        ids = [str(uuid4()) for _ in range(5)]
        a, b, c, d, e = ids
        mock_clusters = [
            HC(node=a, cluster=0, parent_cluster=None, level=0, is_final_cluster=True),
            HC(node=b, cluster=0, parent_cluster=None, level=0, is_final_cluster=True),
            HC(node=c, cluster=1, parent_cluster=None, level=0, is_final_cluster=True),
            HC(node=d, cluster=1, parent_cluster=None, level=0, is_final_cluster=True),
            HC(node=e, cluster=2, parent_cluster=None, level=0, is_final_cluster=True),
            HC(
                node=a, cluster=10, parent_cluster=None, level=1, is_final_cluster=False
            ),
        ]
        edges = [(a, b, 2.0, "KNOWS"), (c, d, 1.0, "KNOWS")]
        with patch.dict(
            "sys.modules", {"graspologic_native": _mock_leiden(mock_clusters)}
        ):
            comms = compute_communities(edges, max_cluster_size=10)
            assert len(comms) == 2
            assert {
                tuple(sorted(str(member_id) for member_id in community.member_ids))
                for community in comms
            } == {(a, b), (c, d)}

    def test_internal_weight_only_internal_edges(self) -> None:
        """Cross-cluster edge contributes to neither community's weight."""
        ids = [str(uuid4()) for _ in range(4)]
        a, b, c, d = ids
        mock_clusters = [
            HC(node=a, cluster=0, parent_cluster=None, level=0, is_final_cluster=True),
            HC(node=b, cluster=0, parent_cluster=None, level=0, is_final_cluster=True),
            HC(node=c, cluster=1, parent_cluster=None, level=0, is_final_cluster=True),
            HC(node=d, cluster=1, parent_cluster=None, level=0, is_final_cluster=True),
        ]
        edges = [(a, b, 2.0, "KNOWS"), (c, d, 1.0, "KNOWS"), (a, c, 5.0, "KNOWS")]
        with patch.dict(
            "sys.modules", {"graspologic_native": _mock_leiden(mock_clusters)}
        ):
            comms = compute_communities(edges)
            for co in comms:
                mstrs = {str(m) for m in co.member_ids}
                if a in mstrs:
                    assert co.internal_weight == 2.0
                else:
                    assert co.internal_weight == 1.0

    def test_member_ordering_by_local_weight(self) -> None:
        """member_ids ordered descending by local weight; stable on tie."""
        ids = [str(uuid4()) for _ in range(3)]
        x, y, z = ids
        mock_clusters = [
            HC(node=n, cluster=5, parent_cluster=None, level=0, is_final_cluster=True)
            for n in ids
        ]
        edges = [(x, y, 10.0, "KNOWS"), (x, z, 1.0, "KNOWS")]
        with patch.dict(
            "sys.modules", {"graspologic_native": _mock_leiden(mock_clusters)}
        ):
            comms = compute_communities(edges)
            assert [str(m) for m in comms[0].member_ids] == [x, y, z]

    def test_tie_stable(self) -> None:
        """Tie in member weight produces stable order."""
        ids = [str(uuid4()) for _ in range(3)]
        mock_clusters = [
            HC(node=n, cluster=0, parent_cluster=None, level=0, is_final_cluster=True)
            for n in ids
        ]
        edges = [
            (ids[0], ids[1], 1.0, "KNOWS"),
            (ids[1], ids[2], 1.0, "KNOWS"),
            (ids[2], ids[0], 1.0, "KNOWS"),
        ]
        with patch.dict(
            "sys.modules", {"graspologic_native": _mock_leiden(mock_clusters)}
        ):
            comms = compute_communities(edges)
            assert [str(m) for m in comms[0].member_ids] == ids

    def test_edge_to_unclustered_node_is_ignored(self) -> None:
        """An edge whose endpoint never got a level-0 cluster is skipped.

        Only weight for edges between two clustered endpoints should count;
        an edge naming a node absent from the clustering output must not
        raise or contribute weight anywhere.
        """
        ids = [str(uuid4()) for _ in range(3)]
        a, b, unclustered = ids
        mock_clusters = [
            HC(node=a, cluster=0, parent_cluster=None, level=0, is_final_cluster=True),
            HC(node=b, cluster=0, parent_cluster=None, level=0, is_final_cluster=True),
        ]
        edges = [(a, b, 2.0, "KNOWS"), (a, unclustered, 9.0, "KNOWS")]
        with patch.dict(
            "sys.modules", {"graspologic_native": _mock_leiden(mock_clusters)}
        ):
            comms = compute_communities(edges)
            assert len(comms) == 1
            assert comms[0].internal_weight == 2.0

    def test_missing_extra(self) -> None:
        """Missing graspologic-native raises CommunityDetectionMissingExtraError."""
        with (
            patch.dict("sys.modules", {"graspologic_native": None}),
            pytest.raises(CommunityDetectionMissingExtraError),
        ):
            compute_communities([])
