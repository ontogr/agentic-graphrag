"""Parameterized Cypher builders for memory retention."""

from agrag.common.data_models.decision import (
    DECISION_LABEL,
    HAS_SUPPORT,
    MADE,
    SUPPORT_LABEL,
)
from agrag.common.data_models.task import (
    EVENT_LABEL,
    HAS_EVENT,
    HAS_STEP,
    STEP_LABEL,
    TASK_LABEL,
)
from agrag.cypher.entities import validate_identifier


_TASK = validate_identifier(TASK_LABEL)
_EVENT = validate_identifier(EVENT_LABEL)
_STEP = validate_identifier(STEP_LABEL)
_DECISION = validate_identifier(DECISION_LABEL)
_SUPPORT = validate_identifier(SUPPORT_LABEL)
_HAS_EVENT = validate_identifier(HAS_EVENT)
_HAS_STEP = validate_identifier(HAS_STEP)
_HAS_SUPPORT = validate_identifier(HAS_SUPPORT)
_MADE = validate_identifier(MADE)


def event_in_project_query() -> str:
    """Find an event only through a task in the configured project."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id}})-[:{_HAS_EVENT}]->"
        f"(e:{_EVENT} {{id: $event_id}}) "
        "RETURN e.id AS id, e.payload AS payload, e.redacted_at AS redacted_at"
    )


def redact_event_query() -> str:
    """Replace an event payload while retaining its identity and hash."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id}})-[:{_HAS_EVENT}]->"
        f"(e:{_EVENT} {{id: $event_id}}) "
        "SET e.payload = $marker, "
        "e.redacted_at = coalesce(e.redacted_at, $redacted_at) "
        "RETURN e.id AS id"
    )


def event_supports_query() -> str:
    """List project decisions that cite an event support."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id}})-[:{_MADE}]->"
        f"(d:{_DECISION})-[:{_HAS_SUPPORT}]->(s:{_SUPPORT}) "
        "WHERE s.kind = 'event' AND s.event_id = $event_id "
        "RETURN DISTINCT d.id AS id"
    )


def task_in_project_query() -> str:
    """Find a task id by name inside the configured project."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id, name: $name}}) RETURN t.id AS id"
    )


def task_dependent_decisions_query() -> str:
    """List project decision roots that cite task events or its decisions."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id, name: $name}}) "
        f"OPTIONAL MATCH (t)-[:{_HAS_EVENT}]->(e:{_EVENT}) "
        "WITH t, collect(DISTINCT e.id) AS event_ids "
        f"OPTIONAL MATCH (t)-[:{_MADE}]->(owned:{_DECISION}) "
        "WITH t, event_ids, collect(DISTINCT owned.id) AS decision_ids "
        f"MATCH (source:{_TASK} {{project_id: $project_id}})-[:{_MADE}]->"
        f"(d:{_DECISION})-[:{_HAS_SUPPORT}]->(s:{_SUPPORT}) "
        "WHERE (s.kind = 'event' AND s.event_id IN event_ids) "
        "OR (s.kind = 'decision' AND s.target_decision_id IN decision_ids) "
        "RETURN DISTINCT d.id AS id"
    )


def flag_decisions_query() -> str:
    """Flag only explicitly matched same-project decisions for review."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id}})-[:{_MADE}]->"
        f"(d:{_DECISION} {{id: $decision_id}}) "
        "SET d.review_state = 'needs_review', d.review_reason = 'source_removed' "
        "RETURN d.id AS id"
    )


def delete_task_children_query() -> str:
    """Delete a task's events and steps, retaining the task node."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id, name: $name}}) "
        f"OPTIONAL MATCH (t)-[:{_HAS_EVENT}|{_HAS_STEP}]->(child) "
        "WITH collect(child) AS children "
        "FOREACH (child IN children | DETACH DELETE child) "
        "RETURN size(children) AS deleted"
    )


def delete_task_decisions_query() -> str:
    """Delete all decisions and supports owned by one project task."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id, name: $name}})"
        f"-[:{_MADE}]->(d:{_DECISION}) "
        f"OPTIONAL MATCH (d)-[:{_HAS_SUPPORT}]->(s:{_SUPPORT}) "
        "WITH collect(s) + collect(d) AS items "
        "FOREACH (item IN items | DETACH DELETE item) "
        "RETURN size(items) AS deleted"
    )


def detach_task_decisions_query() -> str:
    """Preserve decisions when deleting their task container."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id, name: $name}})"
        f"-[r:{_MADE}]->(d:{_DECISION}) "
        "SET d.project_id = $project_id DELETE r RETURN count(r) AS detached"
    )


def delete_task_node_query() -> str:
    """Delete one task after its retained children have been handled."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id, name: $name}}) "
        "DETACH DELETE t RETURN count(t) AS deleted"
    )
