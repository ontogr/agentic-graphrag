"""Env-backed configuration for evidence search and rerank."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RetrievalSettings(BaseSettings):
    """Configuration for evidence search fusion and rerank.

    Attributes:
        rrf_k: The RRF constant controlling how much rank position
            matters.
        cross_encoder_model: The sentence-transformers CrossEncoder model
            used for hybrid rerank. Env:
            RETRIEVAL_CROSS_ENCODER_MODEL.
        rerank_enabled: Whether hybrid search reorders its top hits with the
            cross-encoder. Env: ``RETRIEVAL_RERANK_ENABLED``.
        rerank_candidates: How many of the top fused hits the cross-encoder
            scores. Env: ``RETRIEVAL_RERANK_CANDIDATES``.
        rerank_timeout_seconds: The most seconds one rerank call may take. A
            timed-out rerank keeps the fused order. Env:
            ``RETRIEVAL_RERANK_TIMEOUT_SECONDS``.
        hybrid_alpha: Dense weight for hybrid searches on an external vector
            store. Env: ``RETRIEVAL_HYBRID_ALPHA``.

    Env prefix: ``RETRIEVAL_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="RETRIEVAL_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    rrf_k: int = 60
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_enabled: bool = True
    rerank_candidates: int = Field(default=30, ge=1)
    rerank_timeout_seconds: float = Field(default=5.0, gt=0)
    hybrid_alpha: float = Field(default=0.5, ge=0, le=1)
