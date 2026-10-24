"""Cypher for community retrieval reads."""

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.community import COMMUNITY_LABEL, MEMBER_OF_RELATION
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.structure import HAS_PART
from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.cypher.evidence import _CHUNK_FIELDS


def communities_for_entities_query(where_clause: str = "") -> str:
    """Build Cypher finding communities overlapping given entity ids.

    Args:
        where_clause: Optional parameterized Cypher ``WHERE`` clause
            (including the ``WHERE`` keyword) applied to the candidate
            community node ``c``, e.g. from
            ``SearchFilters.to_cypher_where("c")``. Empty applies no
            additional constraint. Community nodes carry no document or
            tenant scope, so a document- or property-scoped filter that
            names a property Community nodes never have makes this
            clause match nothing, returning no communities rather than
            an unscoped one.

    Returns:
        Parameterized Cypher expecting $entity_ids (list of string ids),
        $job_id (the in-flight Cutover Job's id, or null outside a job),
        and $top_k (max rows to return; must be non-negative, since
        Neo4j rejects a negative LIMIT). Returns each overlapping
        community node and its overlap count, highest overlap first.
        Community nodes are never written by a Cutover Job, but the
        member entity anchor is: the ``$job_id`` guard keeps a
        community from being found through a pending member edge.
    """
    filter_predicate = where_clause.removeprefix("WHERE ").strip()
    filter_suffix = f"AND {filter_predicate} " if filter_predicate else ""
    return (
        "UNWIND $entity_ids AS entity_id "
        f"MATCH (e:{NODE_IDENTITY_LABEL} {{id: entity_id}})"
        f"-[r:{MEMBER_OF_RELATION}]->(c:{COMMUNITY_LABEL}) "
        f"WHERE {pending_filter_clause('r', 'job_id')} "
        f"{filter_suffix}"
        "WITH c, count(DISTINCT entity_id) AS overlap "
        "RETURN c, overlap ORDER BY overlap DESC LIMIT $top_k"
    )


def hydrate_communities_by_id_query() -> str:
    """Build Cypher fetching committed community nodes by id.

    Returns:
        Parameterized Cypher expecting ``$ids`` (list of string ids).
    """
    return (
        f"UNWIND $ids AS id MATCH (n:{NODE_IDENTITY_LABEL}:{COMMUNITY_LABEL} "
        f"{{id: id}}) WHERE {pending_filter_clause('n')} RETURN n"
    )


def community_candidates_query(search_call: str) -> str:
    """Build the vector search query over the Community embedding index.

    Args:
        search_call: The index search fragment from
            ``GraphStore.vector_search_call`` for ``Community.embedding``.

    Returns:
        Parameterized Cypher expecting $vector (the query embedding), $k
        (candidates to read), and the parameters that come with
        ``search_call``. It returns the ``community_id`` and the search
        ``score`` of every candidate, best first, committed communities only.
    """
    return (
        f"{search_call} "
        f"WHERE {pending_filter_clause('node')} "
        "RETURN node.id AS community_id, score ORDER BY score DESC, community_id"
    )


def theme_passages_query() -> str:
    """Build the query that returns the visible in-scope passages of themes.

    For each community id, the query matches member entities through their
    ``MEMBER_OF`` edge, then the passages that mention each member. A passage is
    visible when its ``HAS_PART`` edge is open, its chunk matches the current
    content hash of its document, nothing on the path is written by an in-flight
    job, and the document is in ``$scope_ids``. Chunks are grouped and ranked by
    the count of distinct member entities that mention them, then by chunk
    position, and each community keeps at most ``$support_limit`` chunks.

    Returns:
        Parameterized Cypher expecting $community_ids (list of string ids),
        $scope_ids and $support_limit. One row per community and kept chunk,
        with the ``community_id``, the chunk map and the document columns that
        ``stored_chunk`` reads, the ``member_count`` of distinct members that
        mention the chunk, and the distinct ``member_names`` of those members.
        The caller collects the per-community member list from the rows. A
        community id with no visible passage gives no row, so the caller drops
        it.
    """
    return (
        "UNWIND $community_ids AS candidate_id "
        f"MATCH (community:{NODE_IDENTITY_LABEL}:{COMMUNITY_LABEL} "
        f"{{id: candidate_id}}) "
        f"WHERE {pending_filter_clause('community')} "
        f"MATCH (entity:{NODE_IDENTITY_LABEL})-"
        f"[r:{MEMBER_OF_RELATION}]->(community) "
        f"WHERE {pending_filter_clause('r')} "
        f"MATCH (document:{NODE_IDENTITY_LABEL}:{DOCUMENT_LABEL})"
        f"-[part:{HAS_PART}]->(chunk:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL})"
        "-[mention:MENTIONED_IN]->(entity) "
        "WHERE part.invalid_at IS NULL "
        "AND chunk.content_hash = document.current_content_hash "
        "AND document.id IN $scope_ids "
        f"AND {pending_filter_clause('document')} "
        f"AND {pending_filter_clause('part')} "
        f"AND {pending_filter_clause('chunk')} "
        f"AND {pending_filter_clause('mention')} "
        "WITH community.id AS community_id, chunk, chunk.index AS position, "
        "part.version_id AS version_id, "
        "toString(part.invalid_at) AS closed_at, "
        "document.document_key AS document_key, "
        "document.current_content_hash AS current_content_hash, "
        "count(DISTINCT entity) AS member_count, "
        "collect(DISTINCT entity.name) AS member_names "
        "ORDER BY member_count DESC, position "
        "LIMIT $support_limit "
        f"RETURN community_id, chunk {_CHUNK_FIELDS} AS chunk, "
        "version_id, closed_at, document_key, current_content_hash, "
        "member_count, member_names, position "
        "ORDER BY community_id, member_count DESC, position"
    )
