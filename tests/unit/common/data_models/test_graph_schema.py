"""Tests for the GraphSchema, EntityType and RelationType models.

Verifies that EntityType rejects property names reserved by the vector payload,
and that the full prompt serialization carries the schema's labels,
descriptions, properties, and patterns, including explicit empty markers.
"""

import pytest
from pydantic import ValidationError

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.community import COMMUNITY_LABEL
from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.graph_schema import (
    RESERVED_ENTITY_LABELS,
    EntityType,
    GraphSchema,
    PropertySpec,
    RelationType,
)
from agrag.common.data_models.resolved_entity import RESOLVED_ENTITY_LABEL
from agrag.common.data_models.structure import (
    FIGURE_LABEL,
    SECTION_LABEL,
    SOURCE_LABEL,
    TABLE_LABEL,
)
from agrag.cypher.entities import MERGE_ALIAS_LABEL, NODE_IDENTITY_LABEL


# A schema exercising every serialized field: two entity types, declared
# properties, a subtype, and two relations with distinct pattern lists.
_CLINICAL_SCHEMA = GraphSchema(
    name="clinical",
    version="2",
    entities=[
        EntityType(
            label="Drug",
            description="A medication.",
            properties={
                "brand": PropertySpec(type="string", required=True),
                "dosage": PropertySpec(type="float", description="Dose in milligrams."),
                "form": PropertySpec(type="string", enum=["tablet", "capsule"]),
            },
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
                properties={reserved: PropertySpec(type="string")},
            )
        assert "Rename or remove" in str(excinfo.value)

    def test_rejects_reserved_name_among_valid_ones(self) -> None:
        """One reserved name alongside valid properties still rejects the type."""
        with pytest.raises(ValidationError, match="label"):
            EntityType(
                label="Person",
                description="A named individual.",
                properties={
                    "role": PropertySpec(type="string"),
                    "label": PropertySpec(type="string"),
                },
            )


class TestEntityTypeReservedLabels:
    """EntityType rejects labels that the graph uses for its own nodes."""

    @pytest.mark.parametrize("label", sorted(RESERVED_ENTITY_LABELS))
    def test_rejects_a_reserved_label(self, label: str) -> None:
        """An entity type cannot take over a structure or system label."""
        with pytest.raises(ValidationError, match="reserved label"):
            EntityType(label=label, description="x")

    def test_rejects_a_reserved_subtype(self) -> None:
        """A subtype label is a node label too."""
        with pytest.raises(ValidationError, match="reserved label"):
            EntityType(label="Clause", description="x", subtypes=["Section"])

    def test_reserved_identity_labels_match_graph_write_labels(self) -> None:
        """The reserved set matches the labels used by graph writes."""
        assert {
            DOCUMENT_LABEL,
            CHUNK_LABEL,
            SECTION_LABEL,
            TABLE_LABEL,
            FIGURE_LABEL,
            SOURCE_LABEL,
            COMMUNITY_LABEL,
            RESOLVED_ENTITY_LABEL,
            CUTOVER_JOB_LABEL,
            NODE_IDENTITY_LABEL,
            MERGE_ALIAS_LABEL,
        } == RESERVED_ENTITY_LABELS


class TestPromptSerialization:
    """GraphSchema serializes itself for LLM prompts."""

    def test_to_prompt_description_includes_every_entity_and_relation(self) -> None:
        """Labels, descriptions, properties, subtypes, and patterns all appear."""
        text = _CLINICAL_SCHEMA.to_prompt_description()

        assert text == (
            "Schema clinical (version 2)\n"
            "Entity types:\n"
            "- Drug: A medication.\n"
            "  properties:\n"
            "    - brand (string, required)\n"
            "    - dosage (float): Dose in milligrams.\n"
            "    - form (string, one of: tablet, capsule)\n"
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


class TestPropertySpec:
    """Property specs validate declared types and enum values."""

    def test_type_is_required_and_rejects_unknown_names(self) -> None:
        """A spec must name one of the supported value types."""
        with pytest.raises(ValidationError, match="Field required"):
            PropertySpec(required=True)  # ty: ignore[missing-argument]
        with pytest.raises(ValidationError):
            PropertySpec(type="str")

    @pytest.mark.parametrize(
        "property_type", ["string", "integer", "float", "boolean", "date"]
    )
    def test_accepts_supported_types(self, property_type: str) -> None:
        """Each supported property type can be declared."""
        assert PropertySpec(type=property_type).type == property_type

    @pytest.mark.parametrize(
        ("property_type", "values"),
        [
            ("string", ["tablet", "capsule"]),
            ("integer", ["1", "-2", "40"]),
            ("float", ["1.5", "-2e3", "3"]),
            ("boolean", ["true", "false"]),
            ("date", ["2024-01-31", "1999-12-31"]),
        ],
    )
    def test_accepts_enum_values_that_match_type(
        self, property_type: str, values: list[str]
    ) -> None:
        """Enum entries use the text form accepted by their declared type."""
        assert PropertySpec(type=property_type, enum=values).enum == values

    @pytest.mark.parametrize(
        ("property_type", "value"),
        [
            ("integer", "1.5"),
            ("float", "nan"),
            ("boolean", "yes"),
            ("date", "2024-13-01"),
            ("string", " "),
        ],
    )
    def test_rejects_enum_values_that_do_not_match_type(
        self, property_type: str, value: str
    ) -> None:
        """Enum entries must be valid values for their declared type."""
        with pytest.raises(ValidationError, match="not valid for type"):
            PropertySpec(type=property_type, enum=[value])

    def test_rejects_empty_or_repeated_enum(self) -> None:
        """An enum must contain distinct allowed values."""
        with pytest.raises(ValidationError, match="enum is empty"):
            PropertySpec(type="string", enum=[])
        with pytest.raises(ValidationError, match="more than once"):
            PropertySpec(type="string", enum=["a", "a"])

    def test_description_survives_schema_json_round_trip(self) -> None:
        """Serialized schema preserves property metadata and prompt wording."""
        schema = GraphSchema.model_validate_json(_CLINICAL_SCHEMA.model_dump_json())

        assert schema == _CLINICAL_SCHEMA
        assert schema.entities[0].properties["form"].describe("form") == (
            "form (string, one of: tablet, capsule)"
        )
        assert (
            schema.to_prompt_description() == _CLINICAL_SCHEMA.to_prompt_description()
        )
