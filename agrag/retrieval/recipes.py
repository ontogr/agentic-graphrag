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
        min_score: Results the reranker scores below this are dropped.
            None uses RetrievalSettings.reranker_min_score, so a
            caller can tighten or disable the floor for one call
            without touching the configured default.
        limit: The maximum number of results SearchEngine
            returns.
        community_expand: Whether to fetch and fuse in overlapping
            communities' reports after BFS.
        community_top_k: How many communities community_context
            returns, and (when reranker is cross_encoder) how many
            are reserved a slot after rerank.
    """

    methods: list[str]
    bfs: bool = False
    bfs_depth: int | None = None
    reranker: Literal["cross_encoder", "node_distance"] | None = None
    min_score: float | None = None
    limit: int = 10
    community_expand: bool = False
    community_top_k: int = 3


# Preset recipes for common search patterns.
ENTITY = Recipe(methods=["entity"], limit=10)
CHUNK = Recipe(methods=["chunk"], limit=10)
HYBRID = Recipe(methods=["entity", "chunk"], limit=10)
HYBRID_RERANKED = Recipe(
    methods=["entity", "chunk"],
    reranker="cross_encoder",
    limit=10,
    community_expand=True,
)
GRAPH_EXPAND = Recipe(methods=["entity"], bfs=True, limit=20, community_expand=True)
THEMATIC = Recipe(methods=["community"], limit=5)
TEXT2CYPHER = Recipe(methods=["text2cypher"], limit=10)
