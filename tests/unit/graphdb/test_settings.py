"""Tests for Neo4jSettings in agrag.graphdb.settings.

Covers the validator rejecting a plaintext bolt/neo4j scheme against a
non-local host. Also covers validation errors leaving out the
configured password and every other value read from ``.env``.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from agrag.graphdb.settings import Neo4jSettings


class TestEncryptedRemoteConnection:
    """A plaintext URI to a non-local host is rejected."""

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


class TestSecretsStayOutOfErrors:
    """A validation error message never shows a configured secret."""

    def test_error_omits_the_password(self) -> None:
        """The message leaves out the password passed to the settings."""
        with pytest.raises(ValidationError) as exc_info:
            Neo4jSettings(uri="bolt://example.com:7687", password="pw-8a1f")

        assert "pw-8a1f" not in str(exc_info.value)

    def test_error_omits_other_secrets_in_env_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The message leaves out secrets that .env holds for other components."""
        (tmp_path / ".env").write_text("LLM_API_KEY=key-5c2e\n")
        monkeypatch.chdir(tmp_path)

        with pytest.raises(ValidationError) as exc_info:
            Neo4jSettings(uri="bolt://example.com:7687")

        assert "key-5c2e" not in str(exc_info.value)
