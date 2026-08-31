"""Tests for the Cypher node builders and identifier validation."""

import pytest

from agrag.cypher.entities import (
    NODE_IDENTITY_LABEL,
    filter_clause,
    is_safe_identifier,
    upsert_merge_alias_query,
    upsert_node_query,
    upsert_survivor_query,
    validate_identifier,
)


class TestValidateIdentifier:
    """validate_identifier accepts safe identifiers and rejects the rest."""

    def test_accepts_plain_label(self) -> None:
        """A plain PascalCase label passes through unchanged."""
        assert validate_identifier("Person") == "Person"

    def test_accepts_snake_and_underscore(self) -> None:
        """Underscores and mixed case are allowed."""
        assert validate_identifier("Chunk_Node") == "Chunk_Node"

    @pytest.mark.parametrize(
        "bad",
        ["", " ", "Person Node", "Person`x", "Person;DROP", "1Node", "Person.Node"],
    )
    def test_rejects_injection(self, bad: str) -> None:
        """A space, backtick, semicolon, leading digit, or dot is rejected."""
        with pytest.raises(ValueError):
            validate_identifier(bad)


class TestIsSafeIdentifier:
    """is_safe_identifier is the non-raising counterpart to validate_identifier."""

    def test_true_for_safe_identifier(self) -> None:
        """A safe identifier reports True."""
        assert is_safe_identifier("Chunk_Node") is True

    @pytest.mark.parametrize("bad", ["", " ", "Person Node", "Person-Node", "1Node"])
    def test_false_for_unsafe_identifier(self, bad: str) -> None:
        """An unsafe identifier reports False instead of raising."""
        assert is_safe_identifier(bad) is False


class TestUpsertNodeQuery:
    """upsert_node_query builds a validated, UNWIND-batched merge."""

    def test_builds_unwind_merge(self) -> None:
        """The query merges on the identity anchor and sets the properties map."""
        q = upsert_node_query(["Chunk"])
        assert "UNWIND $records" in q
        assert f"MERGE (n:{NODE_IDENTITY_LABEL} {{id: record.id}})" in q
        assert "SET n:Chunk" in q
        assert "SET n += record.properties" in q
        assert "SET n.id = record.id" in q

    def test_merge_identity_is_independent_of_content_labels(self) -> None:
        """MERGE always anchors on NODE_IDENTITY_LABEL, never the content labels.

        Regression guard: MERGE-ing on the full requested label set would
        only match a node that already has every one of those labels, so
        adding a label to an existing same-id node would create a duplicate
        instead of updating it.
        """
        q = upsert_node_query(["Chunk", "Entity"])
        assert f"MERGE (n:{NODE_IDENTITY_LABEL} {{id: record.id}})" in q
        assert "MERGE (n:Chunk" not in q
        assert "MERGE (n:Entity" not in q

    def test_builds_compound_label_set(self) -> None:
        """Multiple labels are joined into one additive SET expression."""
        q = upsert_node_query(["Chunk", "Entity"])
        assert "SET n:Chunk:Entity" in q

    def test_validates_label(self) -> None:
        """An unsafe label raises before the query is built."""
        with pytest.raises(ValueError):
            upsert_node_query(["Bad Label"])

    def test_validates_every_label_in_a_compound_set(self) -> None:
        """An unsafe label anywhere in the set raises."""
        with pytest.raises(ValueError):
            upsert_node_query(["Chunk", "Bad Label"])

    def test_rejects_empty_labels(self) -> None:
        """An empty label set raises rather than building a labelless MERGE."""
        with pytest.raises(ValueError):
            upsert_node_query([])


class TestUpsertSurvivorQuery:
    """upsert_survivor_query accumulates atomically instead of overwriting."""

    def test_unions_source_chunk_ids_and_merged_from(self) -> None:
        """The accumulator fields are read and unioned/incremented in-query.

        Regression test: two concurrent callers merging into the same
        entity each compute their update from a snapshot taken before
        either write lands. Reading source_chunk_ids/merged_from/
        merge_count fresh inside this same query, rather than trusting a
        Python-computed absolute value, is what keeps neither writer's
        contribution from being lost to the other landing second.
        """
        q = upsert_survivor_query("Person")
        assert "coalesce(n.source_chunk_ids, [])" in q
        assert "coalesce(n.merged_from, [])" in q
        assert "coalesce(n.merge_count, 0)" in q
        assert "SET n.source_chunk_ids =" in q
        assert "record.new_source_chunk_ids" in q
        assert "SET n.merged_from =" in q
        assert "record.new_merged_from" in q
        assert "existing_merge_count + record.merge_count_delta" in q

    def test_reads_accumulators_before_the_blind_property_set(self) -> None:
        """The accumulator read happens before SET n += record.properties.

        Otherwise it would read back the value this same write just
        overwrote instead of whatever another writer already committed.
        """
        q = upsert_survivor_query("Person")
        assert q.index("existing_source_chunk_ids") < q.index(
            "SET n += record.properties"
        )

    def test_merge_identity_is_independent_of_content_label(self) -> None:
        """MERGE anchors on NODE_IDENTITY_LABEL, matching upsert_node_query."""
        q = upsert_survivor_query("Person")
        assert f"MERGE (n:{NODE_IDENTITY_LABEL} {{id: record.id}})" in q
        assert "SET n:Person" in q

    def test_validates_label(self) -> None:
        """An unsafe label raises before the query is built."""
        with pytest.raises(ValueError):
            upsert_survivor_query("Bad Label")


class TestUpsertMergeAliasQuery:
    """upsert_merge_alias_query claims a name without stealing an existing one."""

    def test_batches_over_merge_keys(self) -> None:
        """The query is UNWIND-batched over $merge_keys, not a single key."""
        q = upsert_merge_alias_query()
        assert "UNWIND $merge_keys AS merge_key" in q
        assert "MERGE (a:_AgragMergeAlias {merge_key: merge_key})" in q

    def test_only_claims_an_unclaimed_key(self) -> None:
        """ON CREATE SET means an existing alias keeps its owner.

        Regression test: without this, one merge's accepted names could
        overwrite an alias a different, unrelated entity already owns.
        """
        q = upsert_merge_alias_query()
        assert "ON CREATE SET a.entity_id = $entity_id" in q
        assert "SET a.entity_id = $entity_id" not in q.replace(
            "ON CREATE SET a.entity_id = $entity_id", ""
        )


class TestFilterClause:
    """filter_clause turns a flat-dict filter into a WHERE clause."""

    def test_empty_returns_blank(self) -> None:
        """No filters yields no clause and no parameters."""
        where, params = filter_clause({})
        assert where == ""
        assert params == {}

    def test_scalar_equals(self) -> None:
        """A scalar filter becomes an equality clause."""
        where, params = filter_clause({"kind": "doc"})
        assert where == "WHERE node.kind = $filter_kind"
        assert params == {"filter_kind": "doc"}

    def test_list_in(self) -> None:
        """A list filter becomes an IN clause."""
        where, params = filter_clause({"kind": ["doc", "web"]})
        assert where == "WHERE node.kind IN $filter_kind"
        assert params == {"filter_kind": ["doc", "web"]}

    def test_multiple_keys_anded(self) -> None:
        """Multiple keys are AND-ed together."""
        where, params = filter_clause({"a": 1, "b": "x"})
        assert where == "WHERE node.a = $filter_a AND node.b = $filter_b"

    def test_rejects_bad_field(self) -> None:
        """A non-identifier field name raises."""
        with pytest.raises(ValueError):
            filter_clause({"bad field": 1})
