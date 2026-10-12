"""Pending vector-deletion queries share one public node label.

The enqueue, clear and fetch builders in resolution_write address the node
that records a vector deletion still needing a retry. Pinning all three to
the public constant keeps a rename from leaving one query behind.
"""

from collections.abc import Callable

import pytest

from agrag.common.data_models.resolved_entity import (
    RESOLVED_ENTITY_VECTOR_DELETION_LABEL,
)
from agrag.cypher.resolution_write import (
    clear_resolved_entity_vector_deletions_query,
    enqueue_resolved_entity_vector_deletions_query,
    fetch_resolved_entity_vector_deletions_query,
)


class TestResolvedEntityVectorDeletionLabel:
    """Vector-deletion queries use the public pending-deletion label."""

    @pytest.mark.parametrize(
        "build_query",
        [
            enqueue_resolved_entity_vector_deletions_query,
            clear_resolved_entity_vector_deletions_query,
            fetch_resolved_entity_vector_deletions_query,
        ],
    )
    def test_query_uses_the_public_label(self, build_query: Callable[[], str]) -> None:
        """Each pending-deletion query addresses the shared label."""
        assert f":{RESOLVED_ENTITY_VECTOR_DELETION_LABEL}" in build_query()
