"""Shared assertions for VectorHit results across vector and graph stores.

Both ``tests/integration/vectordb/`` and ``tests/integration/graphdb/`` import
this helper so the two backends prove they return the same ``VectorHit`` shape,
with no adapter between them.
"""

from uuid import UUID

from agrag.common.data_models.vector_record import VectorHit


def assert_is_usable_vector_hit(
    hit: VectorHit, *, expected_id: UUID, expected_text: str
) -> None:
    """Assert a hit is a plain ``VectorHit`` usable by any consumer.

    Args:
        hit: The hit returned by either a ``VectorStore`` or a ``GraphStore``.
        expected_id: The id the hit must carry.
        expected_text: The ``text`` payload the hit must carry.
    """
    assert isinstance(hit, VectorHit)
    assert hit.id == expected_id
    assert hit.score >= 0.0
    assert hit.payload.get("text") == expected_text
