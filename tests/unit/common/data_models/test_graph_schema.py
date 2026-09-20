"""Tests for the GraphSchema, EntityType, RelationType models and GENERIC.

Verifies the shipped GENERIC schema is internally consistent (every relation
pattern references a declared entity label) and has its expected five entity
types and one relation, that a GraphSchema survives a JSON dump/validate
round trip unchanged, that EntityType defaults to empty properties and
subtypes, that it rejects property names reserved by the vector payload, and
that its two prompt serializations carry the schema's labels and patterns
(the full one with descriptions and properties, the compact one without).
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

    def test_generic_has_the_expected_types(self) -> None:
        """GENERIC declares the five expected entity types and one relation."""
        labels = {entity.label for entity in GENERIC.entities}
        assert labels == {
            "Person",
            "Organization",
            "Location",
            "Event",
            "Product",
        }
        assert [relation.label for relation in GENERIC.relations] == ["RELATED_TO"]


class TestGraphSchemaRoundTrip:
    """A GraphSchema round-trips through Pydantic's json dump/validate."""

    def test_model_dump_then_validate_is_unchanged(self) -> None:
        """Dumping to json and validating back yields an equal schema."""
        schema = GraphSchema(
            name="clinical",
            version="2",
            entities=[EntityType(label="Drug", description="A medication.")],
            relations=[
                RelationType(
                    label="TREATS",
                    description="A drug treats a condition.",
                    patterns=[("Drug", "Drug")],
                )
            ],
        )
        restored = GraphSchema.model_validate(schema.model_dump(mode="json"))
        assert restored == schema

    def test_default_fields_are_empty(self) -> None:
        """EntityType defaults to no properties and no subtypes."""
        entity = EntityType(label="X", description="y")
        assert entity.properties == {}
        assert entity.subtypes == []


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

    def test_payload_written_before_the_check_must_be_migrated(self) -> None:
        """A persisted schema declaring a reserved property fails to load.

        The rejection is deliberately breaking: a payload dumped before this
        check existed validates no more, and the error names the migration
        rather than accepting a schema whose two retrieval paths disagree.
        """
        persisted = {
            "name": "clinical",
            "version": "1",
            "entities": [
                {
                    "label": "Person",
                    "description": "A named individual.",
                    "properties": {"text": "str"},
                }
            ],
            "relations": [],
        }
        with pytest.raises(ValidationError, match="text") as excinfo:
            GraphSchema.model_validate(persisted)
        assert "Rename or remove" in str(excinfo.value)

    def test_rejects_reserved_name_among_valid_ones(self) -> None:
        """One reserved name alongside valid properties still rejects the type."""
        with pytest.raises(ValidationError, match="label"):
            EntityType(
                label="Person",
                description="A named individual.",
                properties={"role": "str", "label": "str"},
            )

    def test_rejects_when_nested_in_schema(self) -> None:
        """The rejection also applies to a type built inside a GraphSchema."""
        with pytest.raises(ValidationError, match="text"):
            GraphSchema(
                name="clinical",
                version="1",
                entities=[
                    EntityType(
                        label="Person",
                        description="A named individual.",
                        properties={"text": "str"},
                    )
                ],
                relations=[],
            )

    def test_accepts_unreserved_names(self) -> None:
        """Names outside the reserved set are kept unchanged."""
        entity = EntityType(
            label="Person",
            description="A named individual.",
            properties={"role": "str", "age": "int"},
        )
        assert entity.properties == {"role": "str", "age": "int"}


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

    def test_to_prompt_description_on_generic(self) -> None:
        """GENERIC lists its five entity labels and every RELATED_TO pattern."""
        text = GENERIC.to_prompt_description()

        for label in ("Person", "Organization", "Location", "Event", "Product"):
            assert f"- {label}: " in text
        assert "- RELATED_TO: A generic relationship between two entities." in text
        assert "(Person, Person)" in text
        assert "(Product, Product)" in text

    def test_to_compact_summary_omits_descriptions_and_properties(self) -> None:
        """Labels and patterns survive; descriptions, properties, subtypes do not."""
        text = _CLINICAL_SCHEMA.to_compact_summary()

        assert text == (
            "Entity labels: Drug, Condition\n"
            "Relation types:\n"
            "- TREATS: (Drug, Condition)\n"
            "- INDICATES: (Condition, Condition), (Drug, Condition)"
        )
        assert "A medication." not in text
        assert "A diagnosed condition." not in text
        assert "name" not in text
        assert "dosage" not in text
        assert "Biologic" not in text
