"""Tests for Neo4j settings."""

import pytest

from agrag.graphdb.settings import Neo4jSettings


def test_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings read from NEO4J_ environment variables."""
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://example:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "alice")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")
    monkeypatch.setenv("NEO4J_DATABASE", "docs")
    s = Neo4jSettings()
    assert s.uri == "neo4j+s://example:7687"
    assert s.username == "alice"
    assert s.password.get_secret_value() == "secret"
    assert s.database == "docs"


def test_defaults() -> None:
    """Sensible defaults apply when no environment is set."""
    s = Neo4jSettings()
    assert s.uri.startswith("bolt://")
    assert s.username == "neo4j"
    assert s.database == "neo4j"
    assert s.max_connection_lifetime == 240


class TestEncryptedRemoteConnection:
    """A plaintext URI to a non-local host is rejected."""

    def test_localhost_plaintext_is_allowed(self) -> None:
        """The local dev default, plaintext against localhost, is fine."""
        Neo4jSettings(uri="bolt://localhost:7687")

    def test_remote_encrypted_is_allowed(self) -> None:
        """A remote host is fine once the scheme is encrypted."""
        Neo4jSettings(uri="neo4j+s://example.databases.neo4j.io:7687")

    def test_remote_plaintext_raises(self) -> None:
        """A remote host over a plaintext scheme raises.

        Neo4j always authenticates with a password, so a plaintext bolt://
        or neo4j:// scheme to a non-local host always sends it in the clear.
        """
        with pytest.raises(ValueError, match="unencrypted"):
            Neo4jSettings(uri="bolt://example.com:7687")

    def test_remote_plaintext_neo4j_scheme_raises(self) -> None:
        """The neo4j:// routing scheme is plaintext too, unless +s/+ssc."""
        with pytest.raises(ValueError, match="unencrypted"):
            Neo4jSettings(uri="neo4j://example.com:7687")
