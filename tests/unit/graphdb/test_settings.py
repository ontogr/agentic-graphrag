"""Tests for Neo4jSettings in agrag.graphdb.settings.

Covers the validator rejecting a plaintext bolt/neo4j scheme against a
non-local host while allowing plaintext localhost and encrypted remote
schemes (neo4j+s, neo4j+ssc).
"""

import pytest

from agrag.graphdb.settings import Neo4jSettings


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
