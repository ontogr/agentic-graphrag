"""Tests for the pending-tag Cypher builders in agrag.cypher.cutover_job_write.

Covers rejection of unsafe labels and relationship types by every builder that
interpolates one into a query, and by the two pending index builders in
agrag.cypher.schema.
"""

from collections.abc import Callable

import pytest

from agrag.cypher.cutover_job_write import (
    clear_pending_node_tags_query,
    clear_pending_relation_tags_query,
    delete_pending_nodes_query,
    delete_pending_relations_query,
)
from agrag.cypher.schema import pending_node_index_query, pending_relation_index_query


UNSAFE_IDENTIFIERS = [
    "A]-() DELETE (x",
    "Node`) DETACH DELETE (m",
    "has space",
    "",
]

LABEL_BUILDERS: list[Callable[[str], str]] = [
    clear_pending_node_tags_query,
    delete_pending_nodes_query,
    pending_node_index_query,
]

RELATION_TYPE_BUILDERS: list[Callable[[str], str]] = [
    clear_pending_relation_tags_query,
    delete_pending_relations_query,
    pending_relation_index_query,
]


class TestPendingBuildersRejectUnsafeIdentifiers:
    """Every builder that takes a label or type refuses unsafe input."""

    @pytest.mark.parametrize("unsafe", UNSAFE_IDENTIFIERS)
    @pytest.mark.parametrize("build", LABEL_BUILDERS)
    def test_label_argument_raises_for_unsafe_identifier(
        self, build: Callable[[str], str], unsafe: str
    ) -> None:
        """An unsafe label raises before any query text is produced."""
        with pytest.raises(ValueError):
            build(unsafe)

    @pytest.mark.parametrize("unsafe", UNSAFE_IDENTIFIERS)
    @pytest.mark.parametrize("build", RELATION_TYPE_BUILDERS)
    def test_relation_type_argument_raises_for_unsafe_identifier(
        self, build: Callable[[str], str], unsafe: str
    ) -> None:
        """An unsafe relationship type raises before any query text is produced."""
        with pytest.raises(ValueError):
            build(unsafe)
