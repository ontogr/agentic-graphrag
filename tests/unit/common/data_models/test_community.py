"""Tests for the Community domain model's field validation."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from agrag.common.data_models.community import Community


class TestCommunity:
    """Community rejects out-of-range ratings and negative weights."""

    @pytest.mark.parametrize("rating", [-0.1, 10.1])
    def test_rating_out_of_range_rejected(self, rating: float) -> None:
        """Constructing a Community with rating outside 0-10 raises."""
        with pytest.raises(ValidationError):
            Community(
                id=uuid4(), title="T", summary="S", rating=rating, rating_explanation=""
            )

    def test_negative_internal_weight_rejected(self) -> None:
        """Constructing a Community with a negative weight raises."""
        with pytest.raises(ValidationError):
            Community(
                id=uuid4(),
                title="T",
                summary="S",
                rating=1,
                rating_explanation="",
                internal_weight=-1,
            )
