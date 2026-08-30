"""Cypher builders for relationship writes.

Leaf module: imports nothing from ``agrag.graphdb``. See ``entities.py`` for the
identifier-validation contract shared by every Cypher builder.
"""

from agrag.cypher.entities import validate_identifier


def upsert_relation_query(rel_type: str) -> str:
    """Build the Cypher for an UNWIND-batched relationship upsert.

    Relationship identity is ``record.id``, not the ``(start, end, type)``
    triple: two relationships of this type between the same nodes keep
    separate identities when their ids differ, so parallel relationships do
    not collapse into one. When a record's endpoints move, the relationship
    keeps its id: the stale copy at the old endpoints is deleted before the
    new one is written, backed by the per-type uniqueness constraint from
    ``relation_id_constraint_query``. A relationship's type is immutable once
    written; retyping one requires deleting it under its old type first, since
    a single upsert call only ever targets one type.

    Args:
        rel_type: The relationship type. Must already be validated.

    Returns:
        A parameterized Cypher query expecting a ``$records`` list parameter whose
        items carry ``id``, ``start_id``, ``end_id``, and ``properties`` keys.
    """
    safe_type = validate_identifier(rel_type)
    return (
        f"UNWIND $records AS record "
        f"MATCH (a {{id: record.start_id}}) "
        f"MATCH (b {{id: record.end_id}}) "
        f"OPTIONAL MATCH (x)-[stale:{safe_type} {{id: record.id}}]->(y) "
        f"WHERE x.id <> record.start_id OR y.id <> record.end_id "
        f"FOREACH (_ IN CASE WHEN stale IS NULL THEN [] ELSE [1] END | DELETE stale) "
        f"MERGE (a)-[r:{safe_type} {{id: record.id}}]->(b) "
        f"SET r += record.properties"
    )
