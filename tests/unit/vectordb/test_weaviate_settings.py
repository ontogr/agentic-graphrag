"""Weaviate naming and transport validation without connecting to a server."""

import pytest

from agrag.common.data_models.vector_record import VectorKind
from agrag.vectordb.weaviate import WeaviateSettings, WeaviateVectorStore


class TestWeaviateSettings:
    """Reject ambiguous collection prefixes and unsafe remote transports."""

    @pytest.mark.parametrize("prefix", ["Graph", "1graph", "graph-name", ""])
    def test_rejects_ambiguous_or_invalid_prefix(self, prefix: str) -> None:
        """Uppercase first letters would alias a lowercase prefix in Weaviate."""
        with pytest.raises(ValueError):
            WeaviateSettings(collection_prefix=prefix, _env_file=None)

    def test_maps_collection_names(self) -> None:
        """Only the first letter changes when naming a collection."""
        store = WeaviateVectorStore(
            settings=WeaviateSettings(collection_prefix="graph_A", _env_file=None)
        )
        assert store.collection_name(VectorKind.CHUNK) == "Graph_A_chunks"
        assert store.collection_name(VectorKind.RESOLVED_ENTITY) == (
            "Graph_A_resolved_entities"
        )

    @pytest.mark.parametrize("require_tls", [False, True])
    def test_rejects_remote_plaintext_credentials(self, require_tls: bool) -> None:
        """A remote credential requires HTTPS regardless of the strict flag."""
        with pytest.raises(ValueError, match="unencrypted"):
            WeaviateSettings(
                collection_prefix="graph",
                url="http://example.com:8080",
                api_key="test-only-credential",
                require_tls=require_tls,
                _env_file=None,
            )

    def test_cloud_requires_https(self) -> None:
        """Cloud mode cannot silently upgrade an insecure URL."""
        with pytest.raises(ValueError, match="HTTPS"):
            WeaviateSettings(
                collection_prefix="graph",
                mode="cloud",
                url="http://example.com",
                _env_file=None,
            )
