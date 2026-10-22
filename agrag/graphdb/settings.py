"""Settings for the graph-store backends."""

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from agrag.common.validation import require_encrypted_remote_connection


class Neo4jSettings(BaseSettings):
    """Neo4j connection configuration.

    Attributes:
        uri: The Bolt connection URI, including scheme (``neo4j+s://`` for
            Aura). Env: ``NEO4J_URI``.
        username: The database username. Env: ``NEO4J_USERNAME``.
        password: The database password. Env: ``NEO4J_PASSWORD``.
        database: The target database name. Env: ``NEO4J_DATABASE``.
        max_connection_lifetime: The maximum seconds a pooled connection
            lives, kept well below Aura's roughly five-minute idle timeout.
            Env: ``NEO4J_MAX_CONNECTION_LIFETIME``.

    Raises:
        ValueError: ``uri`` is plaintext (``bolt://`` or ``neo4j://``) and
            points at a non-local host. Neo4j always authenticates with a
            password, so a plaintext scheme always sends it in the clear; use
            ``neo4j+s://`` (or ``bolt+s://``) for a remote instance.
    """

    model_config = SettingsConfigDict(
        env_prefix="NEO4J_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: SecretStr = SecretStr("neo4j")
    database: str = "neo4j"
    max_connection_lifetime: int = 240

    @model_validator(mode="after")
    def _require_encrypted_remote_connection(self) -> "Neo4jSettings":
        """Reject a plaintext URI to a non-local host.

        Unlike the vector-store backends, Neo4j always authenticates with a
        password (there is no unauthenticated mode), so this checks scheme
        and host only.
        """
        require_encrypted_remote_connection(
            url=self.uri,
            has_credential=True,
            encrypted_schemes=frozenset({"bolt+s", "bolt+ssc", "neo4j+s", "neo4j+ssc"}),
        )
        return self


class FalkorDBSettings(BaseSettings):
    """FalkorDB connection configuration.

    Attributes:
        url: The Redis connection URL, including scheme (``rediss://`` for
            TLS). Env: ``FALKORDB_URL``.
        password: The Redis password, or None for a server without one.
            Env: ``FALKORDB_PASSWORD``.
        graph: The name of the graph (the Redis key) that holds all data.
            Env: ``FALKORDB_GRAPH``.
        max_connections: The size of the connection pool. Env:
            ``FALKORDB_MAX_CONNECTIONS``.

    Raises:
        ValueError: ``url`` is plaintext (``redis://``) and points at a
            non-local host while ``password`` is set. Use ``rediss://`` for a
            remote instance.
    """

    model_config = SettingsConfigDict(
        env_prefix="FALKORDB_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    url: str = "redis://localhost:6379"
    password: SecretStr | None = None
    graph: str = "agrag"
    max_connections: int = 16

    @model_validator(mode="after")
    def _require_encrypted_remote_connection(self) -> "FalkorDBSettings":
        """Reject a plaintext URL to a non-local host when a password is set."""
        require_encrypted_remote_connection(
            url=self.url,
            has_credential=self.password is not None,
            encrypted_schemes=frozenset({"rediss"}),
        )
        return self
