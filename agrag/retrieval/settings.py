"""Env-backed configuration for retrieval methods and fusion."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class RetrievalSettings(BaseSettings):
    """Configuration for retrieval methods and fusion.

    Attributes:
        entity_labels: The graph labels native entity search runs
            against, one vector index each. These are the schema's
            entity labels. Only read when the caller passes no label
            filter.
        node_distance_seed_top_k: How many of the highest-ranked
            entity hits seed the node-distance reranker. Candidates
            are ordered by graph distance to those seeds.
        entity_top_k: Results requested per entity search call.
        resolved_entity_top_k: Results requested per resolved-entity search
            call.
        chunk_top_k: Results requested per chunk search call.
        traversal_depth: Maximum BFS hops from a seed entity.
        traversal_limit: Maximum nodes a BFS expansion can return.
        rrf_k: The RRF constant controlling how much rank position
            matters.
        reranker_min_score: Results scoring below this after rerank
            are dropped. None disables the threshold.
        text2cypher_timeout_seconds: Server-side transaction timeout
            applied to generated read queries. The database terminates
            a generated query that runs longer, so a pathological
            query cannot hold server resources indefinitely. None
            uses the server's default timeout.
        text2cypher_max_rows: Maximum rows a generated read query may
            return. Appended as a LIMIT clause when the generated
            query declares none of its own.
        cross_encoder_model: The sentence-transformers CrossEncoder model
            used for cross_encoder reranking. Env:
            RETRIEVAL_CROSS_ENCODER_MODEL.
        community_top_k: Results requested per community search call when
            the caller passes no explicit limit. It plays the same role
            entity_top_k and chunk_top_k play for their retrievers. It is
            distinct from Recipe.community_top_k (enrichment budget and
            reserved slice size). Same name, different class, different job.

    Env prefix: ``RETRIEVAL_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="RETRIEVAL_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    entity_labels: list[str] = []
    node_distance_seed_top_k: int = 3
    entity_top_k: int = 10
    resolved_entity_top_k: int = 10
    chunk_top_k: int = 10
    traversal_depth: int = 2
    traversal_limit: int = 50
    rrf_k: int = 60
    reranker_min_score: float | None = None
    text2cypher_timeout_seconds: float | None = 10.0
    text2cypher_max_rows: int = 1000
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    community_top_k: int = 5
