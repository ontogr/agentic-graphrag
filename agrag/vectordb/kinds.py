"""Map public graph labels to external collection kinds."""

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.community import COMMUNITY_LABEL
from agrag.common.data_models.resolved_entity import RESOLVED_ENTITY_LABEL
from agrag.common.data_models.vector_record import VectorKind


def kind_for_label(label: str) -> VectorKind:
    """Return the system collection kind, or ENTITY for a schema label."""
    return {
        CHUNK_LABEL: VectorKind.CHUNK,
        COMMUNITY_LABEL: VectorKind.COMMUNITY,
        RESOLVED_ENTITY_LABEL: VectorKind.RESOLVED_ENTITY,
    }.get(label, VectorKind.ENTITY)
