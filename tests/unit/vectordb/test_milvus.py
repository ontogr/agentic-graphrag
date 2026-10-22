"""Milvus label expressions preserve literal strings, including escape characters."""

import pytest
from pydantic import ValidationError

from agrag.vectordb.milvus import MilvusSettings, _labels_filter


class TestMilvusLabels:
    """Label values cannot introduce operators or terminate quoted strings."""

    @pytest.mark.parametrize(
        ("labels", "expected"),
        [
            (None, ""),
            ([], "id in []"),
            (["Person", "Animal"], 'array_contains_any(labels, ["Person", "Animal"])'),
            (['a"b'], 'array_contains_any(labels, ["a\\"b"])'),
            (["a\\b"], 'array_contains_any(labels, ["a\\\\b"])'),
            (["line\nbreak"], 'array_contains_any(labels, ["line\\nbreak"])'),
            (["é"], 'array_contains_any(labels, ["é"])'),
            (
                ['") or id != "'],
                'array_contains_any(labels, ["\\") or id != \\""])',
            ),
        ],
    )
    def test_preserves_literal_label_values(
        self, labels: list[str] | None, expected: str
    ) -> None:
        """The only interpolated values are escaped string literals."""
        assert _labels_filter(labels) == expected


class TestMilvusSettings:
    """Milvus settings reject plaintext remote credentials without exposing them."""

    def test_remote_token_is_not_in_error(self) -> None:
        """Validation output omits both token fields and other env settings."""
        token = "test-token-not-a-real-credential"
        with pytest.raises(ValidationError) as error:
            MilvusSettings(
                _env_file=None,
                uri="http://milvus.example.org:19530",
                token=token,
                collection_prefix="test",
            )
        assert "unencrypted" in str(error.value)
        assert token not in str(error.value)

    def test_require_tls_rejects_remote_without_token(self) -> None:
        """Strict TLS applies even when the remote endpoint has no credential."""
        with pytest.raises(ValidationError, match="encryption is required"):
            MilvusSettings(
                _env_file=None,
                uri="http://milvus.example.org:19530",
                token=None,
                require_tls=True,
                collection_prefix="test",
            )
