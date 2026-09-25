"""Tests for set_chunk_embedding_query in agrag.cypher.entities.

Covers rejecting an unsafe vector property name.
"""

import pytest

from agrag.cypher.entities import set_chunk_embedding_query


class TestSetChunkEmbeddingQuery:
    """set_chunk_embedding_query validates its vector property name."""

    def test_validates_property_name(self) -> None:
        """An unsafe property name raises."""
        with pytest.raises(ValueError):
            set_chunk_embedding_query("bad name")
