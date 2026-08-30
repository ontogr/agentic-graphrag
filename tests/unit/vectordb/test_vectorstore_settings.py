"""Tests for vector-store backend settings."""

import pytest

from agrag.vectordb.settings import MilvusSettings, QdrantSettings, WeaviateSettings


class TestQdrantEncryptedRemoteConnection:
    """A plaintext URL to a non-local host carrying an api_key is rejected."""

    def test_localhost_plaintext_with_credential_is_allowed(self) -> None:
        """The local dev default, plaintext against localhost, is fine."""
        QdrantSettings(url="http://localhost:6333", api_key="k")

    def test_remote_plaintext_without_credential_is_allowed(self) -> None:
        """No credential means nothing secret travels in the clear."""
        QdrantSettings(url="http://example.com:6333")

    def test_remote_encrypted_with_credential_is_allowed(self) -> None:
        """A remote host is fine once the scheme is encrypted."""
        QdrantSettings(url="https://example.com:6333", api_key="k")

    def test_remote_plaintext_with_credential_raises(self) -> None:
        """A remote host, plaintext scheme, and a credential together raise."""
        with pytest.raises(ValueError, match="unencrypted"):
            QdrantSettings(url="http://example.com:6333", api_key="k")


class TestWeaviateDefaults:
    """Defaults must pair a mode with a URL that mode can actually reach."""

    def test_default_mode_matches_default_local_url(self) -> None:
        """The default URL is a local Docker host, so the default mode must be custom.

        Regression guard: mode="cloud" paired with the localhost default URL
        sent every out-of-the-box store through the Weaviate Cloud
        connector against a local instance, which cannot connect.
        """
        assert WeaviateSettings().mode == "custom"


class TestWeaviateEncryptedRemoteConnection:
    """A plaintext URL to a non-local host carrying an api_key is rejected."""

    def test_localhost_plaintext_with_credential_is_allowed(self) -> None:
        """The local dev default, plaintext against localhost, is fine."""
        WeaviateSettings(mode="custom", url="http://localhost:8080", api_key="k")

    def test_remote_plaintext_with_credential_raises(self) -> None:
        """A remote host, plaintext scheme, and a credential together raise."""
        with pytest.raises(ValueError, match="unencrypted"):
            WeaviateSettings(mode="custom", url="http://example.com:8080", api_key="k")


class TestMilvusEncryptedRemoteConnection:
    """A plaintext URI to a non-local host carrying a token is rejected."""

    def test_localhost_plaintext_with_credential_is_allowed(self) -> None:
        """The local dev default, plaintext against localhost, is fine."""
        MilvusSettings(uri="http://localhost:19530", token="t")

    def test_remote_plaintext_with_credential_raises(self) -> None:
        """A remote host, plaintext scheme, and a credential together raise."""
        with pytest.raises(ValueError, match="unencrypted"):
            MilvusSettings(uri="http://example.com:19530", token="t")
