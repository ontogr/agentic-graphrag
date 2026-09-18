"""Small clustering primitives shared by entity-resolution phases."""

from uuid import UUID

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage


def average_linkage_clusters(
    ids: list[UUID], distances: np.ndarray, *, cut_distance: float
) -> list[list[UUID]]:
    """Cluster ids with average-linkage agglomerative clustering."""
    if len(ids) != len(distances):
        raise ValueError("distances must have one row per id")
    if len(ids) <= 1:
        return [ids.copy()] if ids else []
    matrix = np.asarray(distances, dtype=float)
    if matrix.shape != (len(ids), len(ids)):
        raise ValueError("distances must be a square matrix")
    condensed = matrix[np.triu_indices(len(ids), k=1)]
    labels = fcluster(
        linkage(condensed, method="average"), cut_distance, criterion="distance"
    )
    clusters: dict[int, list[UUID]] = {}
    for entity_id, cluster_id in zip(ids, labels, strict=True):
        clusters.setdefault(int(cluster_id), []).append(entity_id)
    return list(clusters.values())
