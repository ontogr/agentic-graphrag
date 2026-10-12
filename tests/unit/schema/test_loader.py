"""Tests for load_schema: sources, names, errors and extends."""

import json
from pathlib import Path

import pytest

from agrag.common.data_models.graph_schema import (
    Cardinality,
    EntityType,
    GraphSchema,
    PropertySpec,
    RelationType,
)
from agrag.schema import SchemaLoadError, dump_schema, load_schema


def _base() -> GraphSchema:
    """Build the base schema the extends tests build on."""
    return GraphSchema(
        name="base",
        version="3",
        entities=[
            EntityType(
                label="Person",
                description="A person.",
                properties={
                    "email": PropertySpec(type="string", required=True),
                    "born": PropertySpec(type="integer"),
                },
            ),
            EntityType(label="Organization", description="A company."),
            EntityType(label="Location", description="A place."),
        ],
        relations=[
            RelationType(
                label="WORKS_FOR",
                description="Employment.",
                patterns=[("Person", "Organization")],
            ),
            RelationType(
                label="LOCATED_IN",
                description="Place of an organization.",
                patterns=[("Organization", "Location")],
            ),
        ],
    )


def _labels(schema: GraphSchema) -> list[str]:
    """Return the entity labels in schema order."""
    return [entity.label for entity in schema.entities]


def _error(source, **kwargs) -> SchemaLoadError:
    """Load a bad source and return the raised error."""
    with pytest.raises(SchemaLoadError) as caught:
        load_schema(source, **kwargs)
    return caught.value


def _paths(error: SchemaLoadError) -> list[str]:
    """Return the issue paths of an error."""
    return [issue.path for issue in error.issues]


class TestSources:
    """load_schema reads every accepted source into a GraphSchema."""

    def test_label_list(self):
        """A label list gives label-only types with default name and version."""
        schema = load_schema(["Person", "Vendor"])

        assert _labels(schema) == ["Person", "Vendor"]
        assert schema.relations == []
        assert (schema.name, schema.version) == ("custom", "1")

    def test_list_with_strings_and_triples(self):
        """Relation strings and triples in a native list become relations."""
        schema = load_schema(
            [
                "Person",
                "Vendor",
                "Person-WORKS_FOR->Vendor",
                ("Vendor", "SELLS_TO", "Person"),
            ]
        )

        assert [r.label for r in schema.relations] == ["WORKS_FOR", "SELLS_TO"]

    def test_dict(self):
        """A dict source keeps its name and turns a numeric version into text."""
        schema = load_schema(
            {
                "name": "x",
                "version": 7,
                "entities": {"A": "An a."},
                "relations": ["A-R->A"],
            }
        )

        assert (schema.name, schema.version) == ("x", "7")

    def test_json_text(self):
        """JSON text is parsed and loaded like a dict."""
        schema = load_schema(json.dumps({"entities": ["A"]}))

        assert _labels(schema) == ["A"]

    def test_json_file_takes_the_stem_as_name(self, tmp_path: Path):
        """A file source names the schema after the file stem."""
        path = tmp_path / "vendors.json"
        path.write_text(json.dumps({"entities": ["A"]}))

        assert load_schema(path).name == "vendors"
        assert load_schema(str(path)).name == "vendors"

    def test_yaml_file(self, tmp_path: Path):
        """A YAML file reads hierarchy, version and relation strings."""
        path = tmp_path / "vendors.yaml"
        path.write_text(
            "version: 2\n"
            "entities:\n"
            "  Vendor:\n"
            "    description: A seller.\n"
            "    parents: [Organization]\n"
            "  Organization: A company.\n"
            "relations:\n"
            "  - Vendor-SELLS_TO->Organization\n"
        )

        schema = load_schema(path)

        assert schema.ancestors("Vendor") == ["Organization"]
        assert schema.version == "2"

    def test_graph_schema_is_copied(self):
        """A GraphSchema source is returned as a deep copy."""
        source = _base()

        copy = load_schema(source)

        assert copy == source
        assert copy is not source

    def test_explicit_name_wins(self, tmp_path: Path):
        """A name inside a file wins over the file stem."""
        path = tmp_path / "file.json"
        path.write_text(json.dumps({"name": "chosen", "entities": ["A"]}))

        assert load_schema(path).name == "chosen"

    def test_unknown_name(self):
        """A string that is not a path or known name is rejected."""
        error = _error("defalt")

        assert error.issues[0].message.startswith("unknown schema 'defalt'.")

    def test_missing_file(self, tmp_path: Path):
        """A missing file reports the path as the source."""
        error = _error(tmp_path / "none.json")

        assert error.issues[0].message == "the file does not exist."
        assert error.source == str(tmp_path / "none.json")

    def test_unsupported_suffix(self, tmp_path: Path):
        """A suffix other than json or yaml is rejected."""
        path = tmp_path / "s.toml"
        path.write_text("x = 1")

        assert "cannot read '.toml' files" in _error(path).issues[0].message

    def test_invalid_json(self):
        """Broken JSON text reports the parser position."""
        assert (
            _error('{"entities": [}')
            .issues[0]
            .message.startswith("invalid JSON at line")
        )

    def test_invalid_yaml(self, tmp_path: Path):
        """Broken YAML reports the parser message."""
        path = tmp_path / "s.yaml"
        path.write_text("entities: [a")

        assert _error(path).issues[0].message.startswith("invalid YAML:")

    def test_file_holding_a_string(self, tmp_path: Path):
        """A file that holds neither a mapping nor a list is rejected."""
        path = tmp_path / "s.yaml"
        path.write_text("just text")

        assert _error(path).issues[0].message == (
            "a schema file must hold a mapping or a list, got str."
        )


class TestErrors:
    """load_schema reports every problem with its path in one error."""

    def test_unknown_parent_has_the_exact_path(self):
        """An unknown parent reports its index and a spelling hint."""
        error = _error(
            {
                "entities": [
                    "A",
                    "B",
                    {"label": "Vendor", "parents": ["Organizaton"]},
                    "Organization",
                ]
            }
        )

        assert _paths(error) == ["entities[2].parents[0]"]
        assert "parent 'Organizaton' is not a declared entity type" in str(error)
        assert "Did you mean 'Organization'?" in str(error)

    def test_every_problem_is_reported_in_one_error(self):
        """Reading errors from unrelated keys aggregate into one error."""
        error = _error(
            {
                "dtype": "fp16",
                "entities": [
                    {"label": "A", "parnts": []},
                    {"label": "B", "threshold": 0.5},
                ],
                "relations": ["not a relation", "A-R->B"],
            }
        )

        assert sorted(_paths(error)) == sorted(
            ["dtype", "entities[0].parnts", "entities[1].threshold", "relations[0]"]
        )

    def test_pattern_end_error_names_the_relation_path(self):
        """An undeclared pattern end reports the relation pattern path."""
        error = _error({"entities": ["A"], "relations": ["A-R->Missing"]})

        assert _paths(error) == ["relations[0].patterns[0]"]
        assert "pattern end 'Missing' is not a declared entity type" in str(error)

    def test_header_counts_errors_and_names_the_file(self, tmp_path: Path):
        """The header counts the errors and names the file."""
        path = tmp_path / "s.json"
        path.write_text(json.dumps({"entites": ["A"], "entities": 5}))

        message = str(_error(path))

        assert message.startswith(f"invalid schema in {path} (2 errors):")

    def test_settings_key_message(self):
        """An extraction setting key names ExtractionSettings."""
        error = _error({"entities": ["A"], "label_thresholds": {"A": 0.6}})

        assert "'label_thresholds' is an extraction setting" in str(error)
        assert "ExtractionSettings" in str(error)

    def test_model_error_maps_to_the_source_path(self):
        """A schema model error is mapped back to the source path."""
        error = _error({"entities": ["A", "Section"]})

        assert _paths(error) == ["entities[1]"]
        assert "reserved label" in str(error)

    def test_missing_patterns(self):
        """A relation with no patterns reports its own path."""
        error = _error({"entities": ["A"], "relations": [{"label": "R"}]})

        assert _paths(error) == ["relations[0]"]
        assert error.issues[0].message.startswith("a relation needs 'patterns'.")

    def test_duplicate_entity(self):
        """A repeated entity label names the first declaration."""
        error = _error({"entities": ["A", {"label": "A"}]})

        assert _paths(error) == ["entities[1]"]
        assert error.issues[0].message == (
            "duplicate entity type 'A'. First declared at entities[0]."
        )

    def test_override_without_base(self):
        """An override with no base reports the override key."""
        error = _error({"entities": [{"label": "A", "override": True}]})

        assert _paths(error) == ["entities[0].override"]

    def test_exclude_without_base(self):
        """Exclude with no base reports the exclude key."""
        error = _error({"entities": ["A"], "exclude": ["A"]})

        assert _paths(error) == ["exclude"]


class TestExtends:
    """extends builds on a base schema with override, exclude and add_patterns."""

    def test_child_adds_a_type_and_keeps_the_base(self):
        """A child adds types while the base types and relations stay."""
        schema = load_schema({"entities": {"Vendor": "A seller."}}, extends=_base())

        assert _labels(schema) == ["Person", "Organization", "Location", "Vendor"]
        assert [r.label for r in schema.relations] == ["WORKS_FOR", "LOCATED_IN"]
        assert schema.name == "custom"
        assert schema.version == "1"

    def test_extends_key_in_the_file(self, tmp_path: Path):
        """A base named in the file is loaded relative to the source."""
        base = tmp_path / "base.json"
        base.write_text(json.dumps(dump_schema(_base())))
        child = tmp_path / "child.json"
        child.write_text(json.dumps({"extends": str(base), "entities": ["Vendor"]}))

        assert "Vendor" in _labels(load_schema(child))

    def test_extends_set_twice(self):
        """Setting extends in the call and the file is an error."""
        error = _error({"extends": "x.json"}, extends=_base())

        assert _paths(error) == ["extends"]

    def test_extends_cycle(self, tmp_path: Path):
        """A base chain that loops back reports the cycle."""
        a, b = tmp_path / "a.json", tmp_path / "b.json"
        a.write_text(json.dumps({"extends": str(b), "entities": ["A"]}))
        b.write_text(json.dumps({"extends": str(a), "entities": ["B"]}))

        assert "'extends' loops back to this file" in _error(a).issues[0].message

    def test_redeclared_type_is_an_error(self):
        """Redeclaring a base type without override is an error."""
        error = _error({"entities": [{"label": "Person"}]}, extends=_base())

        assert _paths(error) == ["entities[0]"]
        assert error.issues[0].message == (
            "entity type 'Person' is already defined by the base schema 'base'. "
            "Add 'override: true' to replace it, or choose another label."
        )

    def test_redeclared_relation_is_an_error(self):
        """Redeclaring a base relation without override is an error."""
        error = _error({"relations": ["Person-WORKS_FOR->Location"]}, extends=_base())

        assert "relation type 'WORKS_FOR' is already defined" in str(error)

    def test_override_replaces_in_place(self):
        """An override keeps the base position and replaces the body."""
        child = {
            "entities": [
                {
                    "label": "Organization",
                    "override": True,
                    "description": "A firm.",
                    "properties": {"founded": "integer"},
                }
            ]
        }

        schema = load_schema(child, extends=_base())

        assert _labels(schema) == ["Person", "Organization", "Location"]
        assert _labels(schema)[1] == "Organization"
        assert schema.entities[1].description == "A firm."
        assert "founded" in schema.entities[1].properties

    def test_override_of_a_missing_type(self):
        """An override of a type the base lacks names the fix."""
        error = _error(
            {"entities": [{"label": "Vendor", "override": True}]}, extends=_base()
        )

        assert error.issues[0].message == (
            "'override' is set but the base schema 'base' has no entity type "
            "'Vendor'. Remove 'override'."
        )

    @pytest.mark.parametrize(
        ("properties", "fragment"),
        [
            ({"born": "integer"}, "drops property 'email'"),
            (
                {"email": {"type": "string"}, "born": "integer"},
                "makes property 'email' optional",
            ),
            (
                {"email": {"type": "integer", "required": True}, "born": "integer"},
                "changes the type of property 'email'",
            ),
        ],
    )
    def test_override_may_not_loosen(self, properties, fragment):
        """An override that drops, loosens or retypes a property is an error."""
        error = _error(
            {
                "entities": [
                    {"label": "Person", "override": True, "properties": properties}
                ]
            },
            extends=_base(),
        )

        assert fragment in error.issues[0].message

    def test_override_may_not_widen_an_enum(self):
        """An override that widens an enum is an error."""
        base = GraphSchema(
            name="b",
            version="1",
            entities=[
                EntityType(
                    label="Ticket",
                    description="",
                    properties={
                        "state": PropertySpec(type="string", enum=["open", "done"])
                    },
                )
            ],
            relations=[],
        )

        error = _error(
            {
                "entities": [
                    {
                        "label": "Ticket",
                        "override": True,
                        "properties": {
                            "state": {
                                "type": "string",
                                "enum": ["open", "done", "lost"],
                            }
                        },
                    }
                ]
            },
            extends=base,
        )

        assert "widens the allowed values of property 'state'" in str(error)

    def test_override_may_narrow(self):
        """An override that tightens a property is allowed."""
        schema = load_schema(
            {
                "entities": [
                    {
                        "label": "Person",
                        "override": True,
                        "properties": {
                            "email": {"type": "string", "required": True},
                            "born": {"type": "integer", "required": True},
                        },
                    }
                ]
            },
            extends=_base(),
        )

        assert schema.entities[0].properties["born"].required is True

    def test_override_of_a_relation_may_change_patterns(self):
        """Relation patterns may change freely on an override."""
        schema = load_schema(
            {
                "relations": [
                    {
                        "label": "LOCATED_IN",
                        "override": True,
                        "description": "x",
                        "patterns": ["Person->Location"],
                    }
                ]
            },
            extends=_base(),
        )

        located = {r.label: r for r in schema.relations}["LOCATED_IN"]
        assert [tuple(p) for p in located.patterns] == [("Person", "Location")]

    def test_relation_override_may_not_loosen_cardinality(self):
        """An override that removes a cardinality limit is an error."""
        base = GraphSchema(
            name="b",
            version="1",
            entities=[
                EntityType(label="Person", description=""),
                EntityType(label="Software", description=""),
            ],
            relations=[
                RelationType(
                    label="OWNS",
                    description="",
                    patterns=[("Person", "Software")],
                    cardinality=Cardinality(max_per_source=3),
                )
            ],
        )

        error = _error(
            {
                "relations": [
                    {
                        "label": "OWNS",
                        "override": True,
                        "patterns": ["Person->Software"],
                    }
                ]
            },
            extends=base,
        )

        assert (
            "removes the cardinality limit on the source side"
            in error.issues[0].message
        )

    def test_relation_override_may_tighten_cardinality(self):
        """An override that lowers a cardinality limit is allowed."""
        base = GraphSchema(
            name="b",
            version="1",
            entities=[
                EntityType(label="Person", description=""),
                EntityType(label="Software", description=""),
            ],
            relations=[
                RelationType(
                    label="OWNS",
                    description="",
                    patterns=[("Person", "Software")],
                    cardinality=Cardinality(max_per_source=3),
                )
            ],
        )

        schema = load_schema(
            {
                "relations": [
                    {
                        "label": "OWNS",
                        "override": True,
                        "patterns": ["Person->Software"],
                        "cardinality": {"max_per_source": 1},
                    }
                ]
            },
            extends=base,
        )

        assert schema.relations[0].cardinality.max_per_source == 1

    def test_add_patterns_extends_a_base_relation(self):
        """add_patterns appends pairs and keeps the base description."""
        schema = load_schema(
            {
                "entities": ["Facility"],
                "relations": [
                    {"label": "LOCATED_IN", "add_patterns": ["Facility->Location"]}
                ],
            },
            extends=_base(),
        )

        located = {r.label: r for r in schema.relations}["LOCATED_IN"]
        assert ("Facility", "Location") in [tuple(p) for p in located.patterns]
        assert located.description == "Place of an organization."

    def test_add_patterns_needs_a_base_relation(self):
        """add_patterns for a relation the base lacks is an error."""
        error = _error(
            {"relations": [{"label": "NEW", "add_patterns": ["Person->Location"]}]},
            extends=_base(),
        )

        assert error.issues[0].message == (
            "'add_patterns' needs a relation in the base schema 'base'; "
            "'NEW' is not one."
        )

    def test_add_patterns_with_patterns(self):
        """Combining patterns and add_patterns on one item is an error."""
        error = _error(
            {
                "relations": [
                    {
                        "label": "LOCATED_IN",
                        "patterns": ["Person->Location"],
                        "add_patterns": ["Person->Location"],
                    }
                ]
            },
            extends=_base(),
        )

        assert "not both" in str(error)

    def test_exclude_removes_the_type_and_its_patterns(self):
        """Excluding a type drops the relations that used only it."""
        schema = load_schema({"exclude": ["Location"]}, extends=_base())

        assert _labels(schema) == ["Person", "Organization"]
        assert [r.label for r in schema.relations] == ["WORKS_FOR"]

    def test_exclude_keeps_a_relation_with_other_patterns(self):
        """A relation keeps the patterns that avoid the excluded type."""
        base = load_schema(["A", "B", "C", "A|B-R->C|A"], extends=None)

        schema = load_schema({"exclude": ["C"]}, extends=base)

        assert [tuple(p) for p in schema.relations[0].patterns] == [
            ("A", "A"),
            ("B", "A"),
        ]

    def test_exclude_removes_a_relation_by_label(self):
        """A relation label in exclude removes the whole relation."""
        schema = load_schema({"exclude": ["WORKS_FOR"]}, extends=_base())

        assert [r.label for r in schema.relations] == ["LOCATED_IN"]

    def test_exclude_unknown_label(self):
        """Excluding a label the base lacks is an error."""
        error = _error({"exclude": ["Nope"]}, extends=_base())

        assert _paths(error) == ["exclude[0]"]
        assert error.issues[0].message == (
            "cannot exclude 'Nope': the base schema has no entity type or "
            "relation type with that label."
        )

    def test_exclude_a_parent_of_a_base_type(self):
        """Excluding a base type a base child still needs is an error."""
        base = load_schema(
            {
                "entities": {
                    "Organization": None,
                    "Vendor": {"parents": ["Organization"]},
                }
            }
        )

        error = _error({"exclude": ["Organization"]}, extends=base)

        assert error.issues[0].message == (
            "cannot exclude 'Organization': base type 'Vendor' has it as a parent. "
            "Exclude 'Vendor' as well."
        )

    def test_exclude_both_parent_and_child(self):
        """Excluding a parent and its child leaves no entity types."""
        base = load_schema(
            {
                "entities": {
                    "Organization": None,
                    "Vendor": {"parents": ["Organization"]},
                }
            }
        )

        schema = load_schema({"exclude": ["Organization", "Vendor"]}, extends=base)

        assert schema.entities == []

    def test_declared_and_excluded(self):
        """A label that is both excluded and declared is an error."""
        error = _error(
            {"exclude": ["Location"], "entities": [{"label": "Location"}]},
            extends=_base(),
        )

        assert "is excluded from the base schema and declared here" in str(error)

    def test_child_relation_using_an_excluded_type(self):
        """A new relation that names an excluded type is an error."""
        error = _error(
            {"exclude": ["Location"], "relations": ["Person-LIVES_IN->Location"]},
            extends=_base(),
        )

        assert _paths(error) == ["relations[0].patterns[0]"]

    def test_child_parent_may_be_a_base_type(self):
        """A new type may name a base type as its parent."""
        schema = load_schema(
            {"entities": {"Vendor": {"parents": ["Organization"]}}}, extends=_base()
        )

        assert schema.ancestors("Vendor") == ["Organization"]

    def test_chained_extends_through_a_path(self, tmp_path: Path):
        """A chain of file extends resolves depth first in order."""
        base = tmp_path / "base.json"
        base.write_text(json.dumps(dump_schema(_base())))
        middle = tmp_path / "middle.json"
        middle.write_text(json.dumps({"extends": str(base), "entities": ["Vendor"]}))

        schema = load_schema({"entities": ["Carrier"]}, extends=middle)

        assert _labels(schema)[-2:] == ["Vendor", "Carrier"]

    def test_override_logs_a_warning(self, caplog):
        """Replacing a base item logs a warning on the loader logger."""
        with caplog.at_level("WARNING", logger="agrag.schema.loader"):
            load_schema(
                {
                    "entities": [
                        {"label": "Organization", "override": True, "description": "x"}
                    ]
                },
                extends=_base(),
            )

        assert "replaces the base entity type 'Organization'" in caplog.text


class TestReviewFixes:
    """Regression tests for the review findings on the schema loader."""

    def test_mode_key_names_extraction_settings(self):
        """A top-level mode key points at ExtractionSettings."""
        error = _error({"entities": ["A"], "mode": "hybrid"})

        assert "'mode' is an extraction setting" in str(error)
        assert "ExtractionSettings" in str(error)

    def test_invalid_utf8_file_reports_schema_error(self, tmp_path: Path):
        """A file with invalid UTF-8 raises SchemaLoadError with the source."""
        path = tmp_path / "s.json"
        path.write_bytes(b'{"entities": ["A\xff"]}')

        error = _error(path)

        assert error.source == str(path)

    def test_blank_triple_endpoint_is_an_error(self):
        """A relation triple with a blank endpoint is rejected."""
        error = _error(["A", ("A", "R", "")])

        assert _paths(error) == ["relations[0]"]
        assert "empty target" in str(error)

    def test_empty_patterns_list_is_an_error(self):
        """A relation with an empty patterns list is rejected."""
        error = _error(
            {"entities": ["A"], "relations": [{"label": "R", "patterns": []}]}
        )

        assert _paths(error) == ["relations[0]"]
        assert "needs 'patterns'" in str(error)

    def test_empty_patterns_map_is_an_error(self):
        """A mapping relation with an empty patterns list is rejected."""
        error = _error({"entities": ["A"], "relations": {"R": []}})

        assert _paths(error) == ["relations.R"]
        assert "needs 'patterns'" in str(error)

    def test_duplicate_property_is_an_error(self):
        """A repeated property name names the first declaration."""
        error = _error({"entities": [{"label": "A", "properties": ["email", "email"]}]})

        assert _paths(error) == ["entities[0].properties[1]"]
        assert "duplicate property 'email'" in str(error)

    def test_add_patterns_with_cardinality_is_an_error(self):
        """Cardinality cannot be combined with add_patterns."""
        error = _error(
            {
                "relations": [
                    {
                        "label": "LOCATED_IN",
                        "add_patterns": ["Person->Location"],
                        "cardinality": {"max_per_source": 1},
                    }
                ]
            },
            extends=_base(),
        )

        assert "cannot be combined" in str(error)

    def test_file_extends_resolves_beside_child(self, tmp_path: Path):
        """A relative extends in a file resolves against the child directory."""
        folder = tmp_path / "schemas"
        folder.mkdir()
        (folder / "base.json").write_text(json.dumps(dump_schema(_base())))
        child = folder / "child.json"
        child.write_text(json.dumps({"extends": "base.json", "entities": ["Vendor"]}))

        assert "Vendor" in _labels(load_schema(child))

    def test_in_memory_extends_cycle_is_an_error(self):
        """A dict that extends itself reports a cycle instead of recursing."""
        source: dict = {"entities": ["A"]}
        source["extends"] = source

        error = _error(source)

        assert "loops back" in str(error)

    def test_relation_declared_and_excluded_is_an_error(self):
        """A relation that is both excluded and declared is an error."""
        error = _error(
            {
                "exclude": ["WORKS_FOR"],
                "relations": [
                    {"label": "WORKS_FOR", "patterns": ["Person->Organization"]}
                ],
            },
            extends=_base(),
        )

        assert "is excluded from the base schema and declared here" in str(error)

    def test_malformed_enum_override_reports_schema_error(self):
        """An unhashable enum in an override does not escape SchemaLoadError."""
        error = _error(
            {
                "entities": [
                    {
                        "label": "Person",
                        "override": True,
                        "properties": {
                            "email": {
                                "type": "string",
                                "required": True,
                                "enum": [["a"]],
                            },
                            "born": "integer",
                        },
                    }
                ]
            },
            extends=_base(),
        )

        assert isinstance(error, SchemaLoadError)

    def test_quoted_cardinality_override_tightens(self):
        """A quoted tightening limit loads without escaping SchemaLoadError."""
        base = GraphSchema(
            name="b",
            version="1",
            entities=[
                EntityType(label="Person", description=""),
                EntityType(label="Software", description=""),
            ],
            relations=[
                RelationType(
                    label="OWNS",
                    description="",
                    patterns=[("Person", "Software")],
                    cardinality=Cardinality(max_per_source=3),
                )
            ],
        )
        schema = load_schema(
            {
                "relations": [
                    {
                        "label": "OWNS",
                        "override": True,
                        "patterns": ["Person->Software"],
                        "cardinality": {"max_per_source": "1"},
                    }
                ]
            },
            extends=base,
        )

        assert schema.relations[0].cardinality.max_per_source == 1

    def test_quoted_cardinality_loosening_is_an_error(self):
        """A quoted loosening limit is rejected like a plain one."""
        base = GraphSchema(
            name="b",
            version="1",
            entities=[
                EntityType(label="Person", description=""),
                EntityType(label="Software", description=""),
            ],
            relations=[
                RelationType(
                    label="OWNS",
                    description="",
                    patterns=[("Person", "Software")],
                    cardinality=Cardinality(max_per_source=3),
                )
            ],
        )
        error = _error(
            {
                "relations": [
                    {
                        "label": "OWNS",
                        "override": True,
                        "patterns": ["Person->Software"],
                        "cardinality": {"max_per_source": "9"},
                    }
                ]
            },
            extends=base,
        )

        assert "raises the cardinality limit" in str(error)

    def test_string_false_required_reports_loosening(self):
        """A quoted false for a required property still counts as loosening."""
        error = _error(
            {
                "entities": [
                    {
                        "label": "Person",
                        "override": True,
                        "properties": {
                            "email": {"type": "string", "required": "false"},
                            "born": "integer",
                        },
                    }
                ]
            },
            extends=_base(),
        )

        assert "makes property 'email' optional" in str(error)
