"""Settings for vector-store backends."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class QdrantSettings(BaseSettings):
    """Qdrant connection configuration.

    Attributes:
        url: The Qdrant endpoint URL. Env: ``QDRANT_URL``.
        api_key: The Qdrant API key. Env: ``QDRANT_API_KEY``.
    """

    model_config = SettingsConfigDict(
        env_prefix="QDRANT_", env_file=".env", extra="ignore"
    )

    url: str = "http://localhost:6333"
    api_key: str = ""


class WeaviateSettings(BaseSettings):
    """Weaviate connection configuration.

    Attributes:
        mode: ``"cloud"`` connects to Weaviate Cloud. ``"custom"`` connects to
            a self-hosted instance (used by integration tests against the local
            Docker Compose instance) — an explicit field, not inferred from the
            URL, since inference caused real connection bugs in surveyed
            reference implementations. Env: ``WEAVIATE_MODE``.
        url: The Weaviate endpoint URL. For ``"cloud"``, the cluster URL. For
            ``"custom"``, the full host URL. Env: ``WEAVIATE_URL``.
        api_key: The Weaviate API key. Env: ``WEAVIATE_API_KEY``.
        grpc_port: The gRPC port, used by ``"custom"`` mode only (``"cloud"``
            mode infers it). Env: ``WEAVIATE_GRPC_PORT``.
    """

    model_config = SettingsConfigDict(
        env_prefix="WEAVIATE_", env_file=".env", extra="ignore"
    )

    mode: Literal["cloud", "custom"] = "cloud"
    url: str = "http://localhost:8080"
    api_key: str = ""
    grpc_port: int = 50051


class MilvusSettings(BaseSettings):
    """Milvus connection configuration.

    Attributes:
        uri: The Milvus endpoint URI. Env: ``MILVUS_URI``.
        token: The Milvus auth token. Empty string for an unauthenticated
            instance. Env: ``MILVUS_TOKEN``.
    """

    model_config = SettingsConfigDict(
        env_prefix="MILVUS_", env_file=".env", extra="ignore"
    )

    uri: str = "http://localhost:19530"
    token: str = ""
