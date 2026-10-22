"""Tests for the shared vector collection-prefix validator."""

import pytest
from pydantic import TypeAdapter, ValidationError

from agrag.vectordb.settings import CollectionPrefix


class TestCollectionPrefix:
    """Collection prefixes follow the backend-independent naming contract."""

    @pytest.mark.parametrize("prefix", ["A", "a0", "Graph_Store_7", "A" + "x" * 40])
    def test_accepts_valid_prefixes(self, prefix: str) -> None:
        """A letter-led prefix of at most 41 safe characters is accepted."""
        assert TypeAdapter(CollectionPrefix).validate_python(prefix) == prefix

    @pytest.mark.parametrize(
        "prefix", ["", "7graphs", "_graphs", "graph-store", "a" * 42, "Gráph"]
    )
    def test_rejects_invalid_prefixes(self, prefix: str) -> None:
        """Empty, oversized, unsafe, and non-ASCII prefixes are rejected."""
        with pytest.raises(ValidationError):
            TypeAdapter(CollectionPrefix).validate_python(prefix)
