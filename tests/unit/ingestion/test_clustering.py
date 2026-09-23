"""Tests for average-linkage clustering over entity distances.

Covers tight clusters merging into one group, average linkage resisting
the chaining that would pull distant members together through a shared
neighbor, loose populations staying split at the cut distance, and the
empty and singleton edge cases.
"""

from uuid import UUID, uuid4

import numpy as np

from agrag.ingestion._clustering import average_linkage_clusters


def _distances(entries: dict[tuple[int, int], float], count: int) -> np.ndarray:
    """Build a square symmetric distance matrix, defaulting to far apart."""
    matrix = np.ones((count, count))
    for index in range(count):
        matrix[index, index] = 0.0
    for (left, right), distance in entries.items():
        matrix[left, right] = distance
        matrix[right, left] = distance
    return matrix


def _group_of(groups: list[list[UUID]], id_: UUID) -> list[UUID]:
    """Return the group containing an id."""
    return next(group for group in groups if id_ in group)


class TestAverageLinkageClusters:
    """average_linkage_clusters cuts average-linkage groups at a distance."""

    def test_merges_tight_cluster(self) -> None:
        """Three mutually close ids form one group."""
        ids = [uuid4(), uuid4(), uuid4()]
        distances = _distances({(0, 1): 0.01, (1, 2): 0.01, (0, 2): 0.02}, 3)

        assert average_linkage_clusters(ids, distances, cut_distance=0.05) == [ids]

    def test_chaining_does_not_merge_distant_members(self) -> None:
        """A-B and B-C close but A-C far keeps A and C in separate groups."""
        first, middle, last = uuid4(), uuid4(), uuid4()
        distances = _distances({(0, 1): 0.01, (1, 2): 0.01, (0, 2): 0.5}, 3)

        groups = average_linkage_clusters(
            [first, middle, last], distances, cut_distance=0.05
        )

        assert _group_of(groups, first) is not _group_of(groups, last)

    def test_loose_population_stays_split(self) -> None:
        """Every pair beyond the cut distance stays a singleton."""
        ids = [uuid4(), uuid4(), uuid4()]
        distances = _distances({}, 3)

        groups = average_linkage_clusters(ids, distances, cut_distance=0.05)

        assert {id_ for group in groups for id_ in group} == set(ids)
        assert all(len(group) == 1 for group in groups)

    def test_single_id_returns_singleton(self) -> None:
        """One id needs no linkage computation."""
        id_ = uuid4()

        assert average_linkage_clusters([id_], np.zeros((1, 1)), cut_distance=0.05) == [
            [id_]
        ]

    def test_empty_returns_empty(self) -> None:
        """No ids produce no groups."""
        assert average_linkage_clusters([], np.zeros((0, 0)), cut_distance=0.05) == []
