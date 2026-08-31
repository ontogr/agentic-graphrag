"""Cypher builders for node writes and filters.

Leaf module: imports nothing from ``agrag.graphdb`` or other store packages, so
the dependency points one way (store -> cypher).
"""

import re
from collections.abc import Sequence
from typing import Any


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Every node this store writes carries this label, used only to MERGE onto a
# node by id independently of its other, mutable labels. MERGE-ing on the
# full requested label set instead would only match a node that already has
# every one of those labels, so adding a label to an existing same-id node
# would create a duplicate node (and violate any per-label uniqueness
# constraint) rather than update it.
NODE_IDENTITY_LABEL = "_AgragNode"

# One node per merge_key ever assigned to any entity, permanently mapping
# that key to the entity's own id. A live entity's node also carries
# merge_key directly (see merge_key_constraint_query), but tombstone_query
# clears that property on absorption; this table is what keeps an absorbed
# name resolvable afterward. See fetch_by_merge_keys_query and
# upsert_merge_alias_query.
MERGE_ALIAS_LABEL = "_AgragMergeAlias"


def validate_identifier(value: str) -> str:
    """Check that a label or relationship type is a safe Cypher identifier.

    Args:
        value: The label or relationship type to check.

    Returns:
        ``value`` unchanged, once validated.

    Raises:
        ValueError: ``value`` is not a safe identifier.
    """
    if not _IDENTIFIER.match(value):
        raise ValueError(f"{value!r} is not a valid Cypher identifier")
    return value


def is_safe_identifier(value: str) -> bool:
    """Report whether a label or relationship type is a safe Cypher identifier.

    A non-raising counterpart to ``validate_identifier``, for filtering a
    batch of names (for example ones read back from the database) rather
    than validating one name a caller must supply correctly.

    Args:
        value: The label or relationship type to check.

    Returns:
        ``True`` if ``value`` is a safe identifier.
    """
    return _IDENTIFIER.match(value) is not None


def upsert_node_query(labels: Sequence[str]) -> str:
    """Build the Cypher for an UNWIND-batched node upsert.

    MERGE identity is anchored to ``NODE_IDENTITY_LABEL``, not to ``labels``
    itself, so a node keeps resolving to the same id regardless of what
    labels it currently carries. ``labels`` is then applied additively with
    ``SET``, which is idempotent (a label the node already has is a no-op)
    and never removes a label a previous upsert of the same id set but this
    one omits: labels only ever accumulate. Every node in one call gets the
    same additive label set, since Cypher requires labels to be literal in
    the query text rather than a runtime parameter; nodes whose
    ``NodeRecord.labels`` differ need separate calls, one per distinct label
    set (see ``Neo4jGraphStore.upsert_nodes`` for how a mixed batch is
    grouped and split before reaching this builder).

    Identity is reasserted after applying properties, so a caller-supplied
    ``properties["id"]`` cannot overwrite the ``id`` used to ``MERGE`` and
    orphan the node from later upserts of the same record.

    Args:
        labels: The node's labels to add, in addition to the identity anchor.
            Must already be validated, and non-empty.

    Returns:
        A parameterized Cypher query expecting a ``$records`` list parameter.

    Raises:
        ValueError: ``labels`` is empty, or any label is not a safe
            identifier.
    """
    if not labels:
        raise ValueError("upsert_node_query requires at least one label")
    label_expr = ":".join(validate_identifier(label) for label in labels)
    return (
        f"UNWIND $records AS record "
        f"MERGE (n:{NODE_IDENTITY_LABEL} {{id: record.id}}) "
        f"SET n:{label_expr} "
        f"SET n += record.properties "
        f"SET n.id = record.id"
    )


def merge_key_index_query(label: str) -> str:
    """Build a CREATE INDEX query on the node merge_key property.

    Backs the global exact-match lookup.

    Args:
        label: The node label. Must already be validated.

    Returns:
        A Cypher query creating the range index if absent.
    """
    safe_label = validate_identifier(label)
    return (
        f"CREATE INDEX {safe_label}_merge_key_index IF NOT EXISTS "
        f"FOR (n:{safe_label}) ON (n.merge_key)"
    )


def fetch_by_merge_keys_query() -> str:
    """Build Cypher for a batched exact-match lookup by merge key.

    Resolves through the merge-key alias table (``MERGE_ALIAS_LABEL``)
    rather than matching each node's own ``merge_key`` property directly:
    that property is cleared when a node is tombstoned (see
    ``tombstone_query``), so a name it once held would otherwise become
    unreachable. The alias always points at the entity id that first held
    the key, which may itself now be a tombstone; the caller follows its
    ``merged_into`` chain to the live survivor.

    Returns:
        Parameterized Cypher expecting $merge_keys (list of strings).
    """
    return (
        f"UNWIND $merge_keys AS merge_key "
        f"MATCH (a:{MERGE_ALIAS_LABEL} {{merge_key: merge_key}}) "
        f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: a.entity_id}}) "
        f"RETURN n"
    )


def upsert_merge_alias_query() -> str:
    """Build Cypher recording one merge_key's originating entity id.

    Every ``apply_merge`` call writes this for the survivor's current
    merge_key, so a name an entity has ever held keeps resolving to that
    entity even after the entity's own node clears ``merge_key`` on
    absorption. The alias is never rewritten to point elsewhere: if the
    entity it names is later itself absorbed, ``fetch_by_merge_keys_query``'s
    caller follows that entity's ``merged_into`` chain from here instead of
    this table being kept in sync with every later merge.

    Returns:
        Parameterized Cypher expecting $merge_key and $entity_id.
    """
    return (
        f"MERGE (a:{MERGE_ALIAS_LABEL} {{merge_key: $merge_key}}) "
        f"SET a.entity_id = $entity_id"
    )


def clear_property_query(property_name: str) -> str:
    """Build Cypher removing one property from a batch of nodes by id.

    Used to drop a stale value rather than leave it readable after a write
    that was supposed to replace it fails partway through, such as an
    embedding vector left over from before an entity's text changed.

    Args:
        property_name: The property to remove. Must already be validated.

    Returns:
        Parameterized Cypher expecting $ids (list of strings).
    """
    safe_property = validate_identifier(property_name)
    return (
        f"UNWIND $ids AS entity_id "
        f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: entity_id}}) "
        f"REMOVE n.{safe_property}"
    )


def fetch_all_by_label_query(label: str) -> str:
    """Build Cypher paginating every node with label, for consolidate().

    Args:
        label: The node label. Must already be validated.

    Returns:
        Parameterized Cypher expecting $skip and $limit.
    """
    return (
        f"MATCH (n:{validate_identifier(label)}) "
        f"RETURN n ORDER BY n.id SKIP $skip LIMIT $limit"
    )


def fetch_relations_between_query(rel_type: str) -> str:
    """Build Cypher for batched lookup of existing relations by endpoints.

    Args:
        rel_type: The relationship type. Must already be validated.

    Returns:
        Parameterized Cypher expecting $pairs (list of
        {source_id, target_id}). Returns each match's id and
        source_chunk_ids alongside the pair it matched.
    """
    safe_type = validate_identifier(rel_type)
    return (
        f"UNWIND $pairs AS pair "
        f"MATCH (a {{id: pair.source_id}})-[r:{safe_type}]->(b {{id: pair.target_id}}) "
        f"RETURN pair.source_id AS source_id, pair.target_id AS target_id, "
        f"r.id AS id, r.source_chunk_ids AS source_chunk_ids"
    )


def filter_clause(
    filters: dict[str, Any], node_var: str = "node"
) -> tuple[str, dict[str, Any]]:
    """Build a Cypher WHERE clause and parameters from a flat-dict filter.

    Args:
        filters: A flat-dict filter: a scalar value means exact match, a list
            value means any of, and all keys are AND-ed together.
        node_var: The Cypher variable bound to the node in the surrounding query.

    Returns:
        The ``WHERE`` clause text (beginning with ``WHERE`` when ``filters`` is
        non-empty, otherwise an empty string) and the parameter dict to pass
        with it.
    """
    if not filters:
        return "", {}
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for key, value in filters.items():
        field = validate_identifier(key)
        param = f"filter_{field}"
        if isinstance(value, list):
            clauses.append(f"{node_var}.{field} IN ${param}")
        else:
            clauses.append(f"{node_var}.{field} = ${param}")
        params[param] = value
    return "WHERE " + " AND ".join(clauses), params
