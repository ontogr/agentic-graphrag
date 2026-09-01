"""Env-backed configuration for retrieval methods and fusion."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class RetrievalSettings(BaseSettings):
    """Configuration for retrieval methods and fusion.

    Attributes:
        entity_collection: The VectorStore collection name for entity
            search. Only read when a VectorStore is configured on
            SearchEngine; ignored on the GraphStore-native path.
        chunk_collection: The VectorStore collection name for chunk
            search. Same condition as entity_collection.
        entity_labels: The graph labels native entity search runs
            against, one vector index each. These are the schema's
            entity labels, never a VectorStore collection name. Only
            read when no VectorStore is configured and the caller
            passes no label filter.
        node_distance_seed_top_k: How many of the highest-ranked
            entity hits seed the node-distance reranker. Candidates
            are ordered by graph distance to those seeds.
        entity_top_k: Results requested per entity search call.
        chunk_top_k: Results requested per chunk search call.
        hybrid_alpha: Dense-versus-keyword blend for hybrid search,
            0 to 1. Only meaningful on the VectorStore path;
            GraphStore-native search is dense-only and ignores this.
        traversal_depth: Maximum BFS hops from a seed entity.
        traversal_limit: Maximum nodes a BFS expansion can return.
        rrf_k: The RRF constant controlling how much rank position
            matters.
        reranker_min_score: Results scoring below this after rerank
            are dropped. None disables the threshold.
        text2cypher_max_retries: Maximum retry attempts for a
            text2cypher generation that produces invalid Cypher.
        text2cypher_timeout_seconds: Server-side transaction timeout
            applied to generated read queries. The database terminates
            a generated query that runs longer, so a pathological
            query cannot hold server resources indefinitely. None
            uses the server's default timeout.
        text2cypher_max_rows: Maximum rows a generated read query may
            return. Appended as a LIMIT clause when the generated
            query declares none of its own.

    Env prefix: ``RETRIEVAL_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="RETRIEVAL_", env_file=".env", extra="ignore"
    )

    entity_collection: str = "agrag_entities"
    chunk_collection: str = "agrag_chunks"
    entity_labels: list[str] = []
    node_distance_seed_top_k: int = 3
    entity_top_k: int = 10
    chunk_top_k: int = 10
    hybrid_alpha: float = 0.5
    traversal_depth: int = 2
    traversal_limit: int = 50
    rrf_k: int = 60
    reranker_min_score: float | None = None
    text2cypher_max_retries: int = 3
    text2cypher_timeout_seconds: float | None = 10.0
    text2cypher_max_rows: int = 1000
