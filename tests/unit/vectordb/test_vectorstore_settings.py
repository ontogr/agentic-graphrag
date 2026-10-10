"""Tests for the TLS-enforcement validators on vector-store settings.

Covers QdrantSettings, WeaviateSettings, and MilvusSettings each rejecting a
plaintext URL or URI to a non-local host when a credential (api_key or
token) is present, or when ``require_tls=True`` is set even without a
credential. Also covers validation errors leaving out the configured
credential.
"""

import pytest
from pydantic import ValidationError

from agrag.vectordb.settings import MilvusSettings, QdrantSettings, WeaviateSettings


class TestQdrantEncryptedRemoteConnection:
    """A plaintext URL to a non-local host carrying an api_key is rejected."""

    def test_remote_plaintext_with_credential_raises(self) -> None:
        """A remote host, plaintext scheme, and a credential together raise."""
        with pytest.raises(ValueError, match="unencrypted"):
            QdrantSettings(url="http://example.com:6333", api_key="k")

    def test_require_tls_rejects_remote_plaintext_without_credential(self) -> None:
        """require_tls=True rejects a remote plaintext URL even with no api_key."""
        with pytest.raises(ValueError, match="unencrypted"):
            QdrantSettings(url="http://example.com:6333", require_tls=True)


class TestWeaviateEncryptedRemoteConnection:
    """A plaintext URL to a non-local host carrying an api_key is rejected."""

    def test_remote_plaintext_with_credential_raises(self) -> None:
        """A remote host, plaintext scheme, and a credential together raise."""
        with pytest.raises(ValueError, match="unencrypted"):
            WeaviateSettings(mode="custom", url="http://example.com:8080", api_key="k")

    def test_require_tls_rejects_remote_plaintext_without_credential(self) -> None:
        """require_tls=True rejects a remote plaintext URL even with no api_key."""
        with pytest.raises(ValueError, match="unencrypted"):
            WeaviateSettings(
                mode="custom", url="http://example.com:8080", require_tls=True
            )


class TestMilvusEncryptedRemoteConnection:
    """A plaintext URI to a non-local host carrying a token is rejected."""

    def test_remote_plaintext_with_credential_raises(self) -> None:
        """A remote host, plaintext scheme, and a credential together raise."""
        with pytest.raises(ValueError, match="unencrypted"):
            MilvusSettings(uri="http://example.com:19530", token="t")

    def test_require_tls_rejects_remote_plaintext_without_credential(self) -> None:
        """require_tls=True rejects a remote plaintext URI even with no token."""
        with pytest.raises(ValueError, match="unencrypted"):
            MilvusSettings(uri="http://example.com:19530", require_tls=True)


@pytest.mark.parametrize(
    ("settings_class", "fields"),
    [
        (QdrantSettings, {"url": "http://example.com", "api_key": "cred-9d4b"}),
        (WeaviateSettings, {"url": "http://example.com", "api_key": "cred-9d4b"}),
        (MilvusSettings, {"uri": "http://example.com", "token": "cred-9d4b"}),
    ],
)
def test_validation_error_omits_the_credential(
    settings_class: type[QdrantSettings | WeaviateSettings | MilvusSettings],
    fields: dict[str, str],
) -> None:
    """The message leaves out the api_key or token passed to the settings."""
    with pytest.raises(ValidationError) as exc_info:
        settings_class(**fields)

    assert "cred-9d4b" not in str(exc_info.value)
