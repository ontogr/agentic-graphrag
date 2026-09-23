"""Average-linkage clustering over entity distance matrices."""

from uuid import UUID

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform


def average_linkage_clusters(
    ids: list[UUID], distances: np.ndarray, *, cut_distance: float
) -> list[list[UUID]]:
    """Group ids into average-linkage clusters cut at a fixed distance.

    Average linkage measures cluster distance as the mean of all member
    pair distances, so one close pair cannot drag distant members into a
    cluster the way single linkage chaining does.

    Args:
        ids: Entity identifiers, one per row of ``distances``.
        distances: Square symmetric ``(n, n)`` distance matrix with a zero
            diagonal.
        cut_distance: Maximum average-linkage distance within a cluster.
            Callers pass ``1 - hard_merge_threshold``.

    Returns:
        One id list per cluster, in first-appearance order.
    """
    if len(ids) <= 1:
        return [list(ids)] if ids else []
    matrix = linkage(squareform(distances), method="average")
    labels = fcluster(matrix, t=cut_distance, criterion="distance")
    grouped: dict[int, list[UUID]] = {}
    for label, id_ in zip(labels, ids, strict=True):
        grouped.setdefault(int(label), []).append(id_)
    return list(grouped.values())
