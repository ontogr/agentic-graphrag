"""Cypher reads and writes for persisted Document nodes."""

from agrag.common.data_models.structure import (
    DOCUMENT_ACTIVATION_LABEL,
    HAS_ACTIVATION,
    HAS_PART,
)
from agrag.cypher._pending_filter import pending_filter_clause
from agrag.cypher.entities import NODE_IDENTITY_LABEL


def find_document_query() -> str:
    """Build Cypher reading one Document node by its stable key.

    Returns:
        Parameterized Cypher expecting ``$document_key``. Returns the node's
        ``id``, ``current_content_hash``, ``published_at`` and ``content_date``.
        Skips a node an in-flight job
        wrote, so an uncommitted hash never counts as the current one.
    """
    return (
        f"MATCH (n:{NODE_IDENTITY_LABEL}:Document {{document_key: $document_key}}) "
        f"WHERE {pending_filter_clause('n')} "
        "RETURN n.id AS id, n.current_content_hash AS current_content_hash, "
        "n.published_at AS published_at, n.content_date AS content_date"
    )


def update_document_dates_query() -> str:
    """Build Cypher to replace only the two stored document date properties."""
    return (
        f"MATCH (n:{NODE_IDENTITY_LABEL}:Document {{id: $document_node_id}}) "
        "SET n.published_at = $published_at, n.content_date = $content_date "
        "RETURN n.id AS id"
    )


def current_run_record_query() -> str:
    """Build Cypher reading the run record of a document's current chunks.

    Follows only open ``HAS_PART`` edges to committed chunks, so a version a
    pending job wrote is never read as the current one. The chunk of the
    newest open version is read first.

    Returns:
        Parameterized Cypher expecting ``$document_key``. Returns at most one
        row with ``version_id`` (from the open edge), ``chunker_hash``,
        ``schema_fingerprint`` and ``extraction_fingerprint``. No row means the
        document has no open chunk.
    """
    return (
        f"MATCH (d:{NODE_IDENTITY_LABEL}:Document {{document_key: $document_key}})"
        f"-[p:{HAS_PART}]->(c:{NODE_IDENTITY_LABEL}:Chunk) "
        f"WHERE p.invalid_at IS NULL AND {pending_filter_clause('p')} "
        f"AND {pending_filter_clause('c')} "
        "RETURN p.version_id AS version_id, "
        "c.chunker_hash AS chunker_hash, "
        "c.schema_fingerprint AS schema_fingerprint, "
        "c.extraction_fingerprint AS extraction_fingerprint "
        "ORDER BY p.valid_at DESC LIMIT 1"
    )


def set_chunk_extraction_fingerprint_query() -> str:
    """Build Cypher stamping existing chunks with a new extraction fingerprint.

    The in-place re-extract keeps the chunk nodes, so it cannot write the new
    stamp with the chunk upsert: a pending write over a committed node cannot
    be undone. The cutover job runs this inside its commit transaction.

    Returns:
        Parameterized Cypher expecting ``$chunk_ids`` (a list of id strings) and
        ``$extraction_fingerprint``. Returns the number of chunks stamped.
    """
    return (
        f"MATCH (c:{NODE_IDENTITY_LABEL}:Chunk) WHERE c.id IN $chunk_ids "
        "SET c.extraction_fingerprint = $extraction_fingerprint "
        "RETURN count(c) AS stamped"
    )


def record_activation_query() -> str:
    """Build Cypher recording one committed change to a document.

    Increments the document's ``activation_seq`` and creates a
    ``DocumentActivation`` node that carries the new value, linked to the
    document by ``HAS_ACTIVATION``. The cutover job runs it in its commit
    transaction, so a record exists exactly when its change is committed.

    Returns:
        Parameterized Cypher expecting ``$document_node_id``, ``$id``,
        ``$document_key``, ``$verb``, ``$content_hash``,
        ``$previous_content_hash``, ``$version_id`` and ``$job_id``. Null
        hashes and version ids are left unset on the node. Returns the new
        ``activation_seq``.
    """
    return (
        f"MATCH (d:{NODE_IDENTITY_LABEL}:Document {{id: $document_node_id}}) "
        "SET d.activation_seq = coalesce(d.activation_seq, 0) + 1 "
        "WITH d "
        f"CREATE (d)-[:{HAS_ACTIVATION}]->"
        f"(a:{NODE_IDENTITY_LABEL}:{DOCUMENT_ACTIVATION_LABEL} {{"
        "id: $id, document_key: $document_key, verb: $verb, "
        "content_hash: $content_hash, "
        "previous_content_hash: $previous_content_hash, "
        "version_id: $version_id, activation_seq: d.activation_seq, "
        "activated_at: datetime(), job_id: $job_id}) "
        "RETURN a.activation_seq AS activation_seq"
    )
