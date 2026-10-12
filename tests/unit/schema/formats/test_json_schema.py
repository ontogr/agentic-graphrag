"""Tests for the JSON Schema export."""

import json
from typing import Any

import pytest

from agrag.common.data_models.graph_schema import (
    Cardinality,
    EntityType,
    GraphSchema,
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
        jsonschema = pytest.importorskip("jsonschema")
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
        jsonschema = pytest.importorskip("jsonschema")
        validator = jsonschema.Draft202012Validator(to_json_schema(company_schema))

        assert list(validator.iter_errors(document))

    def test_pattern_accepts_descendants_of_the_target(
        self, company_schema: GraphSchema
    ) -> None:
        """A pattern that names Organization also accepts Company."""
        result = to_json_schema(company_schema)

        allowed = result["$defs"]["WORKS_FOR"]["anyOf"]
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
        jsonschema = pytest.importorskip("jsonschema")
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

        node = to_json_schema(schema)["$defs"]["R"]

        assert node["x-agrag-max-per-source"] == 2
        assert node["x-agrag-max-per-target"] == 2
        assert node["x-agrag-symmetric"] is True
