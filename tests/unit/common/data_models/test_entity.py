"""Tests for the Entity model: node record labels.

Covers the ancestor labels that reach the record alongside the entity's own
label.
"""

from datetime import UTC, datetime
from uuid import uuid4

from agrag.common.data_models.entity import Entity


def _entity() -> Entity:
    return Entity(
        id=uuid4(),
        created_at=datetime(2024, 1, 31, tzinfo=UTC),
        label="Vendor",
        name="Acme",
        properties={"hq": "Oslo"},
    )


class TestEntityNodeRecord:
    """to_node_record labels the node with its own type and ancestors."""

    def test_labels_default_to_own_label(self) -> None:
        """A root type's record carries only its own label."""
        assert _entity().to_node_record().labels == ["Vendor"]

    def test_labels_include_ancestors_nearest_first(self) -> None:
        """Ancestor labels follow the entity's own label in order."""
        record = _entity().to_node_record(ancestor_labels=["Organization", "Agent"])

        assert record.labels == ["Vendor", "Organization", "Agent"]
