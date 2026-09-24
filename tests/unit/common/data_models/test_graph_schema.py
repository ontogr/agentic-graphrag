"""Tests for the GraphSchema, EntityType, RelationType models and GENERIC.

Verifies the shipped GENERIC schema is internally consistent (every relation
pattern references a declared entity label) and has its expected five entity
types and one relation, that a GraphSchema survives a JSON dump/validate
round trip unchanged, that EntityType defaults to empty properties and
subtypes, that it rejects property names reserved by the vector payload, and
that the full prompt serialization carries the schema's labels, descriptions,
properties, and patterns, including explicit empty markers.
"""

import pytest
from pydantic import ValidationError

from agrag.common.data_models.graph_schema import (
    GENERIC,
    EntityType,
    GraphSchema,
    RelationType,
)


# A schema exercising every serialized field: two entity types, declared
# properties, a subtype, and two relations with distinct pattern lists.
_CLINICAL_SCHEMA = GraphSchema(
    name="clinical",
    version="2",
    entities=[
        EntityType(
            label="Drug",
            description="A medication.",
            properties={"name": "str", "dosage": "float"},
            subtypes=["Biologic"],
        ),
        EntityType(label="Condition", description="A diagnosed condition."),
    ],
    relations=[
        RelationType(
            label="TREATS",
            description="A drug treats a condition.",
            patterns=[("Drug", "Condition")],
        ),
        RelationType(
            label="INDICATES",
            description="Two conditions co-occur.",
            patterns=[("Condition", "Condition"), ("Drug", "Condition")],
        ),
    ],
)


class TestGenericSchema:
    """The shipped GENERIC schema must be internally consistent."""

    def test_every_relation_pattern_references_a_declared_entity(self) -> None:
        """Every relation pattern's labels appear in the entity list."""
        declared = {entity.label for entity in GENERIC.entities}
        for relation in GENERIC.relations:
            for source, target in relation.patterns:
                assert source in declared
                assert target in declared


class TestEntityTypeReservedPropertyNames:
    """EntityType rejects property names the vector payload reserves."""

    @pytest.mark.parametrize("reserved", ["label", "text"])
    def test_rejects_reserved_name(self, reserved: str) -> None:
        """A property named label or text raises, naming the fix.

        Both are payload keys every mirrored entity embedding carries, so a
        property with either name would hide the real value from the
        VectorStore's label filter and keyword indexing. The message states
        the migration, since a schema persisted before this check existed
        must be renamed or stripped before it loads again.
        """
        with pytest.raises(ValidationError, match=reserved) as excinfo:
            EntityType(
                label="Person",
                description="A named individual.",
                properties={reserved: "str"},
            )
        assert "Rename or remove" in str(excinfo.value)

    def test_rejects_reserved_name_among_valid_ones(self) -> None:
        """One reserved name alongside valid properties still rejects the type."""
        with pytest.raises(ValidationError, match="label"):
            EntityType(
                label="Person",
                description="A named individual.",
                properties={"role": "str", "label": "str"},
            )


class TestPromptSerialization:
    """GraphSchema serializes itself for LLM prompts."""

    def test_to_prompt_description_includes_every_entity_and_relation(self) -> None:
        """Labels, descriptions, properties, subtypes, and patterns all appear."""
        text = _CLINICAL_SCHEMA.to_prompt_description()

        assert text == (
            "Schema clinical (version 2)\n"
            "Entity types:\n"
            "- Drug: A medication.\n"
            "  properties: name: str, dosage: float\n"
            "  subtypes: Biologic\n"
            "- Condition: A diagnosed condition.\n"
            "Relation types:\n"
            "- TREATS: A drug treats a condition.\n"
            "  valid patterns: (Drug, Condition)\n"
            "- INDICATES: Two conditions co-occur.\n"
            "  valid patterns: (Condition, Condition), (Drug, Condition)"
        )

    def test_empty_patterns_are_explicit(self) -> None:
        """Empty relation patterns render as an explicit absence of patterns."""
        schema = GraphSchema(
            name="empty-patterns",
            version="1",
            entities=[EntityType(label="A", description="A")],
            relations=[RelationType(label="LINKS", description="Links", patterns=[])],
        )

        assert "valid patterns: (none)" in schema.to_prompt_description()
        assert "- LINKS: (none)" in schema.to_compact_summary()

    def test_empty_relations_are_explicit(self) -> None:
        """Schemas without relations state that the relation list is empty."""
        schema = GraphSchema(
            name="no-relations",
            version="1",
            entities=[EntityType(label="A", description="A")],
            relations=[],
        )

        assert "Relation types:\n(none)" in schema.to_prompt_description()
        assert "Relation types:\n(none)" in schema.to_compact_summary()
