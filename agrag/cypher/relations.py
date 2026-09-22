"""Cypher builders for relationship writes and graph traversal.

Leaf module: imports nothing from ``agrag.graphdb``. See ``entities.py`` for the
identifier-validation contract shared by every Cypher builder.
"""

from collections.abc import Sequence
from typing import Any, Literal

from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.entities import NODE_IDENTITY_LABEL, validate_identifier


TraversalDirection = Literal["outgoing", "incoming", "both"]


_DIRECTION_ARROW: dict[TraversalDirection, tuple[str, str]] = {
    "outgoing": ("-", "->"),
    "incoming": ("<-", "-"),
    "both": ("-", "-"),
}


def close_part_of_query() -> str:
    """Build Cypher that closes currently valid document-to-chunk edges.

    Only committed edges are closed. Pending edges belong to an in-flight
    cutover and remain open until that job commits.

    Returns:
        Parameterized Cypher expecting $document_node_id. Returns the
        number of committed edges closed.
    """
    return (
        "MATCH (d:_AgragNode:Document {id: $document_node_id})"
        "-[r:PART_OF]->() "
        f"WHERE r.invalid_at IS NULL AND {pending_filter_clause('r')} "
        "SET r.invalid_at = datetime() RETURN count(r) AS closed"
    )


def bfs_expand_query(
    *,
    depth: int = 2,
    limit: int = 50,
    filters: dict[str, Any] | None = None,
    relation_types: Sequence[str] | None = None,
    direction: TraversalDirection = "both",
    document_ids: Sequence[str] | None = None,
    labels: Sequence[str] | None = None,
    job_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Build Cypher for BFS expansion from seed entity ids.

    Traverses relationships from a set of seed entities, bounded by
    ``depth`` hops and ``limit`` total result nodes. The depth is
    formatted into the query text (not a parameter) because Neo4j does
    not accept a parameter for a variable-length relationship bound. It
    must come from ``RetrievalSettings``, never from user input.

    ``relation_types`` restricts which relationships a traversal may
    cross. Neo4j does not accept a parameter for relationship types
    either, so each type is validated and formatted into the pattern.

    ``direction`` picks which way each hop walks: relationships leaving
    the seed (``"outgoing"``), entering it (``"incoming"``), or either
    way (``"both"``, the default). Direction is a property of the
    pattern's arrow, so it is formatted into the query text like the
    depth and the type pattern are -- it must never be interpolated from
    user input without validation against ``TraversalDirection``.

    ``depth`` is clamped to [1, 10] and ``limit`` to [1, 1000] so
    misconfigured or malicious settings cannot produce unbounded
    traversals. The clamp is applied here, closest to the Cypher
    interpolation, so every caller benefits.

    Result nodes are restricted to ``_AgragNode`` entities that are
    **not** ``Chunk`` nodes: chunks are intermediate path nodes only,
    never returned as BFS results.

    Args:
        depth: The maximum BFS hops. Clamped to [1, 10].
        limit: The maximum number of result nodes. Clamped to [1, 1000].
        filters: Optional flat-dict filter applied to neighbor nodes.
            A scalar value means exact match, a list means any of.
        relation_types: Optional relationship types the traversal may
            cross. None or empty crosses every type.
        direction: Which way a hop walks each relationship. Defaults
            to ``"both"``.
        document_ids: Optional document ids that must mention each result
            entity through a ``MENTIONED_IN`` edge.
        labels: Optional labels that returned neighbors must have at
            least one of.
        job_id: The in-flight Cutover Job's id, or null outside a job.
            A null ``$job_id`` reduces the pending guards to
            committed-only, so no retrieval path ever returns a node or
            crosses an edge written by an uncommitted job.

    Returns:
        A ``(query, params)`` tuple. The query expects ``$seed_ids``
        (list of string ids), ``$job_id``, plus any filter parameters.

    Raises:
        ValueError: A relation type is not a safe Cypher identifier.
            An unsupported direction also raises ValueError.
    """
    from agrag.cypher.entities import filter_clause  # noqa: PLC0415

    safe_depth = max(1, min(depth, 10))
    safe_limit = max(1, min(limit, 1000))
    if direction not in _DIRECTION_ARROW:
        raise ValueError(
            f"unsupported direction {direction!r}; expected one of "
            f"{tuple(_DIRECTION_ARROW)}"
        )

    where_clause, filter_params = filter_clause(filters or {}, node_var="neighbor")
    filter_suffix = f" AND {where_clause[6:]}" if where_clause else ""
    base_where = (
        "neighbor:_AgragNode AND NOT neighbor:Chunk AND NOT neighbor.id IN $seed_ids "
        "AND (neighbor._pending_job_id IS NULL "
        "OR neighbor._pending_job_id = $job_id) "
        "AND ALL(r IN relationships(path) WHERE r._pending_job_id IS NULL "
        "OR r._pending_job_id = $job_id)"
    )
    document_suffix = (
        " AND EXISTS { "
        "MATCH (neighbor)<-[:MENTIONED_IN]-(scoped_chunk:_AgragNode:Chunk) "
        "WHERE scoped_chunk.document_id IN $document_ids }"
        if document_ids
        else ""
    )
    safe_labels = [validate_identifier(label) for label in labels or []]
    label_predicate = " OR ".join(f"neighbor:{label}" for label in safe_labels)
    label_suffix = (
        f" AND ({label_predicate})"
        if len(safe_labels) > 1
        else (f" AND {label_predicate}" if label_predicate else "")
    )
    where = f"{base_where}{filter_suffix}{document_suffix}{label_suffix}"
    type_pattern = relationship_type_pattern(relation_types)
    left_arrow, right_arrow = _DIRECTION_ARROW[direction]
    query = (
        f"UNWIND $seed_ids AS seed_id "
        f"MATCH (start:_AgragNode {{id: seed_id}}) "
        f"MATCH path = (start){left_arrow}[{type_pattern}*1..{safe_depth}]"
        f"{right_arrow}(neighbor) "
        f"WHERE {where} "
        f"RETURN DISTINCT neighbor, neighbor.id AS id "
        f"LIMIT {safe_limit}"
    )
    return query, filter_params


def entities_in_documents_query() -> str:
    """Build a query for live entities mentioned in selected documents.

    Pending visibility is job-scoped: a null ``$job_id`` reduces the
    guard to committed-only, so document scoping never surfaces an
    entity an uncommitted job wrote.

    Returns:
        Parameterized Cypher expecting $document_ids (list of string
        ids) and $job_id (the in-flight job's id, or null outside a
        job).
    """
    return (
        "MATCH (chunk:_AgragNode:Chunk)-[mention:MENTIONED_IN]->"
        "(entity:_AgragNode) "
        "WHERE EXISTS { "
        "MATCH (document:_AgragNode:Document)-[part:PART_OF]->(chunk) "
        "WHERE document.id IN $document_ids AND part.invalid_at IS NULL "
        "AND (document._pending_job_id IS NULL "
        "OR document._pending_job_id = $job_id) "
        "AND (part._pending_job_id IS NULL OR part._pending_job_id = $job_id) } "
        "AND entity.merged_into IS NULL "
        "AND (entity._pending_job_id IS NULL "
        "OR entity._pending_job_id = $job_id) "
        "AND (chunk._pending_job_id IS NULL OR chunk._pending_job_id = $job_id) "
        "AND (mention._pending_job_id IS NULL "
        "OR mention._pending_job_id = $job_id) "
        "RETURN DISTINCT entity.id AS id"
    )


def relationship_types_from_query(
    *,
    relation_types: Sequence[str] | None = None,
    direction: TraversalDirection = "both",
    job_id: str | None = None,
) -> str:
    """Build Cypher listing the relationship types touching seed entities.

    Depth-1 only, by construction: it reads ``type(r)`` off the
    relationships directly attached to each seed entity and never
    traverses past them, so it has no depth bound to clamp the way
    :func:`bfs_expand_query` does and cannot be widened into a multi-hop
    walk by a caller. Use it to discover which types exist before
    narrowing a real traversal, not as a substitute for one.

    Args:
        relation_types: Optional relationship types to list. None or
            empty lists every type directly attached to the seeds.
        direction: Which relationships to consider, read relative to
            the seed entity: those leaving it (``"outgoing"``), those
            entering it (``"incoming"``), or both.
        job_id: The in-flight Cutover Job's id, or null outside a job.
            A null ``$job_id`` reduces the pending guard to
            committed-only, so no in-flight job's edges add types.

    Returns:
        Parameterized Cypher expecting ``$seed_ids`` (list of string
        ids) and ``$job_id``, returning one row per distinct attached
        type under ``rel_type``.

    Raises:
        ValueError: A relation type is not a safe Cypher identifier.
    """
    type_pattern = relationship_type_pattern(relation_types)
    left_arrow, right_arrow = _DIRECTION_ARROW[direction]
    return (
        f"UNWIND $seed_ids AS seed_id "
        f"MATCH (seed:_AgragNode {{id: seed_id}}) "
        f"MATCH (seed){left_arrow}[r{type_pattern}]{right_arrow}(neighbor) "
        f"WHERE NOT neighbor:Chunk AND NOT neighbor:Community "
        f"AND NOT type(r) IN ['MENTIONED_IN', 'MEMBER_OF'] "
        f"AND (r._pending_job_id IS NULL OR r._pending_job_id = $job_id) "
        f"RETURN DISTINCT type(r) AS rel_type"
    )


def relationship_type_pattern(relation_types: Sequence[str] | None) -> str:
    """Return the validated Cypher type pattern for a set of types.

    Args:
        relation_types: The types to restrict a relationship pattern
            to. None or empty returns an untyped pattern.

    Returns:
        A ``:TYPE|TYPE`` pattern, or an empty string when no types were
        given.

    Raises:
        ValueError: A relation type is not a safe Cypher identifier.
    """
    if not relation_types:
        return ""
    return ":" + "|".join(validate_identifier(rel_type) for rel_type in relation_types)


def chunks_mentioning_entities_query() -> str:
    """Build Cypher finding chunks that mention given entities.

    Walks the MENTIONED_IN edge from Chunk to Entity. Returns chunks
    that reference any of the given entity ids. Pending visibility is
    job-scoped: a null ``$job_id`` reduces the guard to committed-only.

    Returns:
        Parameterized Cypher expecting $entity_ids (list of string ids)
        and $job_id (the in-flight job's id, or null outside a job).
    """
    return (
        "UNWIND $entity_ids AS entity_id "
        "MATCH (c:_AgragNode:Chunk)-[:MENTIONED_IN]-> "
        "(e:_AgragNode {{id: entity_id}}) "
        "WHERE c.merged_into IS NULL "
        "AND (c._pending_job_id IS NULL OR c._pending_job_id = $job_id) "
        "RETURN DISTINCT c, c.id AS id"
    )


def entities_mentioned_in_chunks_query() -> str:
    """Build Cypher finding entities mentioned by given chunks.

    Walks the MENTIONED_IN edge from Chunk to Entity in reverse. Returns
    entities referenced by any of the given chunk ids. Pending
    visibility is job-scoped: a null ``$job_id`` reduces the guard to
    committed-only.

    Returns:
        Parameterized Cypher expecting $chunk_ids (list of string ids)
        and $job_id (the in-flight job's id, or null outside a job).
    """
    return (
        "UNWIND $chunk_ids AS chunk_id "
        "MATCH (c:_AgragNode:Chunk {{id: chunk_id}})"
        "-[:MENTIONED_IN]->(e:_AgragNode) "
        "WHERE e.merged_into IS NULL "
        "AND (e._pending_job_id IS NULL OR e._pending_job_id = $job_id) "
        "RETURN DISTINCT e, e.id AS id"
    )


def fetch_all_relations_query() -> str:
    """Build Cypher paginating every live domain relationship.

    Used by Graph.detect_communities() to build the weighted edge list for
    clustering. Excludes MENTIONED_IN and MEMBER_OF (system edges, not
    entity-graph topology) and any endpoint that is a Chunk, a Community,
    or a tombstone.

    ``ORDER BY`` includes ``type(r)`` and ``r.id`` after ``(a.id, b.id)``
    because two distinct relationships (different types, or the same type
    with different ids) can share the same endpoints -- see
    ``upsert_relation_query``. Without a total order, Neo4j does not
    guarantee a stable row order across separate paged queries, so a page
    boundary falling inside such a group can duplicate or drop rows.

    Returns:
        Parameterized Cypher expecting $skip and $limit. Returns each
        relation's source_id, target_id, source_chunk_ids, and rel_type.
    """
    return (
        f"MATCH (a:{NODE_IDENTITY_LABEL})-[r]->(b:{NODE_IDENTITY_LABEL}) "
        f"WHERE a.merged_into IS NULL AND b.merged_into IS NULL "
        f"AND NOT a:Chunk AND NOT b:Chunk "
        f"AND NOT a:Community AND NOT b:Community "
        f"AND NOT type(r) IN ['MENTIONED_IN', 'MEMBER_OF'] "
        f"AND r._pending_job_id IS NULL "
        f"RETURN a.id AS source_id, b.id AS target_id, "
        f"r.source_chunk_ids AS source_chunk_ids, "
        f"type(r) AS rel_type "
        f"ORDER BY a.id, b.id, type(r), coalesce(r.id, '') SKIP $skip LIMIT $limit"
    )


def fetch_all_relations_query_cursor() -> str:
    """Build Cypher paginating every live domain relationship via keyset.

    Keyset variant of :func:`fetch_all_relations_query` for large graphs
    where ``SKIP`` becomes expensive. Orders by ``(a.id, b.id, type(r),
    r.id)`` and pages by the last seen tuple; the first page uses
    ``last_a=""``, ``last_b=""``, ``last_type=""`` and ``last_rel_id=""``.
    Like the offset variant, it excludes every edge an in-flight Cutover
    Job wrote.

    The relationship type and id break ties on ``(a.id, b.id)``: two
    distinct relationships (different types, or the same type with
    different ids) can share the same endpoints -- see
    ``upsert_relation_query``. Ordering by endpoints alone would let a
    page boundary fall inside such a group, silently excluding the
    remaining relationships for that pair from every later page.

    Returns:
        Parameterized Cypher expecting ``$last_a``, ``$last_b``,
        ``$last_type``, ``$last_rel_id`` and ``$limit``.
    """
    return (
        f"MATCH (a:{NODE_IDENTITY_LABEL})-[r]->(b:{NODE_IDENTITY_LABEL}) "
        f"WHERE (a.id > $last_a "
        f"OR (a.id = $last_a AND b.id > $last_b) "
        f"OR (a.id = $last_a AND b.id = $last_b AND type(r) > $last_type) "
        f"OR (a.id = $last_a AND b.id = $last_b AND type(r) = $last_type "
        f"AND coalesce(r.id, '') > $last_rel_id) "
        f'OR ($last_a = "" AND $last_b = "" AND $last_type = "" '
        f'AND $last_rel_id = "")) '
        f"AND a.merged_into IS NULL AND b.merged_into IS NULL "
        f"AND NOT a:Chunk AND NOT b:Chunk "
        f"AND NOT a:Community AND NOT b:Community "
        f"AND NOT type(r) IN ['MENTIONED_IN', 'MEMBER_OF'] "
        f"AND r._pending_job_id IS NULL "
        f"RETURN a.id AS source_id, b.id AS target_id, "
        f"r.source_chunk_ids AS source_chunk_ids, "
        f"type(r) AS rel_type, coalesce(r.id, '') AS rel_id "
        f"ORDER BY a.id, b.id, type(r), coalesce(r.id, '') LIMIT $limit"
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

    The Cutover Job tag is applied only when the ``MERGE`` creates the
    relationship, so the tag means "this job created this edge". A job
    that only writes over an existing edge leaves it untagged: it stays
    visible to retrieval, and the job's rollback — which deletes tagged
    rows — cannot reach it.

    Args:
        rel_type: The relationship type. Must already be validated.

    Returns:
        A parameterized Cypher query expecting a ``$records`` list parameter whose
        items carry ``id``, ``start_id``, ``end_id``, ``properties``, and
        ``pending_job_id`` keys. ``properties`` may include
        ``source_chunk_ids``; other keys are applied as-is. The query returns
        one row with ``id`` for every record whose endpoints matched and was
        processed.
    """
    safe_type = validate_identifier(rel_type)
    return (
        f"UNWIND $records AS record "
        f"MATCH (a {{id: record.start_id}}) "
        f"MATCH (b {{id: record.end_id}}) "
        f"OPTIONAL MATCH (x)-[stale:{safe_type} {{id: record.id}}]->(y) "
        f"WHERE (x.id <> record.start_id OR y.id <> record.end_id) "
        f"AND (record.pending_job_id IS NULL "
        f"OR stale._pending_job_id IS NULL "
        f"OR stale._pending_job_id = record.pending_job_id) "
        f"FOREACH (_ IN CASE WHEN stale IS NULL THEN [] ELSE [1] END | DELETE stale) "
        f"MERGE (a)-[r:{safe_type} {{id: record.id}}]->(b) "
        f"ON CREATE SET r._pending_job_id = record.pending_job_id "
        f"WITH r, record, "
        f"(record.pending_job_id IS NULL OR r._pending_job_id IS NULL "
        f"OR r._pending_job_id = record.pending_job_id) AS can_update, "
        f"coalesce(r.source_chunk_ids, []) AS existing_source_chunk_ids "
        f"SET r += CASE WHEN can_update THEN record.properties ELSE {{}} END "
        f"SET r.source_chunk_ids = CASE WHEN can_update THEN "
        f"[x IN existing_source_chunk_ids "
        f"WHERE NOT x IN coalesce(record.properties.source_chunk_ids, [])] "
        f"+ coalesce(record.properties.source_chunk_ids, []) "
        f"ELSE r.source_chunk_ids END "
        f"SET r.id = record.id "
        f"RETURN record.id AS id"
    )
