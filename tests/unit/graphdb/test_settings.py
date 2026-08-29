"""Tests for Neo4j settings."""

import pytest

from agrag.graphdb.settings import Neo4jSettings


def test_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings read from NEO4J_ environment variables."""
    monkeypatch.setenv("NEO4J_URI", "bolt://example:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "alice")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")
    monkeypatch.setenv("NEO4J_DATABASE", "docs")
    s = Neo4jSettings()
    assert s.uri == "bolt://example:7687"
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
