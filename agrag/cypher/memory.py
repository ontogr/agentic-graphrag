"""Cypher builders for task memory constraints, reads and writes.

Task memory nodes carry their own labels and no identity label, so the entity
readers in ``relations.py`` never return them. Every query filters by
``project_id``, either directly or through a task id that the caller resolved
under that project.
"""

from agrag.common.data_models.decision import (
    DECISION_LABEL,
    DEPENDS_ON,
    HAS_SUPPORT,
    MADE,
    SUPERSEDES,
    SUPPORT_LABEL,
)
from agrag.common.data_models.task import (
    EVENT_LABEL,
    HAS_EVENT,
    HAS_STEP,
    PROJECT_LABEL,
    REQUEST_LABEL,
    STEP_LABEL,
    STEP_STATE_ORDER,
    TASK_LABEL,
)
from agrag.cypher.entities import validate_identifier
from agrag.cypher.schema import node_id_constraint_query


_PROJECT = validate_identifier(PROJECT_LABEL)
_TASK = validate_identifier(TASK_LABEL)
_EVENT = validate_identifier(EVENT_LABEL)
_STEP = validate_identifier(STEP_LABEL)
_REQUEST = validate_identifier(REQUEST_LABEL)
_HAS_EVENT = validate_identifier(HAS_EVENT)
_HAS_STEP = validate_identifier(HAS_STEP)
_DECISION = validate_identifier(DECISION_LABEL)
_SUPPORT = validate_identifier(SUPPORT_LABEL)
_MADE = validate_identifier(MADE)
_HAS_SUPPORT = validate_identifier(HAS_SUPPORT)
_DEPENDS_ON = validate_identifier(DEPENDS_ON)
_SUPERSEDES = validate_identifier(SUPERSEDES)


def memory_schema_queries() -> list[str]:
    """Build the constraints that task memory writes depend on.

    Each query uses ``IF NOT EXISTS``, so running the list again is harmless.
    The ``id`` constraints use the same names as the generic per-label
    constraints, so they never collide with those.

    Returns:
        The Cypher statements, each creating one uniqueness constraint.
    """
    return [
        f"CREATE CONSTRAINT project_id_unique IF NOT EXISTS "
        f"FOR (p:{_PROJECT}) REQUIRE p.project_id IS UNIQUE",
        node_id_constraint_query(_TASK),
        f"CREATE CONSTRAINT task_project_name_unique IF NOT EXISTS "
        f"FOR (t:{_TASK}) REQUIRE (t.project_id, t.name) IS UNIQUE",
        node_id_constraint_query(_EVENT),
        f"CREATE CONSTRAINT event_task_seq_unique IF NOT EXISTS "
        f"FOR (e:{_EVENT}) REQUIRE (e.task_id, e.seq) IS UNIQUE",
        node_id_constraint_query(_STEP),
        f"CREATE CONSTRAINT step_task_name_unique IF NOT EXISTS "
        f"FOR (s:{_STEP}) REQUIRE (s.task_id, s.name) IS UNIQUE",
        node_id_constraint_query(_REQUEST),
        f"CREATE CONSTRAINT request_project_request_unique IF NOT EXISTS "
        f"FOR (r:{_REQUEST}) REQUIRE (r.project_id, r.request_id) IS UNIQUE",
        node_id_constraint_query(_DECISION),
        f"CREATE CONSTRAINT decision_task_choice_revision_unique IF NOT EXISTS "
        f"FOR (d:{_DECISION}) REQUIRE "
        "(d.task_id, d.choice_key, d.revision) IS UNIQUE",
        node_id_constraint_query(_SUPPORT),
    ]


def create_decision_query() -> str:
    """Build a transaction-scoped decision and support write."""
    return (
        f"MATCH (t:{_TASK} {{id: $task_id, project_id: $project_id}}) "
        f"CREATE (t)-[:{_MADE}]->(d:{_DECISION} $decision) "
        "WITH d UNWIND $supports AS item "
        f"CREATE (d)-[:{_HAS_SUPPORT}]->(s:{_SUPPORT}) SET s = item "
        "WITH d, s, item "
        f"OPTIONAL MATCH (target:{_DECISION} {{id: item.target_decision_id}}) "
        "FOREACH (_ IN CASE WHEN item.target_decision_id IS NULL "
        "THEN [] ELSE [1] END | "
        f"CREATE (d)-[:{_DEPENDS_ON}]->(target)) "
        "RETURN d.id AS id"
    )


def decision_by_id_query() -> str:
    """Build a project-scoped decision read with its supports."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id}})-[:{_MADE}]->"
        f"(d:{_DECISION} {{id: $id}}) "
        f"OPTIONAL MATCH (p:{_PROJECT} {{project_id: $project_id}}) "
        f"OPTIONAL MATCH (d)-[:{_HAS_SUPPORT}]->(s:{_SUPPORT}) "
        "WITH d, t, p, s ORDER BY s.ordinal "
        "WITH d, t, p, collect(s) AS supports "
        "RETURN d AS decision, supports, t.name AS task_name, "
        "coalesce(p.review_incomplete, false) AS review_incomplete "
        "LIMIT 1"
    )


def decision_status_query() -> str:
    """Build a project-scoped lifecycle update without changing decision text."""
    return (
        f"MATCH (:{_TASK} {{project_id: $project_id}})-[:{_MADE}]->"
        f"(d:{_DECISION} {{id: $id}}) "
        "SET d.status = $status, d.rejection_reason = $reason, "
        "d.rejected_by = $by, d.review_state = 'clear', d.review_reason = null "
        "RETURN d.id AS id"
    )


def decision_page_query() -> str:
    """Build a project-scoped decision list for one task."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id, name: $task_name}})"
        f"-[:{_MADE}]->(d:{_DECISION}) "
        "WHERE $include_history OR d.status = 'active' "
        f"WITH t, d, $project_id AS project_id "
        f"OPTIONAL MATCH (p:{_PROJECT} {{project_id: project_id}}) "
        f"OPTIONAL MATCH (d)-[:{_HAS_SUPPORT}]->(s:{_SUPPORT}) "
        "WITH t, d, p, s ORDER BY s.ordinal "
        "WITH t, d, p, collect(s) AS supports "
        "RETURN d AS decision, supports, t.name AS task_name, "
        "coalesce(p.review_incomplete, false) AS review_incomplete "
        "ORDER BY d.created_at DESC LIMIT $limit"
    )


def task_review_decisions_query() -> str:
    """Build a bounded read of active decisions that need review for a task."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id, id: $task_id}})"
        f"-[:{_MADE}]->(d:{_DECISION} {{status: 'active'}}) "
        f"MATCH (p:{_PROJECT} {{project_id: $project_id}}) "
        "WHERE (d.review_state = 'needs_review' OR p.review_incomplete) "
        f"OPTIONAL MATCH (d)-[:{_HAS_SUPPORT}]->(s:{_SUPPORT}) "
        "WITH t, d, p, s ORDER BY s.ordinal "
        "WITH t, d, p, collect(s) AS supports "
        "RETURN d AS decision, supports, t.name AS task_name, "
        "p.review_incomplete AS review_incomplete "
        "ORDER BY d.created_at DESC LIMIT $limit"
    )


def task_conflict_keys_query() -> str:
    """Build a bounded read of choice keys conflicting with one task."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id, id: $task_id}})"
        f"-[:{_MADE}]->(d:{_DECISION} {{status: 'active'}}) "
        f"MATCH (other:{_TASK} {{project_id: $project_id}})-[:{_MADE}]->"
        f"(candidate:{_DECISION} {{status: 'active', choice_key: d.choice_key}}) "
        "WHERE other.id <> t.id AND candidate.conclusion <> d.conclusion "
        "RETURN DISTINCT d.choice_key AS choice_key "
        "ORDER BY choice_key LIMIT $limit"
    )


def task_conflict_decisions_query() -> str:
    """Build a read of active decisions for the requested conflicting choices."""
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id}})-[:{_MADE}]->"
        f"(d:{_DECISION} {{status: 'active'}}) "
        "WHERE d.choice_key IN $choice_keys "
        f"WITH t, d, $project_id AS project_id "
        f"OPTIONAL MATCH (p:{_PROJECT} {{project_id: project_id}}) "
        f"OPTIONAL MATCH (d)-[:{_HAS_SUPPORT}]->(s:{_SUPPORT}) "
        "WITH t, d, p, s ORDER BY s.ordinal "
        "WITH t, d, p, collect(s) AS supports "
        "RETURN d AS decision, supports, t.name AS task_name, "
        "coalesce(p.review_incomplete, false) AS review_incomplete "
        "ORDER BY d.choice_key, t.name, d.created_at DESC LIMIT $limit"
    )


def find_task_query() -> str:
    """Build Cypher reading one task by its project and name.

    Returns:
        Parameterized Cypher expecting ``$project_id`` and ``$name``. Returns no
        row when the project has no task of that name.
    """
    return (
        f"MATCH (t:{_TASK} {{project_id: $project_id, name: $name}}) "
        "RETURN t.id AS id, t.project_id AS project_id, t.name AS name, "
        "t.goal AS goal, t.status AS status, t.event_seq AS event_seq, "
        "t.author AS author, t.created_at AS created_at"
    )


def create_task_query() -> str:
    """Build Cypher creating a task and its project node.

    Returns:
        Parameterized Cypher expecting ``$project_id``, ``$id``, ``$name``,
        ``$goal``, ``$status``, ``$author`` and ``$created_at``. A duplicate
        ``(project_id, name)`` fails the uniqueness constraint.
    """
    return (
        f"MERGE (p:{_PROJECT} {{project_id: $project_id}}) "
        "ON CREATE SET p.review_incomplete = false, p.review_epoch = 0 "
        f"CREATE (t:{_TASK} {{id: $id, project_id: $project_id, name: $name, "
        "goal: $goal, status: $status, event_seq: 0, author: $author, "
        "created_at: $created_at}) "
        "RETURN t.id AS id"
    )


def append_event_query() -> str:
    """Build Cypher that takes the next sequence number and creates an event.

    The counter is incremented in the same statement that reads it, so two
    writers cannot read the same value. The event id is set by
    ``set_event_id_query`` once the number is known.

    Returns:
        Parameterized Cypher expecting ``$project_id``, ``$task_id``, ``$kind``,
        ``$role``, ``$name``, ``$payload``, ``$payload_sha256``,
        ``$truncated``, ``$author`` and ``$at``. Returns ``seq``, the number
        given to the new event, or no row when the task does not match.
    """
    return (
        f"MATCH (t:{_TASK} {{id: $task_id, project_id: $project_id}}) "
        "SET t.event_seq = coalesce(t.event_seq, 0) + 1 "
        "WITH t, t.event_seq AS seq "
        f"CREATE (t)-[:{_HAS_EVENT}]->(e:{_EVENT} {{task_id: t.id, seq: seq, "
        "kind: $kind, role: $role, name: $name, payload: $payload, "
        "payload_sha256: $payload_sha256, truncated: $truncated, "
        "author: $author, at: $at}) "
        "RETURN e.seq AS seq"
    )


def set_event_id_query() -> str:
    """Build Cypher setting the id of the event with a given sequence number.

    Returns:
        Parameterized Cypher expecting ``$task_id``, ``$seq`` and ``$id``.
    """
    return (
        f"MATCH (e:{_EVENT} {{task_id: $task_id, seq: $seq}}) "
        "SET e.id = $id RETURN e.id AS id"
    )


def event_by_seq_query() -> str:
    """Build Cypher finding one event of a task by its sequence number.

    Returns:
        Parameterized Cypher expecting ``$project_id``, ``$task_id`` and
        ``$seq``. Returns no row when the event does not exist in that project.
    """
    return (
        f"MATCH (t:{_TASK} {{id: $task_id, project_id: $project_id}})"
        f"-[:{_HAS_EVENT}]->(e:{_EVENT} {{seq: $seq}}) "
        "RETURN e.id AS id"
    )


def events_page_query() -> str:
    """Build Cypher reading one page of a task's events in sequence order.

    Returns:
        Parameterized Cypher expecting ``$project_id``, ``$task_id``,
        ``$after_seq`` and ``$limit``. Returns the event fields in sequence
        order, starting after ``$after_seq``.
    """
    return (
        f"MATCH (t:{_TASK} {{id: $task_id, project_id: $project_id}})"
        f"-[:{_HAS_EVENT}]->(e:{_EVENT}) "
        "WHERE e.seq > $after_seq "
        "RETURN e.id AS id, e.task_id AS task_id, e.seq AS seq, e.kind AS kind, "
        "e.role AS role, e.name AS name, e.payload AS payload, "
        "e.payload_sha256 AS payload_sha256, e.truncated AS truncated, "
        "e.author AS author, e.at AS at "
        "ORDER BY e.seq LIMIT $limit"
    )


def upsert_step_query() -> str:
    """Build Cypher creating or updating one step of a task.

    The step id is derived from the task id and step name, so the same step
    always maps to the same node.

    Returns:
        Parameterized Cypher expecting ``$project_id``, ``$task_id``,
        ``$step_id``, ``$name``, ``$kind``, ``$state``, ``$result_event_seq``
        and ``$updated_seq``. Returns the stored step fields.
    """
    return (
        f"MATCH (t:{_TASK} {{id: $task_id, project_id: $project_id}}) "
        f"MERGE (s:{_STEP} {{id: $step_id}}) "
        "ON CREATE SET s.task_id = $task_id, s.name = $name "
        f"MERGE (t)-[:{_HAS_STEP}]->(s) "
        "SET s.kind = $kind, s.state = $state, "
        "s.result_event_seq = $result_event_seq, s.updated_seq = $updated_seq "
        "RETURN s.id AS id, s.task_id AS task_id, s.name AS name, s.kind AS kind, "
        "s.state AS state, s.result_event_seq AS result_event_seq, "
        "s.updated_seq AS updated_seq"
    )


def step_state_counts_query() -> str:
    """Build Cypher counting a task's steps in each state.

    Returns:
        Parameterized Cypher expecting ``$project_id`` and ``$task_id``. Returns
        one row per state that has steps, with ``state`` and ``count``.
    """
    return (
        f"MATCH (t:{_TASK} {{id: $task_id, project_id: $project_id}})"
        f"-[:{_HAS_STEP}]->(s:{_STEP}) "
        "RETURN s.state AS state, count(s) AS count"
    )


def step_page_query() -> str:
    """Build Cypher reading the first steps of a task in view order.

    The order follows ``STEP_STATE_ORDER``, then the step name. Steps that
    still need work come before completed steps.

    Returns:
        Parameterized Cypher expecting ``$project_id``, ``$task_id`` and
        ``$limit``. Returns the summary fields of each step.
    """
    ranks = " ".join(
        f"WHEN '{state.value}' THEN {rank}"
        for rank, state in enumerate(STEP_STATE_ORDER)
    )
    return (
        f"MATCH (t:{_TASK} {{id: $task_id, project_id: $project_id}})"
        f"-[:{_HAS_STEP}]->(s:{_STEP}) "
        "RETURN s.name AS name, s.kind AS kind, s.state AS state, "
        "s.result_event_seq AS result_event_seq "
        f"ORDER BY CASE s.state {ranks} ELSE {len(STEP_STATE_ORDER)} END, s.name "
        "LIMIT $limit"
    )


def claim_request_query() -> str:
    """Build Cypher that claims a request id, or reads the claim it already has.

    The Request node is created by the same transaction as the write it
    guards, so a failed write leaves no claim behind. A concurrent duplicate
    blocks on the uniqueness constraint until the first transaction ends.

    Returns:
        Parameterized Cypher expecting ``$project_id``, ``$request_id``, ``$id``,
        ``$operation`` and ``$payload_sha256``. Returns the stored digest and
        ``result_json``, which is null when this call created the claim.
    """
    return (
        f"MERGE (r:{_REQUEST} {{project_id: $project_id, request_id: $request_id}}) "
        "ON CREATE SET r.id = $id, r.operation = $operation, "
        "r.payload_sha256 = $payload_sha256 "
        "RETURN r.payload_sha256 AS payload_sha256, r.result_json AS result_json"
    )


def store_request_result_query() -> str:
    """Build Cypher storing the serialized result on a request claim.

    Returns:
        Parameterized Cypher expecting ``$project_id``, ``$request_id`` and
        ``$result_json``.
    """
    return (
        f"MATCH (r:{_REQUEST} {{project_id: $project_id, request_id: $request_id}}) "
        "SET r.result_json = $result_json RETURN count(r) AS stored"
    )
