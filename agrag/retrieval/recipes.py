"""Named, data-only configurations of what SearchEngine runs."""

from typing import Literal

from pydantic import BaseModel


class Recipe(BaseModel):
    """A named configuration of what SearchEngine runs for a query.

    Attributes:
        methods: Which retrieval methods to fan out to
            concurrently, by name.
        bfs: Whether to run a BFS expansion after methods
            complete, seeded from their entity results. BFS
            needs seed ids methods produce, so it cannot run
            concurrently with them.
        bfs_depth: Traversal depth when bfs is true. None uses
            RetrievalSettings.traversal_depth.
        reranker: The optional Rerank pass to run after Fusion.
            None skips reranking.
        limit: The maximum number of results SearchEngine
            returns.
    """

    methods: list[str]
    bfs: bool = False
    bfs_depth: int | None = None
    reranker: Literal["cross_encoder", "node_distance"] | None = None
    limit: int = 10


# Preset recipes for common search patterns.
ENTITY = Recipe(methods=["entity"], limit=10)
CHUNK = Recipe(methods=["chunk"], limit=10)
HYBRID = Recipe(methods=["entity", "chunk"], limit=10)
HYBRID_RERANKED = Recipe(
    methods=["entity", "chunk"], reranker="cross_encoder", limit=10
)
GRAPH_EXPAND = Recipe(methods=["entity"], bfs=True, limit=20)
