"""Cypher builders for evidence discovery and fetch.

Discovery attaches one visibility clause to both search legs. Pending writes,
superseded chunks and out-of-scope documents are marked invisible inside the
query, so the escalation loop in discovery counts only visible rows.
"""

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.structure import HAS_PART
from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.entities import NODE_IDENTITY_LABEL


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
        Parameterized Cypher expecting $index (the index name), $query (Lucene
        terms built from plain words), $k (candidates to read), and $scope_ids.
        It returns every candidate, best score first. See ``_candidate_tail``.
    """
    return (
        "CALL db.index.fulltext.queryNodes($index, $query, {limit: $k}) "
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
        Parameterized Cypher expecting $names and returning one ``name`` and
        ``state`` row per index that exists. A missing index has no row.
    """
    return "SHOW INDEXES YIELD name, state WHERE name IN $names RETURN name, state"


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
