"""Cypher builders for relationship writes and graph traversal.

Leaf module: imports nothing from ``agrag.graphdb``. See ``entities.py`` for the
identifier-validation contract shared by every Cypher builder.
"""

from agrag.cypher.entities import validate_identifier


def bfs_expand_query(*, depth: int = 2, limit: int = 50) -> str:
    """Build Cypher for BFS expansion from seed entity ids.

    Traverses outgoing relationships from a set of seed entities, bounded
    by ``depth`` hops and ``limit`` total result nodes. The depth is
    formatted into the query text (not a parameter) because Neo4j does
    not accept a parameter for a variable-length relationship bound. It
    must come from ``RetrievalSettings``, never from user input.

    Args:
        depth: The maximum BFS hops. Must be a small, trusted constant.
        limit: The maximum number of result nodes.

    Returns:
        Parameterized Cypher expecting $seed_ids (list of string ids).
    """
    return (
        f"UNWIND $seed_ids AS seed_id "
        f"MATCH (start:_AgragNode {{id: seed_id}}) "
        f"MATCH path = (start)-[*1..{depth}]-(neighbor) "
        f"WHERE neighbor:_AgragNode AND NOT neighbor.id IN $seed_ids "
        f"RETURN DISTINCT neighbor, neighbor.id AS id "
        f"LIMIT {limit}"
    )


def chunks_mentioning_entities_query() -> str:
    """Build Cypher finding chunks that mention given entities.

    Walks the MENTIONED_IN edge from Chunk to Entity. Returns chunks
    that reference any of the given entity ids.

    Returns:
        Parameterized Cypher expecting $entity_ids (list of string ids).
    """
    return (
        "UNWIND $entity_ids AS entity_id "
        "MATCH (c:_AgragNode:Chunk)-[:MENTIONED_IN]-> "
        "(e:_AgragNode {{id: entity_id}}) "
        "WHERE c.merged_into IS NULL "
        "RETURN DISTINCT c, c.id AS id"
    )


def entities_mentioned_in_chunks_query() -> str:
    """Build Cypher finding entities mentioned by given chunks.

    Walks the MENTIONED_IN edge from Chunk to Entity in reverse. Returns
    entities referenced by any of the given chunk ids.

    Returns:
        Parameterized Cypher expecting $chunk_ids (list of string ids).
    """
    return (
        "UNWIND $chunk_ids AS chunk_id "
        "MATCH (c:_AgragNode:Chunk {{id: chunk_id}})"
        "-[:MENTIONED_IN]->(e:_AgragNode) "
        "WHERE e.merged_into IS NULL "
        "RETURN DISTINCT e, e.id AS id"
    )


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
    a single upsert call only ever targets one type. Identity is reasserted
    after applying properties, so a caller-supplied ``properties["id"]``
    cannot overwrite the ``id`` used to ``MERGE`` and orphan the relationship
    from later upserts of the same record.

    ``source_chunk_ids`` is unioned against whatever is already on the
    relationship at write time, inside this same query, rather than blindly
    overwritten: two concurrent callers upserting the same relationship each
    compute their own union from a read taken before either write lands, so
    without this, whichever caller's write commits second would silently
    discard the chunk ids the other one contributed. Reading the current
    value here, inside the same MERGE, keeps the union correct regardless of
    which caller's read was stale.

    Args:
        rel_type: The relationship type. Must already be validated.

    Returns:
        A parameterized Cypher query expecting a ``$records`` list parameter whose
        items carry ``id``, ``start_id``, ``end_id``, and ``properties`` keys.
        ``properties`` may include ``source_chunk_ids``; other keys are
        applied as-is.
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
        f"WITH r, record, "
        f"coalesce(r.source_chunk_ids, []) AS existing_source_chunk_ids "
        f"SET r += record.properties "
        f"SET r.source_chunk_ids = "
        f"[x IN existing_source_chunk_ids "
        f"WHERE NOT x IN coalesce(record.properties.source_chunk_ids, [])] "
        f"+ coalesce(record.properties.source_chunk_ids, []) "
        f"SET r.id = record.id"
    )
