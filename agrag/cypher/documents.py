"""Cypher reads and writes for persisted Document nodes."""

from agrag.common.data_models.candidate import CANDIDATE_LABEL, EVIDENCED_BY
from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.cutover_job import CUTOVER_JOB_LABEL
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


def retire_document_version_query() -> str:
    """Build Cypher clearing the current content hash after source deletion."""
    return (
        f"MATCH (n:{NODE_IDENTITY_LABEL}:Document {{id: $document_node_id}}) "
        "SET n.current_content_hash = null "
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

    The record id is the caller's, so a commit that is repeated after a crash
    names the same record. When the document already has a record with ``$id``,
    the query changes nothing and returns no row, so the sequence is not
    incremented twice.

    Returns:
        Parameterized Cypher expecting ``$document_node_id``, ``$id``,
        ``$document_key``, ``$verb``, ``$content_hash``,
        ``$previous_content_hash``, ``$version_id``, ``$activated_at`` and
        ``$job_id``. ``$activated_at`` is an ISO-8601 string stored as given.
        Null hashes and version ids are left unset on the node. Returns the new
        ``activation_seq`` on the first run, and no row when the record exists
        or the document is absent.
    """
    return (
        f"MATCH (d:{NODE_IDENTITY_LABEL}:Document {{id: $document_node_id}}) "
        f"OPTIONAL MATCH (d)-[:{HAS_ACTIVATION}]->"
        f"(existing:{NODE_IDENTITY_LABEL}:{DOCUMENT_ACTIVATION_LABEL} {{id: $id}}) "
        "WITH d, existing WHERE existing IS NULL "
        "SET d.activation_seq = coalesce(d.activation_seq, 0) + 1 "
        "WITH d "
        f"CREATE (d)-[:{HAS_ACTIVATION}]->"
        f"(a:{NODE_IDENTITY_LABEL}:{DOCUMENT_ACTIVATION_LABEL} {{"
        "id: $id, document_key: $document_key, verb: $verb, "
        "content_hash: $content_hash, "
        "previous_content_hash: $previous_content_hash, "
        "version_id: $version_id, activation_seq: d.activation_seq, "
        "activated_at: $activated_at, job_id: $job_id}) "
        "RETURN a.activation_seq AS activation_seq"
    )


def flag_decisions_for_activation_query() -> str:
    """Build a project-independent direct flag for one committed activation."""
    return (
        f"MATCH (doc:Document)-[:{HAS_ACTIVATION}]->"
        f"(a:{DOCUMENT_ACTIVATION_LABEL} {{id: $activation_id}}) "
        "MATCH (d:MemoryDecision {status: 'active'}) "
        f"-[:{HAS_SUPPORT}]->"
        "(s:MemorySupport {kind: 'document', current: true}) "
        "WHERE s.document_node_id = doc.id "
        "AND (a.verb IN ['delete', 'purge'] "
        "OR s.recorded_activation_seq <> a.activation_seq) "
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


def source_status_query() -> str:
    """Build Cypher reading committed source, activation and job state."""
    return (
        f"OPTIONAL MATCH (d:{NODE_IDENTITY_LABEL}:Document "
        "{document_key: $document_key}) "
        f"OPTIONAL MATCH (job:{CUTOVER_JOB_LABEL} {{document_key: $document_key}}) "
        "WHERE job.status IN ['pending', 'rolling_back', 'committed', 'cleaning'] "
        "WITH d, job ORDER BY job.created_at DESC "
        "WITH d, collect(job)[0] AS job "
        f"OPTIONAL MATCH (d)-[part:{HAS_PART}]->"
        f"(chunk:{NODE_IDENTITY_LABEL}:Chunk) "
        "WHERE part.invalid_at IS NULL "
        f"AND {pending_filter_clause('d')} "
        f"AND {pending_filter_clause('part')} "
        f"AND {pending_filter_clause('chunk')} "
        "WITH d, job, collect(part.version_id)[0] AS version_id, "
        "count(part) > 0 AS has_current, "
        "count(CASE WHEN chunk.id IS NOT NULL AND "
        "chunk.extraction_fingerprint IS NULL THEN 1 END) = 0 AS complete "
        f"OPTIONAL MATCH (d)-[:{HAS_ACTIVATION}]->(a:{NODE_IDENTITY_LABEL}:"
        f"{DOCUMENT_ACTIVATION_LABEL}) "
        "WITH d, job, version_id, has_current, complete, a "
        "ORDER BY a.activation_seq DESC "
        "WITH d, job, version_id, has_current, complete, collect(a)[0] AS activation "
        f"RETURN d IS NOT NULL AND {pending_filter_clause('d')} "
        "AS document_exists, "
        f"CASE WHEN {pending_filter_clause('d')} "
        "THEN d.current_content_hash END AS content_hash, "
        f"CASE WHEN {pending_filter_clause('d')} "
        "THEN d.activation_seq END AS activation_seq, version_id, "
        "has_current, complete, "
        "activation.verb AS last_verb, job.id AS job_id, "
        "job.status AS job_status, job.lease_expires_at AS lease_expires_at, "
        "job.created_at AS job_created_at, "
        "job.error AS job_error, job.lease_expires_at < timestamp() AS lease_expired"
    )


def document_content_ids_query() -> str:
    """Build Cypher reading a bounded set of all stored content nodes.

    Returns:
        Parameterized Cypher expecting ``$document_node_id`` and ``$limit``.
        Returns one row per chunk, section, table or figure, up to ``$limit``.
    """
    return (
        f"MATCH (n:{NODE_IDENTITY_LABEL}) "
        "WHERE n.document_id = $document_node_id "
        f"AND (n:{CHUNK_LABEL} OR n:{SECTION_LABEL} OR n:{TABLE_LABEL} "
        f"OR n:{FIGURE_LABEL}) "
        "RETURN n.id AS id LIMIT $limit"
    )


def document_mentioned_entities_query() -> str:
    """Build Cypher listing the entities that any version's chunks mention.

    Returns:
        Parameterized Cypher expecting ``$document_node_id`` and ``$limit``.
        Returns up to ``$limit`` distinct entity ids.
    """
    return (
        f"MATCH (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
        "{document_id: $document_node_id})"
        f"-[:MENTIONED_IN]->(e:{NODE_IDENTITY_LABEL}) "
        "RETURN DISTINCT e.id AS id LIMIT $limit"
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
        "MATCH ()-[r]->() "
        "WHERE r.source_chunk_ids IS NOT NULL "
        "CALL { WITH r "
        f"MATCH (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
        "{document_id: $document_node_id}) "
        "WHERE c.id IN r.source_chunk_ids "
        "RETURN collect(c.id) AS present } "
        "WITH r, present WHERE size(present) > 0 "
        "SET r.source_chunk_ids = "
        "[cid IN r.source_chunk_ids WHERE NOT (cid IN present)] "
        "WITH r WHERE size(r.source_chunk_ids) = 0 "
        "DELETE r RETURN count(r) AS deleted"
    )


def document_cited_relation_endpoints_query() -> str:
    """Build Cypher listing the endpoints of relations that cite the document.

    These are the entities a purge may leave without evidence even when no chunk
    still mentions them, so they are offered to the pruning pass with the mentioned
    entities.

    Returns:
        Parameterized Cypher expecting ``$document_node_id`` and ``$limit``.
        Returns up to ``$limit`` distinct entity ids.
    """
    return (
        f"MATCH (a:{NODE_IDENTITY_LABEL})-[r]->(b:{NODE_IDENTITY_LABEL}) "
        "WHERE r.source_chunk_ids IS NOT NULL "
        "CALL { WITH r "
        f"MATCH (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
        "{document_id: $document_node_id}) "
        "WHERE c.id IN r.source_chunk_ids "
        "WITH 1 AS h LIMIT 1 RETURN count(h) AS n } "
        "WITH a, b, n WHERE n > 0 "
        "UNWIND [a.id, b.id] AS id RETURN DISTINCT id LIMIT $limit"
    )


def document_cited_relation_ids_query() -> str:
    """Build Cypher reading a bounded set of relations citing document chunks."""
    return (
        "MATCH ()-[r]->() WHERE r.source_chunk_ids IS NOT NULL "
        "CALL { WITH r "
        f"MATCH (c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} "
        "{document_id: $document_node_id}) "
        "WHERE c.id IN r.source_chunk_ids "
        "WITH 1 AS h LIMIT 1 RETURN count(h) AS n } "
        "WITH r, n WHERE n > 0 "
        "RETURN r.id AS id LIMIT $limit"
    )


def document_pending_candidate_ids_query() -> str:
    """Build Cypher reading a bounded set of pending candidates on document chunks."""
    return (
        f"MATCH (n:{CANDIDATE_LABEL})-[:{EVIDENCED_BY}]->"
        f"(c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} {{document_id: $document_node_id}}) "
        "WHERE n.state = 'pending' RETURN DISTINCT n.id AS id LIMIT $limit"
    )


def purge_candidate_evidence_query() -> str:
    """Build Cypher deleting pending candidates evidenced by any version's chunks.

    Returns:
        Parameterized Cypher expecting ``$document_node_id``. Returns ``deleted``.
    """
    return (
        f"MATCH (n:{CANDIDATE_LABEL})-[:{EVIDENCED_BY}]->"
        f"(c:{NODE_IDENTITY_LABEL}:{CHUNK_LABEL} {{document_id: $document_node_id}}) "
        "WHERE n.state = 'pending' "
        "WITH DISTINCT n "
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
