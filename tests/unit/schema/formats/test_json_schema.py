"""Tests for the JSON Schema export."""

import json
from typing import Any

import jsonschema
import pytest

from agrag.common.data_models.graph_schema import (
    Cardinality,
    EntityType,
    GraphSchema,
    PropertySpec,
    RelationType,
)
from agrag.schema.formats import to_json_schema
from tests.unit.schema.formats.conftest import FIXTURES


def _document(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "entities": [
            {
                "label": "Person",
                "text": "Ada",
                "properties": {"email": "ada@example.org", "born": "1815-12-10"},
            },
            {"label": "Company", "text": "Acme", "properties": {"status": "active"}},
        ],
        "relations": [
            {
                "type": "WORKS_FOR",
                "source": "Ada",
                "target": "Acme",
                "source_label": "Person",
                "target_label": "Company",
            }
        ],
    }
    return {**document, **overrides}


class TestToJsonSchema:
    """The exporter describes the extraction output for a schema."""

    def test_matches_the_company_fixture(self, company_schema: GraphSchema) -> None:
        """The dict equals the committed fixture."""
        expected = json.loads(
            (FIXTURES / "company.schema.json").read_text(encoding="utf-8")
        )

        assert to_json_schema(company_schema) == expected

    def test_output_is_a_valid_schema_and_accepts_good_data(
        self, company_schema: GraphSchema
    ) -> None:
        """The result passes the meta-schema, and matching data passes."""
        result = to_json_schema(company_schema)

        jsonschema.Draft202012Validator.check_schema(result)
        jsonschema.validate(_document(), result)

    @pytest.mark.parametrize(
        "document",
        [
            _document(entities=[{"label": "Person", "text": "Ada", "properties": {}}]),
            _document(
                entities=[
                    {
                        "label": "Company",
                        "text": "Acme",
                        "properties": {"status": "bankrupt"},
                    }
                ]
            ),
            _document(
                relations=[
                    {
                        "type": "WORKS_FOR",
                        "source": "Acme",
                        "target": "Ada",
                        "source_label": "Organization",
                        "target_label": "Person",
                    }
                ]
            ),
            _document(entities=[{"label": "Planet", "text": "Mars"}]),
        ],
        ids=["missing-required", "bad-enum", "wrong-pattern", "unknown-label"],
    )
    def test_rejects_data_that_breaks_the_schema(
        self, company_schema: GraphSchema, document: dict[str, Any]
    ) -> None:
        """Reject each document that breaks the schema.

        A missing required property, a bad enum value, a pattern break and
        an unknown label each fail validation.
        """
        validator = jsonschema.Draft202012Validator(to_json_schema(company_schema))

        assert list(validator.iter_errors(document))

    def test_pattern_accepts_descendants_of_the_target(
        self, company_schema: GraphSchema
    ) -> None:
        """A pattern that names Organization also accepts Company."""
        result = to_json_schema(company_schema)

        allowed = result["$defs"]["relation-WORKS_FOR"]["anyOf"]
        assert allowed == [
            {
                "properties": {
                    "source_label": {"const": "Person"},
                    "target_label": {"enum": ["Company", "Organization"]},
                }
            }
        ]

    def test_schema_without_relations_rejects_every_relation(self) -> None:
        """An empty relation list gives a schema that no relation satisfies."""
        schema = GraphSchema(
            name="t",
            version="1",
            entities=[EntityType(label="A", description="a")],
            relations=[],
        )
        result = to_json_schema(schema)

        jsonschema.Draft202012Validator.check_schema(result)
        assert result["properties"]["relations"]["items"] is False

    def test_limits_and_symmetry_are_annotations(self) -> None:
        """Cardinality and symmetry appear as x-agrag annotations."""
        schema = GraphSchema(
            name="t",
            version="1",
            entities=[EntityType(label="A", description="a")],
            relations=[
                RelationType(
                    label="R",
                    description="d",
                    patterns=[("A", "A")],
                    cardinality=Cardinality(max_per_source=2, max_per_target=2),
                    symmetric=True,
                )
            ],
        )

        node = to_json_schema(schema)["$defs"]["relation-R"]

        assert node["x-agrag-max-per-source"] == 2
        assert node["x-agrag-max-per-target"] == 2
        assert node["x-agrag-symmetric"] is True

    def test_propertyless_entity_needs_a_properties_object(
        self, company_schema: GraphSchema
    ) -> None:
        """Organization accepts empty properties and rejects a missing object."""
        validator = jsonschema.Draft202012Validator(to_json_schema(company_schema))
        present = {
            "entities": [{"label": "Organization", "text": "Acme", "properties": {}}],
            "relations": [],
        }
        missing = {
            "entities": [{"label": "Organization", "text": "Acme"}],
            "relations": [],
        }

        assert not list(validator.iter_errors(present))
        assert list(validator.iter_errors(missing))

    def test_shared_entity_and_relation_labels_stay_distinct(self) -> None:
        """One label for both kinds still validates each shape."""
        schema = GraphSchema(
            name="t",
            version="1",
            entities=[EntityType(label="X", description="x")],
            relations=[RelationType(label="X", description="y", patterns=[("X", "X")])],
        )
        result = to_json_schema(schema)
        validator = jsonschema.Draft202012Validator(result)
        document = {
            "entities": [{"label": "X", "text": "a", "properties": {}}],
            "relations": [
                {
                    "type": "X",
                    "source": "a",
                    "target": "b",
                    "source_label": "X",
                    "target_label": "X",
                }
            ],
        }

        assert set(result["$defs"]) == {"entity-X", "relation-X"}
        assert not list(validator.iter_errors(document))

    def test_labels_with_pointer_characters_still_resolve(self) -> None:
        """A label with slashes validates through its escaped reference."""
        schema = GraphSchema(
            name="t",
            version="1",
            entities=[EntityType(label="A/B", description="x")],
            relations=[],
        )
        result = to_json_schema(schema)
        validator = jsonschema.Draft202012Validator(result)
        document = {
            "entities": [{"label": "A/B", "text": "a", "properties": {}}],
            "relations": [],
        }

        assert not list(validator.iter_errors(document))

    def test_enum_keeps_one_copy_of_each_converted_value(self) -> None:
        """Distinct text forms of one number give one enum entry."""
        schema = GraphSchema(
            name="t",
            version="1",
            entities=[
                EntityType(
                    label="A",
                    description="a",
                    properties={
                        "count": PropertySpec(type="integer", enum=["0", "-0"]),
                        "big": PropertySpec(type="float", enum=["9007199254740993"]),
                    },
                )
            ],
            relations=[],
        )

        inner = to_json_schema(schema)["$defs"]["entity-A"]["properties"]["properties"][
            "properties"
        ]

        assert inner["count"]["enum"] == [0]
        assert inner["big"]["enum"] == [9007199254740993]

    def test_symmetric_parent_child_accepts_the_reversed_pair(self) -> None:
        """A symmetric pattern also matches the reverse direction."""
        schema = GraphSchema(
            name="t",
            version="1",
            entities=[
                EntityType(label="Base", description="a parent."),
                EntityType(label="Sub", description="a child.", parents=["Base"]),
            ],
            relations=[
                RelationType(
                    label="LINKED",
                    description="a symmetric link.",
                    patterns=[("Base", "Sub")],
                    symmetric=True,
                )
            ],
        )
        validator = jsonschema.Draft202012Validator(to_json_schema(schema))
        document = {
            "entities": [
                {"label": "Sub", "text": "a", "properties": {}},
                {"label": "Base", "text": "b", "properties": {}},
            ],
            "relations": [
                {
                    "type": "LINKED",
                    "source": "a",
                    "target": "b",
                    "source_label": "Sub",
                    "target_label": "Base",
                }
            ],
        }

        assert not list(validator.iter_errors(document))

    def test_child_source_matches_a_parent_based_pattern(self) -> None:
        """A pattern naming a parent also accepts a child as the source."""
        schema = GraphSchema(
            name="t",
            version="1",
            entities=[
                EntityType(label="Base", description="a parent."),
                EntityType(label="Sub", description="a child.", parents=["Base"]),
                EntityType(label="Other", description="another type."),
            ],
            relations=[
                RelationType(
                    label="USES",
                    description="a use.",
                    patterns=[("Base", "Other")],
                )
            ],
        )
        validator = jsonschema.Draft202012Validator(to_json_schema(schema))
        document = {
            "entities": [
                {"label": "Sub", "text": "a", "properties": {}},
                {"label": "Other", "text": "b", "properties": {}},
            ],
            "relations": [
                {
                    "type": "USES",
                    "source": "a",
                    "target": "b",
                    "source_label": "Sub",
                    "target_label": "Other",
                }
            ],
        }

        assert not list(validator.iter_errors(document))
