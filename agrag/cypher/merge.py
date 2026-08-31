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
        f"SET n.merged_into = $survivor_id"
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
        f"{create} "
        f"SET new_r = rel_props "
        f"WITH other, rel_type, new_r, r "
        f"DELETE r "
        f"RETURN other.id AS other_id, rel_type, "
        f"new_r.id AS new_relationship_id, new_r.source_chunk_ids AS source_chunk_ids"
    )


def apply_relationship_dedup_update_query() -> str:
    """Build Cypher applying kept relationships' merged source_chunk_ids.

    Returns:
        Parameterized Cypher expecting $updates (list of {id, source_chunk_ids}).
    """
    return (
        "UNWIND $updates AS update "
        "MATCH ()-[r {id: update.id}]-() "
        "SET r.source_chunk_ids = update.source_chunk_ids"
    )


def apply_relationship_dedup_delete_query() -> str:
    """Build Cypher deleting relationships a dedup pass superseded.

    Returns:
        Parameterized Cypher expecting $delete_ids (list of relationship ids).
    """
    return "UNWIND $delete_ids AS delete_id MATCH ()-[r {id: delete_id}]-() DELETE r"
