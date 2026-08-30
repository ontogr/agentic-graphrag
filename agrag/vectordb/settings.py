"""Settings for vector-store backends."""

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from agrag.common.validation import require_encrypted_remote_connection


class QdrantSettings(BaseSettings):
    """Qdrant connection configuration.

    Attributes:
        url: The Qdrant endpoint URL. Env: ``QDRANT_URL``.
        api_key: The Qdrant API key. Env: ``QDRANT_API_KEY``.

    Raises:
        ValueError: ``url`` is plaintext (``http``), points at a non-local
            host, and ``api_key`` is set. Use ``https`` for a remote Qdrant
            instance.
    """

    model_config = SettingsConfigDict(
        env_prefix="QDRANT_", env_file=".env", extra="ignore"
    )

    url: str = "http://localhost:6333"
    api_key: str = ""

    @model_validator(mode="after")
    def _require_encrypted_remote_connection(self) -> "QdrantSettings":
        """Reject a plaintext URL sending a credential to a non-local host."""
        require_encrypted_remote_connection(
            url=self.url,
            has_credential=bool(self.api_key),
            encrypted_schemes=frozenset({"https"}),
        )
        return self


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

    Raises:
        ValueError: ``url`` is plaintext (``http``), points at a non-local
            host, and ``api_key`` is set. Use ``https`` for a remote Weaviate
            instance.
    """

    model_config = SettingsConfigDict(
        env_prefix="WEAVIATE_", env_file=".env", extra="ignore"
    )

    mode: Literal["cloud", "custom"] = "custom"
    url: str = "http://localhost:8080"
    api_key: str = ""
    grpc_port: int = 50051

    @model_validator(mode="after")
    def _require_encrypted_remote_connection(self) -> "WeaviateSettings":
        """Reject a plaintext URL sending a credential to a non-local host."""
        require_encrypted_remote_connection(
            url=self.url,
            has_credential=bool(self.api_key),
            encrypted_schemes=frozenset({"https"}),
        )
        return self


class MilvusSettings(BaseSettings):
    """Milvus connection configuration.

    Attributes:
        uri: The Milvus endpoint URI. Env: ``MILVUS_URI``.
        token: The Milvus auth token. Empty string for an unauthenticated
            instance. Env: ``MILVUS_TOKEN``.

    Raises:
        ValueError: ``uri`` is plaintext (``http``), points at a non-local
            host, and ``token`` is set. Use ``https`` for a remote Milvus
            instance.
    """

    model_config = SettingsConfigDict(
        env_prefix="MILVUS_", env_file=".env", extra="ignore"
    )

    uri: str = "http://localhost:19530"
    token: str = ""

    @model_validator(mode="after")
    def _require_encrypted_remote_connection(self) -> "MilvusSettings":
        """Reject a plaintext URI sending a credential to a non-local host."""
        require_encrypted_remote_connection(
            url=self.uri,
            has_credential=bool(self.token),
            encrypted_schemes=frozenset({"https"}),
        )
        return self
