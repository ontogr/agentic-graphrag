"""Exercise OWL Turtle imports through the public schema-loading APIs."""

import logging
import subprocess
import sys

import pytest

from agrag.schema import SchemaLoadError, dump_schema, load_schema
from agrag.schema.formats import (
    SchemaFormatError,
    SchemaFormatMissingExtraError,
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
                rdfs:subClassOf <urn:example:Parent>, [
                    a owl:Restriction ; owl:onProperty <urn:example:hasCode> ;
                    owl:maxCardinality 1
                ] .
            <urn:example:hasCode> a owl:DatatypeProperty ;
                rdfs:domain <urn:example:Parent> .
        """)

        child = next(
            entity for entity in result.schema.entities if entity.label == "Child"
        )
        assert "hasCode" in child.properties
        assert any(warning.code == "restriction_ignored" for warning in result.warnings)

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


PREFIXES = """
@prefix ex: <https://example.test/ontology#> .
@prefix other: <https://other.test/ontology#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:A a owl:Class .
ex:B a owl:Class .
ex:C a owl:Class .
"""


def _import(body: str):
    return loads_owl(PREFIXES + body)


def _codes(result) -> list[str]:
    return [warning.code for warning in result.warnings]


class TestOwlWarnings:
    """Lossy or unsupported Turtle input is reported, never dropped silently."""

    @pytest.mark.parametrize(
        ("body", "code"),
        [
            ('ex:A rdfs:comment "one", "two" .', "comment_alternatives_dropped"),
            (
                "ex:p a owl:DatatypeProperty ; rdfs:domain ex:A ; "
                'rdfs:range [ owl:oneOf ( "a" 1 ) ] .',
                "enum_types_widened",
            ),
            (
                "ex:p a owl:DatatypeProperty ; rdfs:domain ex:A ; "
                "rdfs:range xsd:string, xsd:integer .",
                "multiple_ranges_narrowed",
            ),
            (
                "ex:p a owl:DatatypeProperty ; rdfs:domain ex:A, ex:B ; "
                "rdfs:range xsd:string .",
                "multiple_domains_unioned",
            ),
            (
                "ex:bad-name a owl:DatatypeProperty ; rdfs:domain ex:A ; "
                "rdfs:range xsd:string .",
                "construct_ignored",
            ),
            (
                "ex:p a owl:DatatypeProperty ; rdfs:domain ex:A ; "
                "rdfs:range xsd:string . "
                "other:p a owl:DatatypeProperty ; rdfs:domain ex:A ; "
                "rdfs:range xsd:string .",
                "property_name_collision",
            ),
            (
                "ex:p a owl:DatatypeProperty ; rdfs:domain ex:A ; "
                "rdfs:range xsd:string . "
                "ex:A rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:p ; "
                "owl:maxCardinality 0 ] .",
                "zero_max_cardinality_dropped",
            ),
            (
                "ex:p a owl:DatatypeProperty ; rdfs:domain ex:A ; "
                "rdfs:range xsd:string . "
                "ex:A rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:p ; "
                "owl:maxCardinality 3 ] .",
                "max_cardinality_dropped",
            ),
            (
                "ex:r a owl:ObjectProperty ; rdfs:domain ex:A ; "
                "rdfs:range ex:B, ex:C .",
                "conjunctive_endpoints_unsupported",
            ),
            (
                "ex:worksFor a owl:ObjectProperty ; rdfs:domain ex:A ; "
                "rdfs:range ex:B .",
                "relation_label_normalized",
            ),
            (
                "ex:works-for a owl:ObjectProperty ; rdfs:domain ex:A ; "
                "rdfs:range ex:B .",
                "construct_ignored",
            ),
            ("ex:A rdfs:subClassOf ex:Missing .", "unknown_parent"),
            ('ex:A skos:altLabel "Alpha" .', "construct_ignored"),
            ("ex:A owl:disjointWith ex:B .", "construct_ignored"),
        ],
    )
    def test_construct_produces_its_warning(self, body, code):
        """Each lossy construct adds a warning with its documented code."""
        assert code in _codes(_import(body))

    @pytest.mark.parametrize(
        ("restriction", "code"),
        [
            ("owl:cardinality 2", "min_cardinality_dropped"),
            ("owl:minCardinality 1", "min_cardinality_dropped"),
            ("owl:qualifiedCardinality 2", "restriction_ignored"),
            ("owl:maxCardinality 0", "restriction_ignored"),
        ],
    )
    def test_relation_cardinality_restrictions_are_reported(self, restriction, code):
        """Relation limits the model cannot store add a warning."""
        result = _import(
            "ex:r a owl:ObjectProperty ; rdfs:domain ex:A ; rdfs:range ex:B . "
            "ex:A rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:r ; "
            f"{restriction} ] ."
        )

        assert code in _codes(result)

    def test_relation_with_several_comments_reports_dropped_alternatives(self):
        """Extra comments on a relation add a warning."""
        result = _import(
            "ex:r a owl:ObjectProperty ; rdfs:domain ex:A ; rdfs:range ex:B ; "
            'rdfs:comment "one", "two" .'
        )

        assert "comment_alternatives_dropped" in _codes(result)

    def test_mixed_range_and_enum_types_are_read_as_strings(self):
        """Mixed ranges and mixed enum types fall back to a string property."""
        result = _import(
            "ex:p a owl:DatatypeProperty ; rdfs:domain ex:A ; "
            "rdfs:range xsd:string, xsd:integer . "
            "ex:q a owl:DatatypeProperty ; rdfs:domain ex:B ; "
            'rdfs:range [ owl:oneOf ( "a" 1 ) ] .'
        )
        entities = {entity.label: entity for entity in result.schema.entities}

        assert entities["A"].properties["p"].type == "string"
        assert entities["B"].properties["q"].type == "string"
        assert entities["B"].properties["q"].enum == ["1", "a"]

    def test_diamond_inheritance_gives_each_property_once(self):
        """A class reachable through two parents inherits each property once."""
        result = _import(
            "ex:B rdfs:subClassOf ex:A . ex:C rdfs:subClassOf ex:A . "
            "ex:D a owl:Class ; rdfs:subClassOf ex:B, ex:C . "
            "ex:p a owl:DatatypeProperty ; rdfs:domain ex:A ; "
            "rdfs:range xsd:string ."
        )
        entities = {entity.label: entity for entity in result.schema.entities}

        assert list(entities["D"].properties) == ["p"]

    def test_symmetric_functional_relation_is_imported_in_both_directions(self):
        """A symmetric relation gets reversed patterns and matching limits."""
        result = _import(
            "ex:knows a owl:ObjectProperty, owl:SymmetricProperty, "
            "owl:FunctionalProperty ; rdfs:domain ex:A ; rdfs:range ex:B ."
        )
        relation = result.schema.relations[0]

        assert {tuple(pattern) for pattern in relation.patterns} == {
            ("A", "B"),
            ("B", "A"),
        }
        assert relation.cardinality.max_per_source == 1
        assert relation.cardinality.max_per_target == 1

    def test_malformed_rdf_list_fails_with_format_error(self):
        """A list node without a rest link cannot be read."""
        with pytest.raises(SchemaFormatError, match="malformed RDF list"):
            _import(
                "ex:p a owl:DatatypeProperty ; rdfs:domain ex:A ; "
                'rdfs:range [ owl:oneOf [ rdf:first "a" ] ] .'
            )

    def test_text_input_must_be_a_string(self):
        """Passing bytes instead of text is a type error."""
        with pytest.raises(TypeError, match="text must be a string"):
            loads_owl(b"@prefix ex: <https://example.test/> .")

    def test_unreadable_turtle_file_fails_with_format_error(self, tmp_path):
        """A missing file and a non UTF-8 file both fail as format errors."""
        broken = tmp_path / "broken.ttl"
        broken.write_bytes(b"\xff\xfe\x00")

        with pytest.raises(SchemaFormatError, match="cannot read Turtle file"):
            load_owl(tmp_path / "missing.ttl")
        with pytest.raises(SchemaFormatError, match="cannot read Turtle file"):
            load_owl(broken)

    def test_missing_extra_error_names_the_extra(self):
        """The error for a missing optional package gives the install command."""
        error = SchemaFormatMissingExtraError("OWL Turtle import", "schema-formats")

        assert (error.component, error.extra) == ("OWL Turtle import", "schema-formats")
        assert "agentic-graphrag[schema-formats]" in str(error)


class TestLoadSchemaTurtle:
    """``load_schema`` reports Turtle problems as schema load errors."""

    def test_unreadable_turtle_path_raises_schema_load_error(self, tmp_path):
        """A missing .ttl file names the path in the error."""
        path = tmp_path / "missing.ttl"

        with pytest.raises(SchemaLoadError, match="missing.ttl"):
            load_schema(str(path))

    def test_invalid_turtle_file_raises_schema_load_error(self, tmp_path):
        """Broken Turtle in a file is a schema load error that names the file."""
        path = tmp_path / "broken.ttl"
        path.write_text("not Turtle [")

        with pytest.raises(SchemaLoadError, match="invalid Turtle"):
            load_schema(path)

    def test_reserved_label_in_turtle_file_raises_schema_load_error(self, tmp_path):
        """Schema rules still apply to classes read from a Turtle file."""
        path = tmp_path / "reserved.ttl"
        path.write_text(
            "@prefix ex: <https://example.test/> . "
            "@prefix owl: <http://www.w3.org/2002/07/owl#> . "
            "ex:Chunk a owl:Class ."
        )

        with pytest.raises(SchemaLoadError, match="Chunk"):
            load_schema(path)

    def test_turtle_path_in_extends_is_resolved_next_to_the_file(self, tmp_path):
        """A schema file can extend a Turtle file by relative path."""
        (tmp_path / "base.ttl").write_text(ONTOLOGY)
        child = tmp_path / "child.yaml"
        child.write_text("extends: base.ttl\nentities:\n  Distributor: A reseller.\n")

        schema = load_schema(child)

        assert {entity.label for entity in schema.entities} >= {
            "Supplier",
            "Distributor",
        }
