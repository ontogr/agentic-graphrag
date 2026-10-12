"""Tests for the SHACL export."""

import pytest

from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    PropertySpec,
)
from agrag.schema.formats import to_shacl
from tests.unit.schema.formats.conftest import FIXTURES


class TestToShacl:
    """The exporter describes a schema as SHACL shapes in Turtle."""

    def test_matches_the_company_fixture(self, company_schema: GraphSchema) -> None:
        """The Turtle output equals the committed fixture."""
        expected = (FIXTURES / "company.shacl.ttl").read_text(encoding="utf-8")

        assert to_shacl(company_schema) == expected

    def test_output_parses_as_turtle(self, company_schema: GraphSchema) -> None:
        """The output parses as Turtle and carries triples."""
        rdflib = pytest.importorskip("rdflib")

        graph = rdflib.Graph()
        graph.parse(data=to_shacl(company_schema), format="turtle")

        assert len(graph) > 0

    def test_required_properties_declare_min_count(self) -> None:
        """A required property gets sh:minCount 1; an optional one does not."""
        schema = GraphSchema(
            name="t",
            version="1",
            entities=[
                EntityType(
                    label="Person",
                    description="A named individual.",
                    properties={
                        "email": PropertySpec(type="string", required=True),
                        "nick": PropertySpec(type="string"),
                    },
                )
            ],
            relations=[],
        )

        result = to_shacl(schema)

        assert result.count("sh:minCount 1") == 1

    def test_enum_values_appear_in_sh_in(self, company_schema: GraphSchema) -> None:
        """The status enum values appear in an sh:in list."""
        result = to_shacl(company_schema)

        assert "sh:in" in result
        assert '"active"' in result
        assert '"dissolved"' in result

    @pytest.mark.parametrize(
        ("property_type", "datatype"),
        [
            ("string", "xsd:string"),
            ("integer", "xsd:integer"),
            ("boolean", "xsd:boolean"),
            ("date", "xsd:date"),
        ],
        ids=["string", "integer", "boolean", "date"],
    )
    def test_property_types_map_to_xsd_datatypes(
        self, property_type: str, datatype: str
    ) -> None:
        """Each scalar property type maps to its XSD datatype."""
        schema = GraphSchema(
            name="t",
            version="1",
            entities=[
                EntityType(
                    label="Thing",
                    description="A thing.",
                    properties={"value": PropertySpec(type=property_type)},
                )
            ],
            relations=[],
        )

        assert datatype in to_shacl(schema)

    def test_parent_links_become_subclass(self, company_schema: GraphSchema) -> None:
        """Company keeps one rdfs:subClassOf link to Organization."""
        result = to_shacl(company_schema)

        assert result.count("rdfs:subClassOf") == 1
        assert "Organization" in result

    def test_symmetric_relations_are_marked(self, company_schema: GraphSchema) -> None:
        """The symmetric relation carries the agrag symmetric marker."""
        result = to_shacl(company_schema)

        assert result.count("x-agrag:symmetric") == 1

    def test_max_per_source_becomes_max_count(
        self, company_schema: GraphSchema
    ) -> None:
        """The single-target limit on WORKS_FOR becomes sh:maxCount 1."""
        result = to_shacl(company_schema)

        assert result.count("sh:maxCount 1") == 1

    def test_base_iri_override_replaces_the_default_namespace(
        self, company_schema: GraphSchema
    ) -> None:
        """A custom base IRI replaces the schema-derived namespace."""
        result = to_shacl(company_schema, base_iri="https://example.org/shapes#")

        assert "https://example.org/shapes#" in result
        assert "urn:agrag:schema:company:" not in result

    def test_schema_without_relations_exports_entities_only(self) -> None:
        """A schema with no relations still exports its entity shapes."""
        schema = GraphSchema(
            name="bare",
            version="1",
            entities=[EntityType(label="Person", description="A named individual.")],
            relations=[],
        )

        result = to_shacl(schema)

        assert "Person" in result
        assert "sh:property" not in result

    def test_special_characters_in_the_name_become_a_full_iri(self) -> None:
        """A name with spaces is percent-encoded inside angle brackets."""
        schema = GraphSchema(
            name="acme corp",
            version="1",
            entities=[EntityType(label="Person", description="A named individual.")],
            relations=[],
        )

        result = to_shacl(schema)

        assert "<urn:agrag:schema:acme%20corp:" in result
