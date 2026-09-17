"""Tests for the GraphSchema, EntityType, RelationType models and GENERIC.

Verifies the shipped GENERIC schema is internally consistent (every relation
pattern references a declared entity label) and has its expected five entity
types and one relation, that a GraphSchema survives a JSON dump/validate
round trip unchanged, that EntityType defaults to empty properties and
subtypes, and that it rejects property names reserved by the vector payload.
"""

import pytest
from pydantic import ValidationError

from agrag.common.data_models.graph_schema import (
    GENERIC,
    EntityType,
    GraphSchema,
    RelationType,
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
        """A property named label or text raises at construction.

        Both are payload keys every mirrored entity embedding carries, so a
        property with either name would hide the real value from the
        VectorStore's label filter and keyword indexing.
        """
        with pytest.raises(ValidationError, match=reserved):
            EntityType(
                label="Person",
                description="A named individual.",
                properties={reserved: "str"},
            )

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
