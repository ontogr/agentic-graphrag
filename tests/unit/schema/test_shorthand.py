"""Tests for the shorthand readers behind load_schema."""

import pytest

from agrag.schema.errors import Issues
from agrag.schema.shorthand import (
    parse_pattern,
    parse_relation,
    read_entities,
    read_relations,
    split_list,
)


class TestParseRelation:
    """Relation strings parse into a label and expanded endpoint pairs."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            (
                "Person-WORKS_FOR->Organization",
                ("WORKS_FOR", [["Person", "Organization"]]),
            ),
            (
                " Person - WORKS_FOR -> Organization ",
                ("WORKS_FOR", [["Person", "Organization"]]),
            ),
            (
                "Person|Organization-OWNS->Software|Dataset",
                (
                    "OWNS",
                    [
                        ["Person", "Software"],
                        ["Person", "Dataset"],
                        ["Organization", "Software"],
                        ["Organization", "Dataset"],
                    ],
                ),
            ),
        ],
    )
    def test_reads_relation_strings(self, text, expected):
        """An arrow string yields its label and cross product of endpoints."""
        assert parse_relation(text) == expected

    @pytest.mark.parametrize("text", ["Person", "Person->Organization", "-X->", "A--B"])
    def test_returns_none_for_other_text(self, text):
        """Text without a source-label-target shape yields None."""
        assert parse_relation(text) is None


class TestParsePattern:
    """Pattern strings expand alternatives into source-target pairs."""

    def test_reads_alternatives(self):
        """A bar on either side expands to the product of endpoints."""
        assert parse_pattern("A|B->C") == [["A", "C"], ["B", "C"]]

    def test_returns_none_without_arrow(self):
        """Text without an arrow is not a pattern."""
        assert parse_pattern("A") is None


class TestReadEntities:
    """Entity shorthand reads every accepted form into canonical drafts."""

    def test_label_list(self):
        """A plain list gives label-only types with empty parents."""
        issues = Issues()

        drafts = read_entities(["Person", "Vendor"], "entities", issues)

        assert not issues
        assert [d.body["label"] for d in drafts] == ["Person", "Vendor"]
        assert drafts[0].body["description"] == ""
        assert drafts[0].body["parents"] == []
        assert drafts[1].path == "entities[1]"

    def test_label_to_description_map(self):
        """A label-to-description map keeps the key as the label."""
        issues = Issues()

        drafts = read_entities(
            {"Vendor": "A seller.", "Buyer": None}, "entities", issues
        )

        assert not issues
        assert [(d.body["label"], d.body["description"]) for d in drafts] == [
            ("Vendor", "A seller."),
            ("Buyer", ""),
        ]

    def test_label_to_object_map_and_string_parent(self):
        """A single string parent becomes a one-item list."""
        issues = Issues()

        drafts = read_entities(
            {"Vendor": {"description": "A seller.", "parents": "Organization"}},
            "entities",
            issues,
        )

        assert not issues
        assert drafts[0].body["parents"] == ["Organization"]
        assert drafts[0].path == "entities.Vendor"

    def test_label_differing_from_key_is_an_error(self):
        """A label that disagrees with its map key is reported."""
        issues = Issues()

        read_entities({"Vendor": {"label": "Seller"}}, "entities", issues)

        assert [i.path for i in issues.items] == ["entities.Vendor.label"]
        assert "differs from its key 'Vendor'" in issues.items[0].message

    @pytest.mark.parametrize(
        ("properties", "expected"),
        [
            (["email"], {"email": {"type": "string"}}),
            ({"born": "integer"}, {"born": {"type": "integer"}}),
            ({"email": None}, {"email": {"type": "string"}}),
            (
                {"status": {"type": "string", "required": True, "enum": ["a"]}},
                {"status": {"type": "string", "required": True, "enum": ["a"]}},
            ),
            ([{"name": "born", "type": "integer"}], {"born": {"type": "integer"}}),
        ],
    )
    def test_property_forms(self, properties, expected):
        """Every property shorthand reads into the same canonical dict."""
        issues = Issues()

        drafts = read_entities(
            [{"label": "Person", "properties": properties}], "entities", issues
        )

        assert not issues
        assert drafts[0].body["properties"] == expected

    def test_unknown_key_suggests_the_close_match(self):
        """A misspelled key reports the nearest allowed key."""
        issues = Issues()

        read_entities([{"label": "A", "parnts": ["B"]}], "entities", issues)

        assert issues.items[0].path == "entities[0].parnts"
        assert "Did you mean 'parents'?" in issues.items[0].message

    def test_subtypes_key_names_the_replacement(self):
        """The removed subtypes key points at parents."""
        issues = Issues()

        read_entities([{"label": "A", "subtypes": ["B"]}], "entities", issues)

        assert "Set 'parents' on each child type" in issues.items[0].message

    def test_settings_key_names_extraction_settings(self):
        """A threshold in a schema points at ExtractionSettings."""
        issues = Issues()

        read_entities([{"label": "A", "threshold": 0.6}], "entities", issues)

        assert issues.items[0].path == "entities[0].threshold"
        assert "ExtractionSettings" in issues.items[0].message

    def test_wrong_container_type(self):
        """A non-list, non-mapping entities value is rejected."""
        issues = Issues()

        read_entities(5, "entities", issues)

        assert issues.items[0].message == (
            "expected a list or a mapping of entity types, got int."
        )


class TestReadRelations:
    """Relation shorthand reads every accepted form into canonical drafts."""

    def test_string_triple_and_object_forms(self):
        """Strings, triples and objects read in source order."""
        issues = Issues()

        drafts = read_relations(
            [
                "Person-WORKS_FOR->Organization",
                ("Organization", "LOCATED_IN", "Location"),
                {"label": "OWNS", "description": "d", "patterns": ["Person->Software"]},
            ],
            "relations",
            issues,
        )

        assert not issues
        assert [d.body["label"] for d in drafts] == ["WORKS_FOR", "LOCATED_IN", "OWNS"]
        assert drafts[1].body["patterns"] == [["Organization", "Location"]]
        assert drafts[2].body["patterns"] == [["Person", "Software"]]

    def test_same_label_strings_merge_patterns(self):
        """Strings with one label merge into a single relation."""
        issues = Issues()

        drafts = read_relations(["A-R->B", "C-R->D", "A-R->B"], "relations", issues)

        assert len(drafts) == 1
        assert drafts[0].body["patterns"] == [["A", "B"], ["C", "D"]]

    def test_label_to_pattern_map(self):
        """A label-to-pattern map names the relation and its pairs."""
        issues = Issues()

        drafts = read_relations({"OWNS": "Person->Software"}, "relations", issues)

        assert not issues
        assert drafts[0].body["patterns"] == [["Person", "Software"]]

    def test_pair_patterns(self):
        """A list of [source, target] pairs is accepted as written."""
        issues = Issues()

        drafts = read_relations(
            [{"label": "OWNS", "patterns": [["Person", "Software"]]}],
            "relations",
            issues,
        )

        assert not issues
        assert drafts[0].body["patterns"] == [["Person", "Software"]]

    def test_bad_relation_string(self):
        """Text with no arrow reports the expected relation shape."""
        issues = Issues()

        read_relations(["Person WORKS_FOR Org"], "relations", issues)

        assert issues.items[0].path == "relations[0]"
        assert issues.items[0].message.startswith(
            "cannot read 'Person WORKS_FOR Org' as a relation."
        )

    def test_bad_relation_label(self):
        """A label with a hyphen reports the allowed characters."""
        issues = Issues()

        read_relations([("A", "works-for", "B")], "relations", issues)

        assert (
            "may hold only letters, digits and underscores" in issues.items[0].message
        )

    def test_bad_pattern_string(self):
        """A pattern string without an arrow reports its own path."""
        issues = Issues()

        read_relations([{"label": "R", "patterns": ["Person"]}], "relations", issues)

        assert issues.items[0].path == "relations[0].patterns[0]"


class TestSplitList:
    """Native lists split into entity labels and relations."""

    def test_splits_labels_and_relations(self):
        """Labels and arrow strings or triples go to separate keys."""
        issues = Issues()

        data = split_list(["A", "B", "A-R->B", ("B", "S", "A")], issues)

        assert not issues
        assert data == {
            "entities": ["A", "B"],
            "relations": ["A-R->B", ("B", "S", "A")],
        }

    def test_rejects_other_items(self):
        """An item that is neither a label nor a relation is reported."""
        issues = Issues()

        split_list(["A", 3], issues)

        assert issues.items[0].path == "[1]"
