"""Cypher for the tombstone/transfer/dedup merge path."""

from agrag.cypher.entities import validate_identifier


def tombstone_query(label: str) -> str:
    """Build Cypher marking one or more nodes as merged, never deleting them.

    Args:
        label: The node label. Must already be validated.

    Returns:
        Parameterized Cypher expecting $tombstone_ids and $survivor_id.
    """
    return (
        f"UNWIND $tombstone_ids AS tombstone_id "
        f"MATCH (n:{validate_identifier(label)} {{id: tombstone_id}}) "
        f"SET n.merged_into = $survivor_id "
        f"REMOVE n.merge_key"
    )


def transfer_relationships_query(*, outgoing: bool) -> str:
    """Build Cypher moving one direction of a tombstoned node's relationships.

    Args:
        outgoing: True moves (tombstone)-[r]->(other) edges. False moves
            (other)-[r]->(tombstone) edges.

    Returns:
        Parameterized Cypher expecting $tombstone_id and $survivor_id.
    """
    if outgoing:
        match = "MATCH (tombstone {id: $tombstone_id})-[r]->(other)"
        create = "CREATE (survivor)-[new_r:$(rel_type)]->(other)"
    else:
        match = "MATCH (other)-[r]->(tombstone {id: $tombstone_id})"
        create = "CREATE (other)-[new_r:$(rel_type)]->(survivor)"
    return (
        f"MATCH (survivor {{id: $survivor_id}}) "
        f"{match} "
        f"WHERE other.id <> $survivor_id "
        f"WITH survivor, other, r, type(r) AS rel_type, properties(r) AS rel_props "
        f"DELETE r "
        f"WITH survivor, other, rel_type, rel_props "
        f"{create} "
        f"SET new_r = rel_props "
        f"RETURN other.id AS other_id, rel_type, "
        f"new_r.id AS new_relationship_id, new_r.source_chunk_ids AS source_chunk_ids"
    )


def apply_relationship_dedup_update_query() -> str:
    """Build Cypher applying a kept relationship's merged properties.

    Returns:
        Parameterized Cypher expecting $updates (list of
        {id, rel_type, properties}), where properties is the full merged
        property map -- not just source_chunk_ids -- so a duplicate's other
        fields are not silently dropped when its edge is deleted.
    """
    return (
        "UNWIND $updates AS update "
        "MATCH ()-[r {id: update.id}]-() "
        "WHERE type(r) = update.rel_type "
        "SET r += update.properties"
    )


def apply_relationship_dedup_delete_query() -> str:
    """Build Cypher deleting relationships a dedup pass superseded.

    Returns:
        Parameterized Cypher expecting $delete_ids (list of
        {id, rel_type}).
    """
    return (
        "UNWIND $delete_ids AS delete_id "
        "MATCH ()-[r {id: delete_id.id}]-() "
        "WHERE type(r) = delete_id.rel_type "
        "DELETE r"
    )


def fetch_node_relationships_query(*, outgoing: bool) -> str:
    """Build Cypher fetching one direction of a node's own relationships.

    Run against the survivor after every transfer completes, so the dedup
    pass that follows sees the survivor's whole neighbourhood in that
    direction -- both freshly transferred edges and ones it already had --
    rather than only what one transfer call happened to move.

    Args:
        outgoing: True fetches (node)-[r]->(other) edges. False fetches
            (other)-[r]->(node) edges.

    Returns:
        Parameterized Cypher expecting $node_id.
    """
    match = (
        "MATCH (n {id: $node_id})-[r]->(other)"
        if outgoing
        else "MATCH (other)-[r]->(n {id: $node_id})"
    )
    return (
        f"{match} "
        f"RETURN other.id AS other_id, type(r) AS rel_type, "
        f"r.id AS new_relationship_id, properties(r) AS properties"
    )


def delete_internal_relationships_query() -> str:
    """Build Cypher deleting edges that would become meaningless self-links.

    Covers two cases, both before any transfer runs, inside the same
    transaction as the merge:

    - An edge between two absorbed nodes: left untransferred, it would
      become a stale ``survivor->tombstone`` edge after the first transfer.
    - An edge directly between an absorbed node and its own survivor:
      ``transfer_relationships_query`` excludes these (``other.id <>
      $survivor_id``), since transferring one would create a
      ``survivor->survivor`` self-loop that no relation type's semantics
      call for. Deleting them here, in both directions, is what keeps them
      from being silently orphaned on the tombstone instead.

    Returns:
        Parameterized Cypher expecting $tombstone_ids (list of strings) and
        $survivor_id.
    """
    return (
        "UNWIND $tombstone_ids AS tid "
        "MATCH (a {id: tid})-[r]-(b) "
        "WHERE b.id IN $tombstone_ids OR b.id = $survivor_id "
        "DELETE r"
    )
