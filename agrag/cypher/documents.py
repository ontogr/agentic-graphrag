"""Cypher reads and writes for persisted Document nodes."""

from agrag.common.data_models.candidate import CANDIDATE_LABEL, EVIDENCED_BY
from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.decision import HAS_SUPPORT
from agrag.common.data_models.structure import (
    DOCUMENT_ACTIVATION_LABEL,
    FIGURE_LABEL,
    HAS_ACTIVATION,
    HAS_PART,
    SECTION_LABEL,
    TABLE_LABEL,
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


def flag_decisions_for_activation_query() -> str:
    """Build a project-independent direct flag for one committed activation."""
    return (
        f"MATCH (doc:Document)-[:{HAS_ACTIVATION}]->"
        f"(a:{DOCUMENT_ACTIVATION_LABEL} {{id: $activation_id}}) "
        "MATCH (d:MemoryDecision {status: 'active'}) "
        f"-[:{HAS_SUPPORT}]->"
        "(s:MemorySupport {kind: 'document'}) "
        "WHERE s.document_node_id = doc.id "
        "AND (a.verb IN ['delete', 'purge'] "
        "OR s.content_hash <> a.content_hash) "
        "WITH DISTINCT d, a "
        "MATCH (t:MemoryTask)-[:MADE]->(d) "
        "MATCH (p:MemoryProject {project_id: t.project_id}) "
        "SET p.review_incomplete = true, "
        "p.review_epoch = coalesce(p.review_epoch, 0) + 1, "
        "d.review_pending = true, d.review_state = 'needs_review', "
        "d.review_reason = CASE WHEN a.verb IN ['delete', 'purge'] "
        "THEN 'source_removed' ELSE 'source_changed' END "
        "RETURN count(DISTINCT d) AS flagged"
    )


def document_chunk_count_query() -> str:
    """Build Cypher counting the stored chunks of a document in every version.

    Returns:
        Parameterized Cypher expecting ``$document_node_id``. Returns ``chunks``.
    """
    return (
        f"MATCH (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
        "{document_id: $document_node_id}) "
        "RETURN count(c) AS chunks"
    )


def document_mentioned_entities_query() -> str:
    """Build Cypher listing the entities that any version's chunks mention.

    Returns:
        Parameterized Cypher expecting ``$document_node_id``. Returns ``id``, one
        row per entity.
    """
    return (
        f"MATCH (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
        "{document_id: $document_node_id})"
        f"-[:MENTIONED_IN]->(e:{NODE_IDENTITY_LABEL}) "
        "RETURN DISTINCT e.id AS id"
    )


def purge_relation_evidence_query() -> str:
    """Build Cypher removing every version's chunks from relation evidence.

    Matches relations by their ``source_chunk_ids`` directly, so a relation is
    found even when no chunk of the document still mentions its endpoints. Strips
    the document's chunk ids from each matched relation, and deletes a relation
    left with no evidence. Must run before the chunks are deleted, since it reads
    their ids.

    Returns:
        Parameterized Cypher expecting ``$document_node_id``. Returns ``deleted``,
        the relations removed.
    """
    return (
        f"MATCH (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
        "{document_id: $document_node_id}) "
        "WITH collect(DISTINCT c.id) AS chunk_ids "
        "MATCH ()-[r]->() "
        "WHERE r.source_chunk_ids IS NOT NULL "
        "AND any(cid IN r.source_chunk_ids WHERE cid IN chunk_ids) "
        "SET r.source_chunk_ids = "
        "[cid IN r.source_chunk_ids WHERE NOT cid IN chunk_ids] "
        "WITH DISTINCT r WHERE size(r.source_chunk_ids) = 0 "
        "WITH collect(r) AS doomed "
        "FOREACH (relation IN doomed | DETACH DELETE relation) "
        "RETURN size(doomed) AS deleted"
    )


def document_cited_relation_endpoints_query() -> str:
    """Build Cypher listing the endpoints of relations that cite the document.

    These are the entities a purge may leave without evidence even when no chunk
    still mentions them, so they are offered to the pruning pass with the mentioned
    entities.

    Returns:
        Parameterized Cypher expecting ``$document_node_id``. Returns ``id``, one
        row per entity.
    """
    return (
        f"MATCH (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
        "{document_id: $document_node_id}) "
        "WITH collect(DISTINCT c.id) AS chunk_ids "
        f"MATCH (a:{NODE_IDENTITY_LABEL})-[r]->(b:{NODE_IDENTITY_LABEL}) "
        "WHERE r.source_chunk_ids IS NOT NULL "
        "AND any(cid IN r.source_chunk_ids WHERE cid IN chunk_ids) "
        "WITH collect(DISTINCT a) + collect(DISTINCT b) AS ends "
        "UNWIND ends AS entity "
        "RETURN DISTINCT entity.id AS id"
    )


def purge_candidate_evidence_query() -> str:
    """Build Cypher deleting pending candidates evidenced by any version's chunks.

    Returns:
        Parameterized Cypher expecting ``$document_node_id``. Returns ``deleted``.
    """
    return (
        f"MATCH (n:{CANDIDATE_LABEL})-[:{EVIDENCED_BY}]->"
        f"(c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} {{document_id: $document_node_id}}) "
        "DETACH DELETE n RETURN count(n) AS deleted"
    )


def purge_document_nodes_query() -> str:
    """Build Cypher hard-deleting every chunk, section, table and figure of a document.

    Matches on the ``document_id`` property, so every version is removed. Detach
    deletion also removes the nodes' edges, including ``HAS_PART`` and
    ``MENTIONED_IN``. The Document node and its activation records stay.

    Returns:
        Parameterized Cypher expecting ``$document_node_id``. Returns ``deleted``.
    """
    return (
        f"MATCH (n:{NODE_IDENTITY_LABEL}) "
        "WHERE n.document_id = $document_node_id "
        f"AND (n:{CHUNK_LABEL} OR n:{SECTION_LABEL} OR n:{TABLE_LABEL} "
        f"OR n:{FIGURE_LABEL}) "
        "DETACH DELETE n RETURN count(n) AS deleted"
    )
