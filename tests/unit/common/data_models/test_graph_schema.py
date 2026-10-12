"""Check schema hierarchy, relation rules, validation and public renderings."""

import pytest
from pydantic import ValidationError

from agrag.common.data_models import Cardinality
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


# A schema exercising properties, hierarchy, limits, symmetry and patterns.
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
            parents=["Medicine"],
        ),
        EntityType(label="Medicine", description="A pharmaceutical product."),
        EntityType(
            label="Biologic", description="A biological drug.", parents=["Drug"]
        ),
        EntityType(label="Condition", description="A diagnosed condition."),
    ],
    relations=[
        RelationType(
            label="TREATS",
            description="A drug treats a condition.",
            patterns=[("Drug", "Condition")],
            cardinality=Cardinality(max_per_source=2),
        ),
        RelationType(
            label="COOCCURS_WITH",
            description="Two conditions co-occur.",
            patterns=[("Condition", "Condition")],
            symmetric=True,
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

    def test_rejects_a_reserved_parent(self) -> None:
        """A parent label is a node label too."""
        with pytest.raises(ValidationError, match="reserved label"):
            EntityType(label="Clause", description="x", parents=["Section"])


class TestHierarchyBehavior:
    """Schema hierarchies and relation declarations enforce their contract."""

    @staticmethod
    def entity(label: str, *parents: str) -> EntityType:
        """Build a declared entity type."""
        return EntityType(label=label, description=label, parents=list(parents))

    @staticmethod
    def schema(
        entities: list[EntityType], relations: list[RelationType] | None = None
    ) -> GraphSchema:
        """Build a schema from the given public model values."""
        return GraphSchema(
            name="test", version="1", entities=entities, relations=relations or []
        )

    def test_rejects_unknown_parent_and_cycle(self) -> None:
        """Every parent must exist and hierarchy paths must be acyclic."""
        with pytest.raises(ValidationError, match="names unknown parent 'Missing'"):
            self.schema([self.entity("Vendor", "Missing")])
        with pytest.raises(ValidationError, match="A -> B -> A"):
            self.schema([self.entity("A", "B"), self.entity("B", "A")])

    def test_unknown_parent_suggests_a_close_declared_type(self) -> None:
        """A likely spelling mistake names the declared replacement."""
        with pytest.raises(ValidationError, match="Did you mean 'Organization'"):
            self.schema(
                [self.entity("Organization"), self.entity("Vendor", "Organisation")]
            )

    def test_rejects_self_and_repeated_parents(self) -> None:
        """A type cannot repeat itself or a parent in its parent list."""
        with pytest.raises(ValidationError, match="lists itself as a parent"):
            self.entity("A", "A")
        with pytest.raises(ValidationError, match="lists parent.*more than once"):
            self.entity("Child", "Parent", "Parent")

    def test_rejects_duplicate_entity_and_relation_labels(self) -> None:
        """One label has one entity definition and one relation definition."""
        with pytest.raises(ValidationError, match="declared more than once"):
            self.schema([self.entity("Person"), self.entity("Person")])
        with pytest.raises(ValidationError, match="declared more than once"):
            self.schema(
                [self.entity("Person")],
                [RelationType(label="KNOWS", description="x", patterns=[])] * 2,
            )

    def test_ancestors_are_breadth_first_and_deduplicate_diamonds(self) -> None:
        """Parents precede grandparents, with shared ancestors listed once."""
        schema = self.schema(
            [
                self.entity("Root"),
                self.entity("Left", "Root"),
                self.entity("Right", "Root"),
                self.entity("Leaf", "Left", "Right"),
            ]
        )
        assert schema.ancestors("Leaf") == ["Left", "Right", "Root"]
        assert schema.node_labels("Leaf") == ["Leaf", "Left", "Right", "Root"]

    def test_inherited_patterns_keep_direction_unless_symmetric(self) -> None:
        """Children satisfy parent patterns, while reversal needs symmetry."""
        entities = [
            self.entity("Person"),
            self.entity("Organization"),
            self.entity("Vendor", "Organization"),
        ]
        relation = RelationType(
            label="WORKS_AT", description="x", patterns=[("Person", "Organization")]
        )
        schema = self.schema(entities, [relation])
        assert schema.allows("WORKS_AT", "Person", "Vendor")
        assert not schema.allows("WORKS_AT", "Vendor", "Person")
        assert not schema.allows("UNKNOWN", "Person", "Vendor")
        assert not schema.allows("WORKS_AT", "Unknown", "Vendor")
        assert not schema.allows("WORKS_AT", "Person", "Unknown")
        symmetric_relation = RelationType(
            label="RELATED",
            description="x",
            patterns=[("Organization", "Vendor")],
            symmetric=True,
        )
        symmetric = self.schema(entities, [symmetric_relation])
        assert symmetric.allows("RELATED", "Vendor", "Organization")

    def test_json_round_trip_and_public_rendering(self) -> None:
        """Dumped schema loads as the same contract and prompt shows its rules."""
        dumped = _CLINICAL_SCHEMA.model_dump(mode="json")
        assert GraphSchema.model_validate(dumped) == _CLINICAL_SCHEMA
        prompt = _CLINICAL_SCHEMA.to_prompt_description()
        assert "parents: Medicine" in prompt
        assert "declared limits (not enforced): at most 2 targets" in prompt
        assert "symmetric: yes" in prompt
        assert "pattern that names a type allows every child" in prompt
        assert "Stored nodes carry only their leaf label" in prompt
        assert "subtypes" not in prompt

    def test_resolve_expands_patterns_and_counts_labels(self) -> None:
        """Resolved output lists every child combination and total labels."""
        schema = self.schema(
            [self.entity("A"), self.entity("B", "A")],
            [RelationType(label="R", description="x", patterns=[("A", "A")])],
        )

        assert "valid patterns: (A, A), (A, B), (B, A), (B, B)" in schema.resolve()
        assert "Total labels: 3" in schema.resolve()

    def test_cardinality_and_symmetric_limits_are_validated(self) -> None:
        """Limits are positive and symmetric limits must agree."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            Cardinality(max_per_source=0)
        with pytest.raises(ValidationError, match="must be equal"):
            RelationType(
                label="R",
                description="x",
                patterns=[("Person", "Person")],
                symmetric=True,
                cardinality=Cardinality(max_per_source=1),
            )
        with pytest.raises(ValidationError, match="must be the same type"):
            self.schema(
                [self.entity("Person"), self.entity("Organization")],
                [
                    RelationType(
                        label="R",
                        description="x",
                        patterns=[("Person", "Organization")],
                        symmetric=True,
                    )
                ],
            )


class TestPromptSerialization:
    """GraphSchema serializes itself for LLM prompts."""

    def test_to_prompt_description_includes_hierarchy_and_relation_rules(self) -> None:
        """Labels, parents, properties, limits and symmetry appear."""
        text = _CLINICAL_SCHEMA.to_prompt_description()

        assert text == (
            "Schema clinical (version 2)\n"
            "Entity types:\n"
            "- Drug: A medication.\n"
            "  parents: Medicine\n"
            "  properties:\n"
            "    - brand (string, required)\n"
            "    - dosage (float): Dose in milligrams.\n"
            "    - form (string, one of: tablet, capsule)\n"
            "- Medicine: A pharmaceutical product.\n"
            "- Biologic: A biological drug.\n"
            "  parents: Drug\n"
            "- Condition: A diagnosed condition.\n"
            "Relation types:\n"
            "- TREATS: A drug treats a condition.\n"
            "  valid patterns: (Drug, Condition)\n"
            "  declared limits (not enforced): at most 2 targets per source\n"
            "- COOCCURS_WITH: Two conditions co-occur.\n"
            "  valid patterns: (Condition, Condition)\n"
            "  symmetric: yes\n"
            "Note: a pattern that names a type allows every child of that type.\n"
            "Stored nodes carry only their leaf label. Queries for a parent "
            "type must also match all descendant labels."
        )

    def test_compact_summary_shows_hierarchy_and_symmetry(self) -> None:
        """The compact form preserves parent context and symmetric semantics."""
        summary = _CLINICAL_SCHEMA.to_compact_summary()

        assert "Drug (parents: Medicine)" in summary
        assert "Biologic (parents: Drug)" in summary
        assert "[symmetric]" in summary
        assert "also cover its descendants" in summary

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
            "Candidate",
        } == RESERVED_ENTITY_LABELS

    def test_extra_fields_are_rejected(self) -> None:
        """Misspelled or removed schema fields cannot be silently ignored."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            EntityType.model_validate(
                {"label": "Thing", "description": "x", "subtypes": []}
            )
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            PropertySpec.model_validate({"type": "string", "typo": True})
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            RelationType.model_validate(
                {"label": "R", "description": "x", "patterns": [], "typo": 1}
            )
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            GraphSchema.model_validate(
                {
                    "name": "x",
                    "version": "1",
                    "entities": [],
                    "relations": [],
                    "typo": 1,
                }
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
