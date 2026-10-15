"""Cypher builders for evidence discovery and fetch.

Discovery attaches one visibility clause to both search legs. Pending writes,
superseded chunks and out-of-scope documents are marked invisible inside the
query, so the escalation loop in discovery counts only visible rows.
"""

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.navigation import NavigationRelation
from agrag.common.data_models.structure import (
    HAS_CHILD,
    HAS_PART,
    SECTION_LABEL,
    TABLE_LABEL,
)
from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.entities import NODE_IDENTITY_LABEL, validate_identifier


# Chunk fields that evidence reads. The embedding is left out, and the text of a
# candidate is returned only when its document was found to be visible.
_CHUNK_FIELDS = (
    "{.id, .document_id, .content_hash, .index, .text, .provenance, "
    ".heading_path, .content_kind, .chunker, .chunker_hash, "
    ".schema_fingerprint, .extraction_fingerprint, .section_ids, .created_at}"
)


def _candidate_tail() -> str:
    """Return the clause that marks each candidate chunk as visible or not.

    Every candidate row is returned. A candidate is visible when it is committed,
    belongs to a document in ``$scope_ids``, and has an open ``HAS_PART`` edge from
    a committed Document node. Invisible candidates come back with null document
    fields. The caller counts all candidates to tell an exhausted index from a
    search that needs more candidates, and it keeps the visible rows.
    """
    return (
        f"OPTIONAL MATCH (document:{NODE_IDENTITY_LABEL}:{DOCUMENT_LABEL})"
        f"-[part:{HAS_PART}]->(node) "
        "WHERE document.id = node.document_id AND part.invalid_at IS NULL "
        "AND node.document_id IN $scope_ids "
        f"AND {pending_filter_clause('node')} "
        "AND node.content_hash = document.current_content_hash "
        f"AND {pending_filter_clause('document')} "
        f"AND {pending_filter_clause('part')} "
        "RETURN node.id AS chunk_id, "
        f"CASE WHEN document IS NULL THEN null ELSE node {_CHUNK_FIELDS} END "
        "AS chunk, score, "
        "document.document_key AS document_key, document.title AS title, "
        "document.current_content_hash AS current_content_hash "
        "ORDER BY score DESC, chunk_id"
    )


def lexical_candidates_query() -> str:
    """Build the full-text discovery query over the Chunk text index.

    Returns:
        Parameterized Cypher expecting $index (the index name), $fulltext_terms
        (Lucene terms built from plain words), $k (candidates to read), and $scope_ids.
        It returns every candidate, best score first. See ``_candidate_tail``.
    """
    return (
        "CALL db.index.fulltext.queryNodes($index, $fulltext_terms, {limit: $k}) "
        "YIELD node, score " + _candidate_tail()
    )


def semantic_candidates_query() -> str:
    """Build the vector discovery query over the Chunk embedding index.

    Returns:
        Parameterized Cypher expecting $index (the index name), $vector (the query
        embedding), $k (candidates to read), and $scope_ids. It returns every
        candidate, best score first. See ``_candidate_tail``.
    """
    return (
        "CALL db.index.vector.queryNodes($index, $k, $vector) YIELD node, score "
        + _candidate_tail()
    )


def index_states_query() -> str:
    """Build the query that reads the state of named indexes.

    Returns:
        Parameterized Cypher expecting $names and returning one row per index that
        exists, with its ``state``, ``type``, ``labelsOrTypes`` and ``properties``.
        A missing index has no row.
    """
    return (
        "SHOW INDEXES YIELD name, state, populationPercent, type, labelsOrTypes, "
        "properties "
        "WHERE name IN $names "
        "RETURN name, state, populationPercent, type, labelsOrTypes, properties"
    )


def evidence_chunks_query(*, by_chunk_id: bool) -> str:
    """Build the query that loads the chunks of one document version.

    The query reads committed chunks of one document, including chunks of
    superseded versions, so a stored id keeps resolving after an update.

    Args:
        by_chunk_id: True to load one chunk by ``$chunk_id``, or False to load
            every chunk whose content hash starts with ``$content_hash_prefix``.

    Returns:
        Parameterized Cypher expecting $document_id, $content_hash_prefix and,
        when ``by_chunk_id`` is set, $chunk_id. Each row holds the chunk
        properties, the edge's ``version_id``, the edge's ``closed_at`` time (null
        while the edge is open), and the document key, title and current content
        hash.
    """
    chunk_filter = "AND chunk.id = $chunk_id " if by_chunk_id else ""
    return (
        f"MATCH (document:{NODE_IDENTITY_LABEL}:{DOCUMENT_LABEL} {{id: $document_id}})"
        f"-[part:{HAS_PART}]->(chunk:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL}) "
        "WHERE chunk.content_hash STARTS WITH $content_hash_prefix "
        f"{chunk_filter}"
        f"AND {pending_filter_clause('document')} "
        f"AND {pending_filter_clause('part')} "
        f"AND {pending_filter_clause('chunk')} "
        f"RETURN chunk {_CHUNK_FIELDS} AS chunk, part.version_id AS version_id, "
        "toString(part.invalid_at) AS closed_at, "
        "document.document_key AS document_key, document.title AS title, "
        "document.current_content_hash AS current_content_hash"
    )


def _neighbor_chunks_head(relation: NavigationRelation) -> str:
    """Return the match clause that binds the chunks next to an anchor chunk."""
    anchor = f"(anchor:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} {{id: $chunk_id}})"
    neighbor = f"(neighbor:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL})"
    if relation is NavigationRelation.PREVIOUS:
        return f"MATCH {neighbor}-[:NEXT_CHUNK]->{anchor} "
    if relation is NavigationRelation.NEXT:
        return f"MATCH {anchor}-[:NEXT_CHUNK]->{neighbor} "
    if relation is NavigationRelation.CHILDREN:
        return (
            f"MATCH (parent:{NODE_IDENTITY_LABEL})-[:{HAS_CHILD}]->{anchor} "
            f"MATCH (parent)-[:{HAS_CHILD}]->{neighbor} "
            "WHERE neighbor.id <> $chunk_id "
        )
    if relation is NavigationRelation.TABLE_CONTEXT:
        return (
            f"MATCH (parent:{NODE_IDENTITY_LABEL}:{TABLE_LABEL})"
            f"-[:{HAS_CHILD}]->{anchor} "
            f"MATCH (parent)-[:{HAS_CHILD}]->{neighbor} "
        )
    raise ValueError(f"{relation.value!r} does not select chunks")


def navigation_chunks_query(relation: NavigationRelation) -> str:
    """Build the query that returns the chunks related to one anchor chunk.

    Only chunks of the same document version as the anchor are returned. A
    neighbor must have a ``HAS_PART`` edge from the document with the version id
    of the anchor, and it must not be written by an in-flight job. The table
    context query is not bounded in Cypher, because the caller windows the rows
    around the anchor. Every other query returns at most ``$fetch`` rows.

    Args:
        relation: One of previous, next, children or table_context.

    Returns:
        Parameterized Cypher expecting $chunk_id, $document_id, $version_id and
        $fetch. Each row holds the chunk properties, the version id, the close
        time of the edge, the document key, the current content hash and the
        reading position of the neighbor.

    Raises:
        ValueError: ``relation`` does not select chunks.
    """
    tail = (
        f"MATCH (document:{NODE_IDENTITY_LABEL}:{DOCUMENT_LABEL} {{id: $document_id}})"
        f"-[part:{HAS_PART}]->(neighbor) "
        "WHERE part.version_id = $version_id "
        f"AND {pending_filter_clause('neighbor')} "
        f"AND {pending_filter_clause('part')} "
        f"AND {pending_filter_clause('document')} "
        f"RETURN neighbor {_CHUNK_FIELDS} AS chunk, part.version_id AS version_id, "
        "toString(part.invalid_at) AS closed_at, "
        "document.document_key AS document_key, "
        "document.current_content_hash AS current_content_hash, "
        "neighbor.index AS position ORDER BY position"
    )
    if relation is NavigationRelation.TABLE_CONTEXT:
        return _neighbor_chunks_head(relation) + tail
    return _neighbor_chunks_head(relation) + tail + " LIMIT $fetch"


def navigation_sections_query(relation: NavigationRelation) -> str:
    """Build the query that returns sections next to a chunk's own sections.

    ``parent`` returns the sections that hold the chunk. ``siblings`` returns the
    other sections under the same parent as those sections. Each row carries the
    heading of the section, the headings above it, and the first visible chunk of
    the section in the anchor's version. A section with no visible chunk is left
    out, because it has no passage to cite.

    Args:
        relation: Either parent or siblings.

    Returns:
        Parameterized Cypher expecting $section_ids (the section node ids of the
        anchor), $document_id, $version_id and $fetch. Each row holds the section
        position, its heading, the ancestor headings from the outermost down, and
        the first chunk row, with the same columns as ``navigation_chunks_query``.

    Raises:
        ValueError: ``relation`` is neither parent nor siblings.
    """
    if relation is NavigationRelation.PARENT:
        head = f"MATCH (section:{NODE_IDENTITY_LABEL}:{SECTION_LABEL}) "
        head += "WHERE section.id IN $section_ids "
    elif relation is NavigationRelation.SIBLINGS:
        head = (
            f"MATCH (owner:{NODE_IDENTITY_LABEL})"
            f"-[:{HAS_CHILD}]->(covering:{NODE_IDENTITY_LABEL}:{SECTION_LABEL}) "
            "WHERE covering.id IN $section_ids "
            f"MATCH (owner)-[:{HAS_CHILD}]->"
            f"(section:{NODE_IDENTITY_LABEL}:{SECTION_LABEL}) "
            "WHERE NOT section.id IN $section_ids "
        )
    else:
        raise ValueError(f"{relation.value!r} does not select sections")
    return (
        head + "WITH DISTINCT section "
        f"OPTIONAL MATCH (ancestor:{NODE_IDENTITY_LABEL}:{SECTION_LABEL})"
        f"-[:{HAS_CHILD}*]->(section) "
        "WITH section, ancestor ORDER BY ancestor.depth "
        "WITH section, collect(ancestor.heading) AS ancestors "
        "CALL { "
        "WITH section "
        f"MATCH (document:{NODE_IDENTITY_LABEL}:{DOCUMENT_LABEL} {{id: $document_id}})"
        f"-[part:{HAS_PART}]->(chunk:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL}) "
        "WHERE part.version_id = $version_id AND section.id IN chunk.section_ids "
        f"AND {pending_filter_clause('chunk')} "
        f"AND {pending_filter_clause('part')} "
        f"AND {pending_filter_clause('document')} "
        f"RETURN chunk {_CHUNK_FIELDS} AS chunk, part.version_id AS version_id, "
        "toString(part.invalid_at) AS closed_at, "
        "document.document_key AS document_key, "
        "document.current_content_hash AS current_content_hash, "
        "chunk.index AS chunk_position ORDER BY chunk_position LIMIT 1 "
        "} "
        "RETURN section.index AS position, section.heading AS heading, "
        "ancestors, chunk, version_id, closed_at, document_key, "
        "current_content_hash ORDER BY position LIMIT $fetch"
    )


def entity_labels_query() -> str:
    """Build the query that lists the indexes of entity labels.

    An entity label has a vector index on ``embedding`` and a full-text index on
    ``name``. Other labels may have only one of them, so the caller keeps the
    labels that have both.

    Returns:
        Cypher returning one row per index, with its ``labelsOrTypes`` list and
        ``type``. It takes no parameters. Neo4j 5 does not allow ``UNWIND``
        directly after ``SHOW``, so the caller flattens the lists.
    """
    return (
        "SHOW INDEXES YIELD labelsOrTypes, properties, type "
        "WHERE (type = 'VECTOR' AND properties = ['embedding']) "
        "OR (type = 'FULLTEXT' AND properties = ['name']) "
        "RETURN DISTINCT labelsOrTypes, type"
    )


def entity_candidates_query(label: str, *, lexical: bool) -> str:
    """Build the query that finds entity candidates of one label.

    Args:
        label: The entity label whose index is searched. It is validated here.
        lexical: True to search the full-text index of ``name``, or False to search
            the vector index of ``embedding``.

    Returns:
        Parameterized Cypher. The lexical form expects $index, $fulltext_terms and
        $k. The vector form expects $index, $vector and $k. Each row holds the
        ``entity_id`` and the search ``score``, best first. Pending entities are
        left out.

    Raises:
        ValueError: ``label`` is not a safe identifier.
    """
    safe_label = validate_identifier(label)
    if lexical:
        call = (
            "CALL db.index.fulltext.queryNodes($index, $fulltext_terms, {limit: $k}) "
        )
    else:
        call = "CALL db.index.vector.queryNodes($index, $k, $vector) "
    return (
        f"{call}YIELD node, score "
        f"WHERE node:{safe_label} AND {pending_filter_clause('node')} "
        "RETURN node.id AS entity_id, score ORDER BY score DESC, entity_id"
    )


def entity_mentions_query() -> str:
    """Build the query that returns the mention passages of entities in scope.

    For each entity, the query returns up to ``$support_limit`` passages of
    documents in ``$scope_ids``. Visible passages (open ``HAS_PART`` edge) come
    first. An entity with no passage in scope gives no row, so the caller drops
    it. An entity with only hidden passages gives rows with ``visible`` false.

    Returns:
        Parameterized Cypher expecting $entity_ids, $scope_ids and
        $support_limit. Each row holds ``entity_id``, the entity map with the
        embedding removed, the chunk map, the version id, the close time of the
        edge, the document key, the current content hash and ``visible``.
    """
    return (
        "UNWIND $entity_ids AS entity_id "
        f"MATCH (entity:{NODE_IDENTITY_LABEL} {{id: entity_id}}) "
        f"WHERE {pending_filter_clause('entity')} "
        "CALL { "
        "WITH entity "
        f"MATCH (document:{NODE_IDENTITY_LABEL}:{DOCUMENT_LABEL})"
        f"-[part:{HAS_PART}]->(chunk:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL})"
        f"-[mention:MENTIONED_IN]->(entity) "
        "WHERE document.id IN $scope_ids "
        f"AND {pending_filter_clause('document')} "
        f"AND {pending_filter_clause('part')} "
        f"AND {pending_filter_clause('chunk')} "
        f"AND {pending_filter_clause('mention')} "
        f"RETURN DISTINCT chunk {_CHUNK_FIELDS} AS chunk, "
        "part.version_id AS version_id, toString(part.invalid_at) AS closed_at, "
        "document.document_key AS document_key, "
        "document.current_content_hash AS current_content_hash, "
        "part.invalid_at IS NULL AS visible, chunk.index AS position "
        "ORDER BY visible DESC, position LIMIT $support_limit "
        "} "
        "RETURN entity.id AS entity_id, entity {.*, embedding: null} AS entity, "
        "chunk, version_id, closed_at, document_key, current_content_hash, visible "
        "ORDER BY entity_id, visible DESC, position"
    )


def explore_edges_query() -> str:
    """Build the query that returns the entity relations of a frontier.

    A relation counts when it joins two entities, and its type is either one of
    the given types or, when none is given, any schema type. Graph-owned types
    are never returned. The other entity must have a passage in scope. For each
    relation, the query returns up to ``$support_limit`` visible passages in scope
    from its ``source_chunk_ids``. A relation with no visible passage in scope has
    an empty ``supports`` list, and the caller decides what that means.

    Returns:
        Parameterized Cypher expecting $node_ids, $relation_types (empty for any
        schema type), $system_types, $scope_ids and $support_limit. Each row holds
        ``relation_id``, ``relation_type``, ``source_id``, ``target_id``,
        ``entity_id`` and ``name`` of the other entity, its ``label``, the count
        of ``source_chunk_ids`` and ``supports``, a list of maps with ``chunk``,
        ``version_id``, ``closed_at``, ``document_key`` and
        ``current_content_hash``.
    """
    return (
        "UNWIND $node_ids AS node_id "
        f"MATCH (node:{NODE_IDENTITY_LABEL} {{id: node_id}}) "
        f"WHERE {pending_filter_clause('node')} "
        f"MATCH (node)-[relation]-(other:{NODE_IDENTITY_LABEL}) "
        f"WHERE {pending_filter_clause('relation')} "
        f"AND {pending_filter_clause('other')} "
        "AND other.merge_key IS NOT NULL "
        "AND CASE WHEN size($relation_types) > 0 "
        "THEN type(relation) IN $relation_types "
        "ELSE NOT type(relation) IN $system_types END "
        "AND EXISTS { "
        f"MATCH (scope_document:{NODE_IDENTITY_LABEL}:{DOCUMENT_LABEL})"
        f"-[scope_part:{HAS_PART}]->"
        f"(scope_chunk:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL})"
        "-[:MENTIONED_IN]->(other) "
        "WHERE scope_document.id IN $scope_ids "
        f"AND {pending_filter_clause('scope_document')} "
        f"AND {pending_filter_clause('scope_part')} "
        f"AND {pending_filter_clause('scope_chunk')} "
        "} "
        "WITH DISTINCT relation, other, startNode(relation) AS source, "
        "endNode(relation) AS target "
        "CALL { "
        "WITH relation "
        "OPTIONAL MATCH (support_document:"
        f"{NODE_IDENTITY_LABEL}:{DOCUMENT_LABEL})"
        f"-[support_part:{HAS_PART}]->"
        f"(support_chunk:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL}) "
        "WHERE support_chunk.id IN coalesce(relation.source_chunk_ids, []) "
        "AND support_part.invalid_at IS NULL "
        "AND support_document.id IN $scope_ids "
        f"AND {pending_filter_clause('support_document')} "
        f"AND {pending_filter_clause('support_part')} "
        f"AND {pending_filter_clause('support_chunk')} "
        "WITH support_chunk, support_document, support_part "
        "ORDER BY support_chunk.index LIMIT $support_limit "
        "RETURN collect(CASE WHEN support_chunk IS NULL THEN NULL ELSE {"
        f"chunk: support_chunk {_CHUNK_FIELDS}, "
        "version_id: support_part.version_id, "
        "closed_at: toString(support_part.invalid_at), "
        "document_key: support_document.document_key, "
        "current_content_hash: support_document.current_content_hash} END) "
        "AS supports "
        "} "
        "RETURN relation.id AS relation_id, type(relation) AS relation_type, "
        "source.id AS source_id, target.id AS target_id, "
        "other.id AS entity_id, other.name AS name, "
        f"[label IN labels(other) WHERE label <> '{NODE_IDENTITY_LABEL}'][0] AS label, "
        "size(coalesce(relation.source_chunk_ids, [])) AS source_count, supports "
        "ORDER BY relation_id"
    )
