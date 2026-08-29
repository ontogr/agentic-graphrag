"""Settings for the Neo4j graph-store backend."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    """

    model_config = SettingsConfigDict(
        env_prefix="NEO4J_", env_file=".env", extra="ignore"
    )

    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: SecretStr = SecretStr("neo4j")
    database: str = "neo4j"
    max_connection_lifetime: int = 240
