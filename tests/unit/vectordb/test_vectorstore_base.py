"""Tests for the VectorStore base contract helpers."""

import pytest

from agrag.vectordb.base import require_positive_batch_size


class TestRequirePositiveBatchSize:
    """require_positive_batch_size guards the upsert batching contract."""

    @pytest.mark.parametrize("batch_size", [1, 256, 10_000])
    def test_accepts_positive_values(self, batch_size: int) -> None:
        """A positive batch size passes without error."""
        require_positive_batch_size(batch_size)

    def test_rejects_zero(self) -> None:
        """Zero would raise from range() itself; reject it with a clear error."""
        with pytest.raises(ValueError):
            require_positive_batch_size(0)

    def test_rejects_negative(self) -> None:
        """A negative value would silently skip every record via range()."""
        with pytest.raises(ValueError):
            require_positive_batch_size(-1)
