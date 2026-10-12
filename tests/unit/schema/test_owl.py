"""Exercise OWL Turtle imports through the public schema-loading APIs."""

import logging
import subprocess
import sys

import pytest

from agrag.schema import SchemaLoadError, dump_schema, load_schema
from agrag.schema.formats import (
    SchemaFormatError,
    load_owl,
    loads_owl,
)


ONTOLOGY = """
@prefix ex: <https://example.test/ontology#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:Organization a owl:Class ;
    rdfs:label "Organization" ;
    rdfs:comment "An organized group." .
ex:Supplier a owl:Class ;
    rdfs:subClassOf ex:Organization ;
    rdfs:comment "A group that supplies goods." .
ex:Product a owl:Class ;
    rdfs:comment "An item made or sold." .
ex:registeredOn a owl:DatatypeProperty ;
    rdfs:domain ex:Supplier ;
    rdfs:range xsd:date .
ex:active a owl:DatatypeProperty ;
    rdfs:domain ex:Supplier ;
    rdfs:range xsd:boolean .
ex:provides a owl:ObjectProperty ;
    rdfs:label "PROVIDES" ;
    rdfs:comment "A supplier provides a product." ;
    rdfs:domain ex:Supplier ;
    rdfs:range ex:Product .
ex:ontology owl:imports <https://invalid.example/unavailable.ttl> .
ex:sample a owl:NamedIndividual .
"""


class TestOwlImport:
    """OWL readers preserve mapped schema data and report ignored RDF."""

    def test_loads_owl_returns_a_canonical_schema_and_warnings(self):
        """Text input preserves mapped terms in the full canonical dump."""
        result = loads_owl(ONTOLOGY, name="supply", version="4")

        assert (result.schema.name, result.schema.version) == ("supply", "4")
        assert result.schema.ancestors("Supplier") == ["Organization"]
        supplier = next(
            entity for entity in result.schema.entities if entity.label == "Supplier"
        )
        assert supplier.properties["registeredOn"].type == "date"
        assert supplier.properties["active"].type == "boolean"
        provides = next(
            rel for rel in result.schema.relations if rel.label == "PROVIDES"
        )
        assert provides.patterns == [("Supplier", "Product")]
        assert [warning.code for warning in result.warnings] == [
            "description_ignored",
            "description_ignored",
            "description_ignored",
            "missing_description",
            "missing_description",
            "comment_ignored",
            "construct_ignored",
            "individuals_ignored",
        ]
        assert dump_schema(result.schema) == {
            "name": "supply",
            "version": "4",
            "entities": [
                {
                    "label": "Organization",
                    "description": "Organization",
                    "parents": [],
                    "properties": {},
                },
                {
                    "label": "Product",
                    "description": "Product",
                    "parents": [],
                    "properties": {},
                },
                {
                    "label": "Supplier",
                    "description": "Supplier",
                    "parents": ["Organization"],
                    "properties": {
                        "active": {
                            "type": "boolean",
                            "required": False,
                            "enum": None,
                            "description": "active",
                        },
                        "registeredOn": {
                            "type": "date",
                            "required": False,
                            "enum": None,
                            "description": "registeredOn",
                        },
                    },
                },
            ],
            "relations": [
                {
                    "label": "PROVIDES",
                    "description": "provides",
                    "patterns": [["Supplier", "Product"]],
                    "cardinality": {
                        "max_per_source": None,
                        "max_per_target": None,
                    },
                    "symmetric": False,
                }
            ],
        }

    def test_load_schema_logs_warnings_and_returns_schema(self, tmp_path, caplog):
        """Path dispatch logs each warning and returns the validated schema."""
        path = tmp_path / "supply.ttl"
        path.write_text(ONTOLOGY)

        with caplog.at_level(logging.WARNING, logger="agrag.schema.formats.dispatch"):
            schema = load_schema(path)

        assert schema.name == "supply"
        assert (
            sum("missing_description" in record.message for record in caplog.records)
            == 2
        )

    def test_load_owl_reads_a_turtle_path_and_extends_it(self, tmp_path):
        """A Turtle path imports directly and serves as an extends source."""
        path = tmp_path / "supply.ttl"
        path.write_text(ONTOLOGY)

        imported = load_owl(path)
        extended = load_schema(
            {"extends": path, "entities": {"Distributor": "A reseller."}}
        )

        assert imported.schema.name == "supply"
        assert extended.ancestors("Supplier") == ["Organization"]
        assert {entity.label for entity in extended.entities} == {
            "Organization",
            "Supplier",
            "Product",
            "Distributor",
        }

    def test_import_uses_the_same_validation_as_other_schema_sources(self):
        """Canonical schema validation rejects reserved entity labels."""
        invalid = ONTOLOGY.replace(
            "ex:Supplier a owl:Class ;", "ex:Chunk a owl:Class ;", 1
        )

        with pytest.raises(SchemaLoadError, match="reserved"):
            loads_owl(invalid)

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            ("not Turtle [", "invalid Turtle"),
            (
                "@prefix ex: <https://example.test/> . ex:A a owl:Class .",
                "invalid Turtle",
            ),
        ],
    )
    def test_invalid_or_unbound_turtle_raises_format_error(self, text, message):
        """Malformed Turtle and undeclared prefixes fail as format errors."""
        with pytest.raises(SchemaFormatError, match=message):
            loads_owl(text)

    def test_missing_rdflib_extra_names_the_install_extra(self):
        """A clean interpreter reports the optional extra when rdflib is blocked."""
        script = (
            "import importlib.abc, sys\n"
            "class BlockRdfLib(importlib.abc.MetaPathFinder):\n"
            "    def find_spec(self, fullname, path, target=None):\n"
            "        if fullname == 'rdflib' or fullname.startswith('rdflib.'):\n"
            "            raise ModuleNotFoundError(name=fullname)\n"
            "        return None\n"
            "sys.meta_path.insert(0, BlockRdfLib())\n"
            "from agrag.schema.formats import loads_owl\n"
            "from agrag.schema.formats import SchemaFormatMissingExtraError\n"
            "try:\n"
            "    loads_owl('')\n"
            "except SchemaFormatMissingExtraError as error:\n"
            "    assert error.extra == 'schema-formats'\n"
            "else:\n"
            "    raise AssertionError('missing extra was not reported')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, check=False
        )

        assert result.returncode == 0, result.stderr

    def test_package_import_does_not_load_rdflib(self):
        """Importing the formats package leaves the optional module unloaded."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import agrag.schema.formats; "
                "assert 'rdflib' not in sys.modules",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr

    def test_unsupported_suffix_is_rejected_before_reading(self, tmp_path):
        """Files outside the documented suffix set fail as schema load errors."""
        path = tmp_path / "supply.rdf"
        path.write_text(ONTOLOGY)

        with pytest.raises(SchemaLoadError, match=".ttl"):
            load_schema(path)

    def test_object_property_union_domains_and_ranges_make_all_endpoint_pairs(self):
        """An asymmetric union yields its source-target cross product."""
        result = loads_owl("""
            @prefix ex: <https://example.test/union#> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

            ex:A a owl:Class . ex:B a owl:Class .
            ex:C a owl:Class . ex:D a owl:Class .
            ex:links a owl:ObjectProperty ;
                rdfs:domain [ owl:unionOf (ex:A ex:B) ] ;
                rdfs:range [ owl:unionOf (ex:C ex:D) ] .
        """)

        assert result.schema.relations[0].patterns == [
            ("A", "C"),
            ("A", "D"),
            ("B", "C"),
            ("B", "D"),
        ]

    def test_functional_and_inverse_functional_properties_set_directional_limits(self):
        """Functional markers limit source or target independently."""
        result = loads_owl("""
            @prefix ex: <https://example.test/limits#> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

            ex:A a owl:Class . ex:B a owl:Class .
            ex:out a owl:ObjectProperty, owl:FunctionalProperty ;
                rdfs:domain ex:A ; rdfs:range ex:B .
            ex:in a owl:ObjectProperty, owl:InverseFunctionalProperty ;
                rdfs:domain ex:A ; rdfs:range ex:B .
        """)
        limits = {rel.label: rel.cardinality for rel in result.schema.relations}

        assert limits["OUT"].max_per_source == 1
        assert limits["OUT"].max_per_target is None
        assert limits["IN"].max_per_source is None
        assert limits["IN"].max_per_target == 1

    def test_required_datatype_cardinality_and_integer_enumeration_are_imported(self):
        """Datatype minimum cardinality and integer values survive import."""
        result = loads_owl("""
            @prefix ex: <https://example.test/data#> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .
            @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
            @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

            ex:A a owl:Class ; rdfs:subClassOf [
                a owl:Restriction ; owl:onProperty ex:count ;
                owl:cardinality "1"^^xsd:nonNegativeInteger
            ] .
            ex:count a owl:DatatypeProperty ; rdfs:domain ex:A ;
                rdfs:range [ a rdfs:Datatype ; owl:oneOf
                    ("2"^^xsd:integer "7"^^xsd:integer) ] .
        """)
        prop = result.schema.entities[0].properties["count"]

        assert prop.type == "integer"
        assert prop.required is True
        assert prop.enum == ["2", "7"]

    def test_non_xsd_type_with_xsd_local_name_is_widened_to_string(self):
        """A foreign datatype cannot gain meaning from its local name."""
        result = loads_owl("""
            @prefix ex: <https://example.test/types#> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

            ex:A a owl:Class .
            ex:value a owl:DatatypeProperty ; rdfs:domain ex:A ;
                rdfs:range <https://foreign.test/types#integer> .
        """)

        assert result.schema.entities[0].properties["value"].type == "string"

    def test_urn_classes_and_inherited_datatype_properties_import(self):
        """URN local names import, and superclass properties reach subclasses."""
        result = loads_owl("""
            @prefix owl: <http://www.w3.org/2002/07/owl#> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

            <urn:example:Parent> a owl:Class .
            <urn:example:Child> a owl:Class ;
                rdfs:subClassOf <urn:example:Parent> .
            <urn:example:hasCode> a owl:DatatypeProperty ;
                rdfs:domain <urn:example:Parent> .
        """)

        child = next(
            entity for entity in result.schema.entities if entity.label == "Child"
        )
        assert "hasCode" in child.properties

    def test_timezone_date_enum_is_normalized_to_schema_date(self):
        """Timezone suffixes are removed from date enum lexical values."""
        result = loads_owl("""
            @prefix ex: <https://example.test/dates#> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
            @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

            ex:A a owl:Class .
            ex:date a owl:DatatypeProperty ; rdfs:domain ex:A ;
                rdfs:range [ owl:oneOf ("2025-01-02Z"^^xsd:date) ] .
        """)

        date = result.schema.entities[0].properties["date"]
        assert date.enum == ["2025-01-02"]

    def test_cyclic_union_list_fails_with_format_error(self):
        """A cyclic RDF list fails rather than keeping the import stuck."""
        with pytest.raises(SchemaFormatError, match="cyclic RDF list"):
            loads_owl("""
                @prefix ex: <https://example.test/cycle#> .
                @prefix owl: <http://www.w3.org/2002/07/owl#> .
                @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
                @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

                ex:A a owl:Class .
                ex:p a owl:ObjectProperty ; rdfs:domain [ owl:unionOf _:list ] .
                _:list rdf:first ex:A ; rdf:rest _:list .
            """)

    def test_ontology_comments_are_not_used_as_schema_descriptions(self):
        """Untrusted comments cannot become instruction-bearing descriptions."""
        result = loads_owl("""
            @prefix ex: <https://example.test/comments#> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

            ex:A a owl:Class ; rdfs:comment "Tagged"@en ;
                rdfs:comment "Preferred" .
        """)

        assert result.schema.entities[0].description == "A"

    def test_partial_domain_restriction_does_not_impose_a_global_relation_limit(self):
        """A limit on only one of multiple sources is not globalized."""
        result = loads_owl("""
            @prefix ex: <https://example.test/scoped#> .
            @prefix owl: <http://www.w3.org/2002/07/owl#> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
            @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

            ex:A a owl:Class ; rdfs:subClassOf [
                a owl:Restriction ; owl:onProperty ex:links ;
                owl:maxCardinality "1"^^xsd:nonNegativeInteger
            ] .
            ex:B a owl:Class . ex:C a owl:Class .
            ex:links a owl:ObjectProperty ;
                rdfs:domain [ owl:unionOf (ex:A ex:B) ] ; rdfs:range ex:C .
        """)

        assert result.schema.relations[0].cardinality.max_per_source is None

    @pytest.mark.parametrize(
        "class_iris",
        [
            "<https://example.test/classes#bad-name>",
            "<https://example.test/one#Same> <https://example.test/two#Same>",
        ],
    )
    def test_invalid_or_colliding_class_local_names_fail(self, class_iris):
        """Invalid and duplicate local class labels are rejected."""
        declarations = " .\n            ".join(
            f"{iri} a owl:Class" for iri in class_iris.split()
        )
        with pytest.raises((SchemaFormatError, SchemaLoadError)):
            loads_owl(f"""
                @prefix owl: <http://www.w3.org/2002/07/owl#> .
                {declarations} .
            """)
