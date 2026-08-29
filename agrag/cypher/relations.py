"""Cypher builders for relationship writes.

Leaf module: imports nothing from ``agrag.graphdb``. See ``entities.py`` for the
identifier-validation contract shared by every Cypher builder.
"""

from agrag.cypher.entities import validate_identifier


def upsert_relation_query(rel_type: str) -> str:
    """Build the Cypher for an UNWIND-batched relationship upsert.

    Args:
        rel_type: The relationship type. Must already be validated.

    Returns:
        A parameterized Cypher query expecting a ``$records`` list parameter whose
        items carry ``start_id``, ``end_id``, and ``properties`` keys.
    """
    safe_type = validate_identifier(rel_type)
    return (
        f"UNWIND $records AS record "
        f"MATCH (a {{id: record.start_id}}) "
        f"MATCH (b {{id: record.end_id}}) "
        f"MERGE (a)-[r:{safe_type}]->(b) "
        f"SET r += record.properties"
    )
