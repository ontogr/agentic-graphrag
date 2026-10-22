"""Qdrant credentials must not travel over a remote plaintext connection."""

import pytest
from pydantic import SecretStr, ValidationError

from agrag.vectordb.qdrant import QdrantSettings


class TestQdrantSettings:
    """TLS is required for remote credentials and explicit encryption requests."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://user:private-password@qdrant.example.com",
            "https://qdrant.example.com?token=private-password",
            "http://qdrant.example.com#private-password",
            "file:///private-password",
        ],
    )
    def test_rejects_unsafe_urls_without_exposing_secrets(self, url: str) -> None:
        """Credentials belong in the secret field, not in connection URLs."""
        with pytest.raises(ValidationError) as error:
            QdrantSettings(_env_file=None, url=url, collection_prefix="unit")
        assert "private-password" not in str(error.value)

    @pytest.mark.parametrize(
        ("url", "credential", "require_tls", "valid"),
        [
            ("http://localhost:6333", True, False, True),
            ("http://qdrant.example.com", True, False, False),
            ("https://qdrant.example.com", True, False, True),
            ("http://qdrant.example.com", False, False, True),
            ("http://localhost:6333", False, True, True),
            ("http://qdrant.example.com", False, True, False),
        ],
    )
    def test_connection_security(
        self, url: str, credential: bool, require_tls: bool, valid: bool
    ) -> None:
        """Connection validation covers credential and explicit TLS policies."""
        api_key = SecretStr("unit-test-key") if credential else None
        if valid:
            settings = QdrantSettings(
                _env_file=None,
                url=url,
                api_key=api_key,
                require_tls=require_tls,
                collection_prefix="unit",
            )
            assert settings.url == url
        else:
            with pytest.raises(ValidationError):
                QdrantSettings(
                    _env_file=None,
                    url=url,
                    api_key=api_key,
                    require_tls=require_tls,
                    collection_prefix="unit",
                )
