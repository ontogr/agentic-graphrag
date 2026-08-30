"""Tests for the GraphSchema contract and the GENERIC schema."""

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
