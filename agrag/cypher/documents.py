"""Cypher reads for persisted Document nodes."""

from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.entities import NODE_IDENTITY_LABEL


def find_document_query() -> str:
    """Build Cypher reading one Document node by its stable key.

    Returns:
        Parameterized Cypher expecting ``$document_key``. Returns the node's
        ``id`` and ``current_content_hash``.
    """
    return (
        f"MATCH (n:{NODE_IDENTITY_LABEL}:Document {{document_key: $document_key}}) "
        "RETURN n.id AS id, n.current_content_hash AS current_content_hash"
    )


def current_chunker_hash_query() -> str:
    """Build Cypher reading the chunker fingerprint of a document's chunks.

    Follows only open ``PART_OF`` edges to committed chunks, so a version a
    pending job wrote is never read as the current one.

    Returns:
        Parameterized Cypher expecting ``$document_key``. Returns at most
        one ``chunker_hash``.
    """
    return (
        f"MATCH (d:{NODE_IDENTITY_LABEL}:Document {{document_key: $document_key}})"
        f"-[p:PART_OF]->(c:{NODE_IDENTITY_LABEL}:Chunk) "
        f"WHERE p.invalid_at IS NULL AND {pending_filter_clause('p')} "
        f"AND {pending_filter_clause('c')} "
        "RETURN c.chunker_hash AS chunker_hash LIMIT 1"
    )
