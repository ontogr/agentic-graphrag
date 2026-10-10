"""Tests for page provenance: page numbers, box order and page order."""

import pytest
from pydantic import ValidationError

from agrag.common.data_models.provenance import BoundingBox, PageProvenance, PageSpan


_BOX = BoundingBox(x0=0, y0=0, x1=1, y1=1)


class TestPageProvenance:
    """A page provenance is valid only when its spans are."""

    @pytest.mark.parametrize(
        ("spans", "message"),
        [
            pytest.param(
                [PageSpan(page_no=0, bbox=_BOX)],
                "must be >= 1",
                id="page-below-one",
            ),
            pytest.param(
                [PageSpan(page_no=1, bbox=BoundingBox(x0=2, y0=0, x1=1, y1=1))],
                "x0 <= x1",
                id="box-x-reversed",
            ),
            pytest.param(
                [PageSpan(page_no=2, bbox=_BOX), PageSpan(page_no=1, bbox=_BOX)],
                "out of order",
                id="pages-reversed",
            ),
        ],
    )
    def test_rejects_invalid_spans(self, spans: list[PageSpan], message: str) -> None:
        """Each rule rejects its own bad span."""
        with pytest.raises(ValidationError, match=message):
            PageProvenance(page_spans=spans)
