"""Cypher builders for durable, bounded decision review propagation."""

from agrag.common.data_models.decision import (
    DECISION_LABEL,
    DEPENDS_ON,
    HAS_SUPPORT,
    MADE,
    SUPERSEDES,
    SUPPORT_LABEL,
)
from agrag.common.data_models.structure import HAS_PART
from agrag.common.data_models.task import (
    HISTORY_RECORD_PROPERTY,
    PROJECT_LABEL,
    TASK_LABEL,
)


REVIEW_CHILD_PAGE_SIZE = 100


def flag_new_decision_for_review_query() -> str:
    """Flag a new decision that depends on a decision already needing review."""
    return (
        f"MATCH (t:{TASK_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        f"project_id: $project_id}})-[:{MADE}]->"
        f"(d:{DECISION_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "id: $decision_id}) "
        f"MATCH (p:{PROJECT_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id}) "
        f"MATCH (d)-[:{DEPENDS_ON}]->"
        f"(parent:{DECISION_LABEL} {{{HISTORY_RECORD_PROPERTY}: true}}) "
        "WHERE parent.review_state <> 'clear' OR p.review_incomplete "
        "SET d.review_state = 'needs_review', "
        "d.review_reason = 'dependency_review', d.review_pending = true, "
        "p.review_incomplete = true, "
        "p.review_epoch = coalesce(p.review_epoch, 0) + 1 "
        "RETURN d.id AS id"
    )


def claim_review_unit_query() -> str:
    """Lock one project's review state and claim one pending decision."""
    return (
        f"MATCH (p:{PROJECT_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id}) "
        "SET p.review_lock = coalesce(p.review_lock, 0) + 1 "
        "WITH p "
        f"OPTIONAL MATCH (t:{TASK_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id})"
        f"-[:{MADE}]->(d:{DECISION_LABEL} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, review_pending: true}}) "
        "WITH p, d ORDER BY d.created_at, d.id LIMIT 1 "
        "FOREACH (_ IN CASE WHEN d IS NULL THEN [] ELSE [1] END | "
        "SET d.review_pending = false, "
        "d.review_cursor = CASE WHEN coalesce(d.review_epoch, -1) <> p.review_epoch "
        "THEN null ELSE d.review_cursor END, d.review_epoch = p.review_epoch) "
        "RETURN d.id AS id"
    )


def expand_review_unit_query() -> str:
    """Flag one bounded page of active dependents of a claimed decision."""
    return (
        f"MATCH (p:{PROJECT_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id}) "
        f"MATCH (t:{TASK_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        f"project_id: $project_id}})-[:{MADE}]->"
        f"(parent:{DECISION_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "id: $decision_id}) "
        "CALL { WITH parent, p "
        f"MATCH (child:{DECISION_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "status: 'active'})"
        f"-[:{DEPENDS_ON}]->(parent) "
        "WHERE child.id > coalesce(parent.review_cursor, '') "
        "AND coalesce(child.review_epoch, -1) <> p.review_epoch "
        "WITH child ORDER BY child.id LIMIT $page_limit "
        "RETURN collect(child) AS page } "
        "WITH parent, p, page, size(page) = $page_limit AS more, "
        "page[..$child_limit] AS batch "
        "FOREACH (child IN batch | SET "
        "child.review_reason = CASE "
        "WHEN coalesce(child.review_state, 'clear') = 'needs_review' "
        "THEN child.review_reason ELSE 'dependency_review' END, "
        "child.review_state = 'needs_review', child.review_pending = true, "
        "child.review_cursor = CASE "
        "WHEN coalesce(child.review_epoch, -1) <> p.review_epoch "
        "THEN null ELSE child.review_cursor END, "
        "child.review_epoch = p.review_epoch) "
        "FOREACH (_ IN CASE WHEN size(batch) > 0 THEN [1] ELSE [] END | "
        "SET parent.review_cursor = batch[-1].id, parent.review_pending = more) "
        "RETURN size(batch) AS queued"
    )


def finish_review_propagation_query() -> str:
    """Clear the project incomplete marker only when its queue is empty."""
    return (
        f"MATCH (p:{PROJECT_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id}) "
        f"OPTIONAL MATCH (t:{TASK_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id})"
        f"-[:{MADE}]->(d:{DECISION_LABEL} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, review_pending: true}}) "
        "WITH p, count(d) AS pending "
        "FOREACH (_ IN CASE WHEN pending = 0 THEN [1] ELSE [] END | "
        "SET p.review_incomplete = false) "
        "RETURN pending"
    )


def current_document_query() -> str:
    """Read a document's current content hash and whether that version is live.

    A version is live while its ``HAS_PART`` edges are open. A soft-deleted
    document keeps its hash but has no open edges.
    """
    return (
        "MATCH (doc:Document {id: $id}) "
        f"OPTIONAL MATCH (doc)-[part:{HAS_PART}]->() WHERE part.invalid_at IS NULL "
        "RETURN doc.document_key AS key, doc.current_content_hash AS hash, "
        "doc.activation_seq AS activation_seq, count(part) > 0 AS live"
    )


def support_event_query() -> str:
    """Read an event support without exposing another project's events."""
    return (
        f"MATCH (t:Task {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id, name: $task_name})"
        f"-[:HAS_EVENT]->(e:Event {{{HISTORY_RECORD_PROPERTY}: true, "
        "seq: $seq}) "
        "RETURN e.id AS id, e.redacted_at AS redacted_at, e.truncated AS truncated"
    )


def support_history_query() -> str:
    """Read support history in creation order with a stable ordinal cursor."""
    return (
        f"MATCH (:Task {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id})-[:MADE]->"
        f"(:Decision {{{HISTORY_RECORD_PROPERTY}: true, id: $id}})"
        f"-[:HAS_SUPPORT]->(s:DecisionSupport {{{HISTORY_RECORD_PROPERTY}: true}}) "
        "WHERE s.ordinal > $after_ordinal "
        "RETURN s AS support ORDER BY s.ordinal LIMIT $limit"
    )


def next_support_ordinal_query() -> str:
    """Read the next append position without loading historical support bodies."""
    return (
        f"MATCH (:Task {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id})-[:MADE]->"
        f"(:Decision {{{HISTORY_RECORD_PROPERTY}: true, id: $id}})"
        f"-[:HAS_SUPPORT]->(s:DecisionSupport {{{HISTORY_RECORD_PROPERTY}: true}}) "
        "RETURN coalesce(max(s.ordinal), -1) + 1 AS ordinal"
    )


def replace_document_supports_query() -> str:
    """Archive current document supports and attach replacement supports.

    Old support nodes stay attached as history with their original evidence ids.
    """
    return (
        f"MATCH (t:{TASK_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        f"project_id: $project_id}})-[:{MADE}]->"
        f"(d:{DECISION_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "id: $decision_id}) "
        f"OPTIONAL MATCH (d)-[:{HAS_SUPPORT}]->"
        f"(old:{SUPPORT_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "kind: 'document', current: true}) "
        "SET old.current = false, old.reviewed_by = $reviewer, "
        "old.reviewed_at = $reviewed_at, "
        "old.review_explanation = $explanation "
        "WITH DISTINCT d UNWIND $supports AS item "
        f"CREATE (d)-[:{HAS_SUPPORT}]->(s:{SUPPORT_LABEL}) SET s = item "
        f"SET s.{HISTORY_RECORD_PROPERTY} = true "
        "RETURN d.id AS id"
    )


def clear_decision_review_query() -> str:
    """Clear a reaffirmed decision's review state."""
    return (
        f"MATCH (:{TASK_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        f"project_id: $project_id}})-[:{MADE}]->"
        f"(d:{DECISION_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "id: $decision_id}) "
        "SET d.review_state = 'clear', d.review_reason = null, "
        "d.review_reaffirmed = null "
        "RETURN d.id AS id"
    )


def queue_superseded_decision_query() -> str:
    """Queue dependents of a decision superseded in the same transaction."""
    return (
        f"MATCH (old:{DECISION_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "id: $id, project_id: $project_id}) "
        "SET old.status = 'superseded', old.review_state = 'clear', "
        "old.review_reason = null, old.review_pending = true "
        f"WITH old MATCH (p:{PROJECT_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id}) "
        "SET p.review_incomplete = true, "
        "p.review_epoch = coalesce(p.review_epoch, 0) + 1 "
        f"WITH old MATCH (new:{DECISION_LABEL} {{{HISTORY_RECORD_PROPERTY}: true, "
        "id: $new_id}) "
        f"CREATE (new)-[:{SUPERSEDES}]->(old) "
        "RETURN old.id AS id"
    )
