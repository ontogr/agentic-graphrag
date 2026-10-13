"""Cypher builders for relationship writes and graph traversal.

Leaf module: imports nothing from ``agrag.graphdb``. See ``entities.py`` for the
identifier-validation contract shared by every Cypher builder.
"""

from collections.abc import Sequence
from typing import Any, Literal

from agrag.common.data_models.candidate import CANDIDATE_EDGE_TYPES
from agrag.common.data_models.graph_record import PENDING_JOB_ID_PROPERTY
from agrag.common.data_models.structure import (
    FIGURE_LABEL,
    HAS_CHILD,
    HAS_DOCUMENT,
    HAS_PART,
    SECTION_LABEL,
    SOURCE_LABEL,
    TABLE_LABEL,
)
from agrag.cypher._pending_filter import (
    pending_filter_clause,
    pending_path_filter_clause,
)
from agrag.cypher.entities import (
    NODE_IDENTITY_LABEL,
    own_row_expression,
    validate_identifier,
)


TraversalDirection = Literal["outgoing", "incoming", "both"]


_STRUCTURE_RELATIONS = (HAS_PART, HAS_CHILD, HAS_DOCUMENT)
_STRUCTURE_LABELS = (SECTION_LABEL, TABLE_LABEL, FIGURE_LABEL, SOURCE_LABEL)


def _cypher_string_list(values: Sequence[str]) -> str:
    """Return a Cypher list literal of validated relationship types."""
    return "[" + ", ".join(f"'{validate_identifier(v)}'" for v in values) + "]"


_NON_ENTITY_RELATIONS = _cypher_string_list(
    ("MENTIONED_IN", "MEMBER_OF", *_STRUCTURE_RELATIONS, *sorted(CANDIDATE_EDGE_TYPES))
)

_DEFAULT_TRAVERSAL_EXCLUSIONS = _cypher_string_list(_STRUCTURE_RELATIONS)
_STRUCTURE_LABEL_EXCLUSIONS = " AND ".join(
    f"NOT neighbor:{validate_identifier(label)}" for label in _STRUCTURE_LABELS
)

_DIRECTION_ARROW: dict[TraversalDirection, tuple[str, str]] = {
    "outgoing": ("-", "->"),
    "incoming": ("<-", "-"),
    "both": ("-", "-"),
}


def _identity_path_clause(path_alias: str) -> str:
    """Return a filter requiring every node in a path to be an entity."""
    return (
        f"ALL(path_node IN nodes({path_alias}) WHERE path_node:{NODE_IDENTITY_LABEL})"
    )


def close_has_part_query() -> str:
    """Build Cypher that closes currently valid document-to-node edges.

    Only committed edges are closed. Pending edges belong to an in-flight
    cutover and remain open until that job commits. An edge to a node in
    ``$keep_node_ids`` stays open: a job that writes a chunk, section, table or
    figure with the id of a committed one reuses its edge without tagging it,
    and the edge must outlive the close.

    Returns:
        Parameterized Cypher expecting $document_node_id and $keep_node_ids
        (a list of node id strings). Returns the number of committed edges
        closed.
    """
    return (
        f"MATCH (d:{NODE_IDENTITY_LABEL}:Document {{id: $document_node_id}})"
        f"-[r:{HAS_PART}]->(c) "
        f"WHERE r.invalid_at IS NULL AND {pending_filter_clause('r')} "
        "AND NOT c.id IN $keep_node_ids "
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
    None or empty crosses every type except the structure types
    (``HAS_PART``, ``HAS_CHILD``, ``HAS_DOCUMENT``); pass those explicitly
    to opt in to crossing them.

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

    Result nodes are restricted to entities that carry the identity label
    (``NODE_IDENTITY_LABEL``) and are **not** ``Chunk`` nodes: chunks are
    intermediate path nodes only, never returned as BFS results. Section,
    Table, Figure and Source nodes are never returned either. Every path node
    must carry the identity label, so paths cannot cross candidates.

    Args:
        depth: The maximum BFS hops. Clamped to [1, 10].
        limit: The maximum number of result nodes. Clamped to [1, 1000].
        filters: Optional flat-dict filter applied to neighbor nodes.
            A scalar value means exact match, a list means any of.
        relation_types: Optional relationship types the traversal may
            cross. None or empty crosses every type except the structure
            types, which must be named explicitly to cross.
        direction: Which way a hop walks each relationship. Defaults
            to ``"both"``.
        document_ids: Optional document ids that must mention each result
            entity through a ``MENTIONED_IN`` edge. A chunk and a mention
            count only when committed, or written by the job in ``$job_id``.
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
    path_guard = pending_filter_clause("r", "job_id")
    if not relation_types:
        path_guard += f" AND NOT type(r) IN {_DEFAULT_TRAVERSAL_EXCLUSIONS}"
    base_where = (
        f"neighbor:{NODE_IDENTITY_LABEL} AND NOT neighbor:Chunk "
        "AND NOT neighbor.id IN $seed_ids "
        f"AND {_STRUCTURE_LABEL_EXCLUSIONS} "
        f"AND {pending_filter_clause('neighbor', 'job_id')} "
        f"AND {_identity_path_clause('path')} "
        f"AND ALL(r IN relationships(path) WHERE {path_guard})"
    )
    document_suffix = (
        " AND EXISTS { "
        "MATCH (neighbor)<-[scoped_mention:MENTIONED_IN]-"
        f"(scoped_chunk:{NODE_IDENTITY_LABEL}:Chunk) "
        "WHERE scoped_chunk.document_id IN $document_ids "
        f"AND {pending_filter_clause('scoped_chunk', 'job_id')} "
        f"AND {pending_filter_clause('scoped_mention', 'job_id')} }}"
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
        f"MATCH (start:{NODE_IDENTITY_LABEL} {{id: seed_id}}) "
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
        f"MATCH (chunk:{NODE_IDENTITY_LABEL}:Chunk)-[mention:MENTIONED_IN]->"
        f"(entity:{NODE_IDENTITY_LABEL}) "
        "WHERE EXISTS { "
        f"MATCH (document:{NODE_IDENTITY_LABEL}:Document)"
        f"-[part:{HAS_PART}]->(chunk) "
        "WHERE document.id IN $document_ids AND part.invalid_at IS NULL "
        f"AND {pending_filter_clause('document', 'job_id')} "
        f"AND {pending_filter_clause('part', 'job_id')} }} "
        f"AND {pending_filter_clause('entity', 'job_id')} "
        f"AND {pending_filter_clause('chunk', 'job_id')} "
        f"AND {pending_filter_clause('mention', 'job_id')} "
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
    ``bfs_expand_query`` does and cannot be widened into a multi-hop
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
        f"MATCH (seed:{NODE_IDENTITY_LABEL} {{id: seed_id}}) "
        f"MATCH (seed){left_arrow}[r{type_pattern}]{right_arrow}(neighbor) "
        f"WHERE neighbor:{NODE_IDENTITY_LABEL} "
        f"AND NOT neighbor:Chunk AND NOT neighbor:Community "
        f"AND NOT type(r) IN {_NON_ENTITY_RELATIONS} "
        f"AND {pending_filter_clause('r', 'job_id')} "
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
        f"MATCH (c:{NODE_IDENTITY_LABEL}:Chunk)-[:MENTIONED_IN]-> "
        f"(e:{NODE_IDENTITY_LABEL} {{id: entity_id}}) "
        f"WHERE {pending_filter_clause('c', 'job_id')} "
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
        f"MATCH (c:{NODE_IDENTITY_LABEL}:Chunk {{id: chunk_id}})"
        f"-[:MENTIONED_IN]->(e:{NODE_IDENTITY_LABEL}) "
        f"WHERE {pending_filter_clause('e', 'job_id')} "
        "RETURN DISTINCT e, e.id AS id"
    )


def fetch_all_relations_query_cursor() -> str:
    """Build Cypher paginating every live domain relationship via keyset.

    Pages every live domain relationship by keyset, so cost does not grow
    with the page number. Orders by ``(a.id, b.id, type(r), r.id)`` and
    pages by the last seen tuple; the first page uses ``last_a=""``,
    ``last_b=""``, ``last_type=""`` and ``last_rel_id=""``. It excludes
    every edge an in-flight Cutover Job wrote. Used by
    Graph.detect_communities() to build the weighted edge list for
    clustering; it skips MENTIONED_IN and MEMBER_OF (system edges, not
    entity-graph topology) and any endpoint that is a Chunk or a Community.

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
        f"AND NOT a:Chunk AND NOT b:Chunk "
        f"AND NOT a:Community AND NOT b:Community "
        f"AND NOT type(r) IN {_NON_ENTITY_RELATIONS} "
        f"AND {pending_filter_clause('r')} "
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
    new one is written. The stale copy is deleted only when the writer owns
    it. A committed copy is left alone, so the write fails on the per-type
    uniqueness constraint from ``relation_id_constraint_query``. Production
    ids hash the endpoints, so an id's endpoints never move in practice. A
    relationship's type is immutable once
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

    Both endpoints must carry the identity label. Candidate edge types are
    reserved for the candidate store and cannot be written here.

    The Cutover Job tag is set only when the ``MERGE`` creates the
    relationship, so the tag means "this job created this edge". A write
    over a relationship the job did not create is not applied: the row
    reports ``written`` false, and the store defers the write to the job's
    commit transaction.

    Args:
        rel_type: The relationship type. Must already be validated.

    Returns:
        A parameterized Cypher query expecting a ``$records`` list parameter whose
        items carry ``id``, ``start_id``, ``end_id``, ``properties``, and
        ``pending_job_id`` keys. ``properties`` may include
        ``source_chunk_ids``; other keys are applied as-is. The query returns
        ``id`` and ``written`` for every record whose endpoints matched and was
        processed.

    Raises:
        ValueError: ``rel_type`` is unsafe or reserved for candidate edges.
    """
    safe_type = validate_identifier(rel_type)
    if safe_type in CANDIDATE_EDGE_TYPES:
        raise ValueError(f"{safe_type!r} is reserved for the candidate store")
    own = own_row_expression("r", "record.pending_job_id")
    own_stale = own_row_expression("stale", "record.pending_job_id")
    return (
        f"UNWIND $records AS record "
        f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: record.start_id}}) "
        f"MATCH (b:{NODE_IDENTITY_LABEL} {{id: record.end_id}}) "
        f"OPTIONAL MATCH (x:{NODE_IDENTITY_LABEL})"
        f"-[stale:{safe_type} {{id: record.id}}]->(y:{NODE_IDENTITY_LABEL}) "
        f"WHERE (x.id <> record.start_id OR y.id <> record.end_id) "
        f"AND {own_stale} "
        f"FOREACH (_ IN CASE WHEN stale IS NULL THEN [] ELSE [1] END | DELETE stale) "
        f"MERGE (a)-[r:{safe_type} {{id: record.id}}]->(b) "
        f"ON CREATE SET r.{PENDING_JOB_ID_PROPERTY} = record.pending_job_id "
        f"WITH r, record, {own} AS own, "
        f"coalesce(r.source_chunk_ids, []) AS existing_source_chunk_ids "
        f"FOREACH (_ IN CASE WHEN own THEN [1] ELSE [] END | "
        f"SET r += record.properties "
        f"SET r.source_chunk_ids = [x IN existing_source_chunk_ids "
        f"WHERE NOT x IN coalesce(record.properties.source_chunk_ids, [])] "
        f"+ coalesce(record.properties.source_chunk_ids, []) "
        f"SET r.id = record.id) "
        f"RETURN record.id AS id, own AS written"
    )


def shortest_path_distance_query() -> str:
    """Build Cypher measuring the shortest committed path between entities.

    The path may cross committed nodes and relationships only, so an
    in-flight Cutover Job never shortens a distance.

    Returns:
        Parameterized Cypher expecting ``$seed_ids`` and ``$target_ids``
        (lists of string ids). Returns one ``dist`` per seed and target pair
        joined by a path.
    """
    return (
        "UNWIND $seed_ids AS seed_id "
        "UNWIND $target_ids AS target_id "
        "MATCH path = shortestPath("
        f"(seed:{NODE_IDENTITY_LABEL} {{id: seed_id}})"
        f"-[*]-(target:{NODE_IDENTITY_LABEL} {{id: target_id}})"
        f") WHERE {pending_path_filter_clause('path')} "
        f"AND {_identity_path_clause('path')} "
        "RETURN length(path) AS dist"
    )
