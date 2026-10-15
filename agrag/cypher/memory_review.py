"""Cypher builders for durable, bounded decision review propagation."""

from agrag.common.data_models.decision import (
    DECISION_LABEL,
    DEPENDS_ON,
    HAS_SUPPORT,
    MADE,
    SUPPORT_LABEL,
)
from agrag.common.data_models.structure import HAS_PART
from agrag.common.data_models.task import PROJECT_LABEL, TASK_LABEL


def flag_new_decision_for_review_query() -> str:
    """Flag a new decision that depends on a decision already needing review."""
    return (
        f"MATCH (t:{TASK_LABEL} {{project_id: $project_id}})-[:{MADE}]->"
        f"(d:{DECISION_LABEL} {{id: $decision_id}}) "
        f"MATCH (p:{PROJECT_LABEL} {{project_id: $project_id}}) "
        f"MATCH (d)-[:{DEPENDS_ON}]->(parent:{DECISION_LABEL}) "
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
        f"MATCH (p:{PROJECT_LABEL} {{project_id: $project_id}}) "
        "SET p.review_lock = coalesce(p.review_lock, 0) + 1 "
        "WITH p "
        f"OPTIONAL MATCH (t:{TASK_LABEL} {{project_id: $project_id}})"
        f"-[:{MADE}]->(d:{DECISION_LABEL} {{review_pending: true}}) "
        "WITH p, d ORDER BY d.created_at, d.id LIMIT 1 "
        "FOREACH (_ IN CASE WHEN d IS NULL THEN [] ELSE [1] END | "
        "SET d.review_pending = false) "
        "RETURN d.id AS id"
    )


def expand_review_unit_query() -> str:
    """Flag and enqueue every active one-hop dependent of a claimed decision.

    A dependent already flagged keeps its state and reason, but is queued
    again so its own dependents are reached even if they were reaffirmed
    since the dependent was last expanded.
    """
    return (
        f"MATCH (t:{TASK_LABEL} {{project_id: $project_id}})-[:{MADE}]->"
        f"(parent:{DECISION_LABEL} {{id: $decision_id}}) "
        f"MATCH (child:{DECISION_LABEL} {{status: 'active'}})"
        f"-[:{DEPENDS_ON}]->(parent) "
        "WITH child, coalesce(child.review_state, 'clear') = 'needs_review' AS flagged "
        "SET child.review_reason = CASE WHEN flagged THEN child.review_reason "
        "ELSE 'dependency_review' END, "
        "child.review_state = 'needs_review', "
        "child.review_pending = true "
        "RETURN count(DISTINCT child) AS queued"
    )


def finish_review_propagation_query() -> str:
    """Clear the project incomplete marker only when its queue is empty."""
    return (
        f"MATCH (p:{PROJECT_LABEL} {{project_id: $project_id}}) "
        f"OPTIONAL MATCH (t:{TASK_LABEL} {{project_id: $project_id}})"
        f"-[:{MADE}]->(d:{DECISION_LABEL} {{review_pending: true}}) "
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
        "count(part) > 0 AS live"
    )


def replace_document_supports_query() -> str:
    """Replace a decision's document supports and keep its other supports.

    Expects ``$project_id``, ``$decision_id`` and ``$supports``, a list of
    support property maps that already carry their ids and ordinals.
    """
    return (
        f"MATCH (t:{TASK_LABEL} {{project_id: $project_id}})-[:{MADE}]->"
        f"(d:{DECISION_LABEL} {{id: $decision_id}}) "
        f"OPTIONAL MATCH (d)-[:{HAS_SUPPORT}]->"
        f"(old:{SUPPORT_LABEL} {{kind: 'document'}}) "
        "DETACH DELETE old "
        "WITH DISTINCT d UNWIND $supports AS item "
        f"CREATE (d)-[:{HAS_SUPPORT}]->(s:{SUPPORT_LABEL}) SET s = item "
        "RETURN d.id AS id"
    )


def clear_decision_review_query() -> str:
    """Clear a reaffirmed decision's review state and mark it as reaffirmed.

    The project queue marker is left alone. ``review_reaffirmed`` keeps the
    decision clear in review reads while that marker is set.
    """
    return (
        f"MATCH (:{TASK_LABEL} {{project_id: $project_id}})-[:{MADE}]->"
        f"(d:{DECISION_LABEL} {{id: $decision_id}}) "
        "SET d.review_state = 'clear', d.review_reason = null, "
        "d.review_reaffirmed = true "
        "RETURN d.id AS id"
    )
