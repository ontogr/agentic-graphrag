"""Cypher builders for durable, bounded decision review propagation."""

from agrag.common.data_models.decision import DECISION_LABEL, DEPENDS_ON, MADE
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
    """Flag and enqueue the active one-hop dependents of a claimed decision."""
    return (
        f"MATCH (t:{TASK_LABEL} {{project_id: $project_id}})-[:{MADE}]->"
        f"(parent:{DECISION_LABEL} {{id: $decision_id}}) "
        f"MATCH (child:{DECISION_LABEL} {{status: 'active'}})"
        f"-[:{DEPENDS_ON}]->(parent) "
        "WHERE coalesce(child.review_state, 'clear') <> 'needs_review' "
        "SET child.review_state = 'needs_review', "
        "child.review_reason = 'dependency_review', "
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
