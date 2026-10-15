"""Shared assertions for VectorHit results from the graph store.

The graph store tests import this helper so every hit is a plain ``VectorHit``.
"""

from uuid import UUID

from agrag.common.data_models.vector_record import VectorHit


def assert_is_usable_vector_hit(
    hit: VectorHit, *, expected_id: UUID, expected_text: str
) -> None:
    """Assert a hit is a plain ``VectorHit`` usable by any consumer.

    Args:
        hit: The hit returned by a ``GraphStore``.
        expected_id: The id the hit must carry.
        expected_text: The ``text`` payload the hit must carry.
    """
    assert isinstance(hit, VectorHit)
    assert hit.id == expected_id
    assert hit.score >= 0.0
    assert hit.payload.get("text") == expected_text
