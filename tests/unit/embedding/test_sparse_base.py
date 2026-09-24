"""Tests for the SparseEmbedder base class.

Verifies the abstract base cannot be instantiated directly.
"""

import pytest

from agrag.embedding.sparse_base import SparseEmbedder


class TestSparseEmbedder:
    """SparseEmbedder is an abstract protocol with a document and query method."""

    def test_cannot_instantiate(self) -> None:
        """The base class cannot be constructed directly."""
        with pytest.raises(TypeError):
            SparseEmbedder()  # type: ignore[abstract]
