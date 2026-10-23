"""Cypher builders for conversation history constraints, reads and writes.

History records carry a private marker as well as their domain labels. This
keeps their constraints and reads separate from knowledge entities that use
the same labels. Every query is scoped to a project, directly or through a
task id resolved under that project.
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
    HISTORY_RECORD_PROPERTY,
    PROJECT_LABEL,
    REQUEST_LABEL,
    STEP_LABEL,
    STEP_STATE_ORDER,
    TASK_LABEL,
)
from agrag.cypher.entities import validate_identifier


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


def history_unique_constraints() -> list[tuple[str, tuple[str, ...]]]:
    """List the uniqueness constraints that history writes depend on.

    Returns:
        One ``(label, properties)`` pair per constraint. A pair with several
        properties makes the combination unique. Pass each pair to
        ``GraphStore.ensure_unique_constraint``; running the list again is
        harmless.
    """
    marker = (HISTORY_RECORD_PROPERTY,)
    return [
        (_PROJECT, (*marker, "project_id")),
        (_TASK, (*marker, "id")),
        (_TASK, (*marker, "project_id", "name")),
        (_EVENT, (*marker, "id")),
        (_EVENT, (*marker, "task_id", "seq")),
        (_STEP, (*marker, "id")),
        (_STEP, (*marker, "task_id", "name")),
        (_REQUEST, (*marker, "id")),
        (_REQUEST, (*marker, "project_id", "request_id")),
        (_DECISION, (*marker, "id")),
        (_DECISION, (*marker, "task_id", "choice_key", "revision")),
        (_SUPPORT, (*marker, "id")),
    ]


def create_decision_query(*, text_copy_set: str = "") -> str:
    """Build a transaction-scoped decision and support write.

    Args:
        text_copy_set: Extra ``SET`` clauses for the new decision node, from
            ``GraphStore.fulltext_copy_set``. Empty by default.
    """
    return (
        f"MATCH (t:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        "id: $task_id, project_id: $project_id}) "
        f"CREATE (t)-[:{_MADE}]->(d:{_DECISION}) SET d = $decision "
        f"SET d.{HISTORY_RECORD_PROPERTY} = true "
        f"{text_copy_set + ' ' if text_copy_set else ''}"
        "WITH d UNWIND $supports AS item "
        f"CREATE (d)-[:{_HAS_SUPPORT}]->(s:{_SUPPORT}) SET s = item "
        f"SET s.{HISTORY_RECORD_PROPERTY} = true "
        "WITH d, s, item "
        f"OPTIONAL MATCH (target:{_DECISION} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, id: item.target_decision_id}}) "
        "FOREACH (_ IN CASE WHEN item.target_decision_id IS NULL "
        "THEN [] ELSE [1] END | "
        f"CREATE (d)-[:{_DEPENDS_ON}]->(target)) "
        "RETURN d.id AS id"
    )


def decision_by_id_query() -> str:
    """Build a project-scoped decision read with its supports."""
    return (
        f"MATCH (t:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        f"project_id: $project_id}})-[:{_MADE}]->"
        f"(d:{_DECISION} {{{HISTORY_RECORD_PROPERTY}: true, id: $id}}) "
        f"OPTIONAL MATCH (p:{_PROJECT} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, project_id: $project_id}}) "
        f"OPTIONAL MATCH (d)-[:{_HAS_SUPPORT}]->"
        f"(s:{_SUPPORT} {{{HISTORY_RECORD_PROPERTY}: true, current: true}}) "
        "WITH d, t, p, s ORDER BY s.current DESC, s.ordinal "
        "WITH d, t, p, collect(s) AS supports "
        "RETURN d AS decision, supports, t.name AS task_name, "
        "coalesce(p.review_incomplete, false) AS review_incomplete "
        "LIMIT 1"
    )


def decision_status_query() -> str:
    """Build a project-scoped lifecycle update without changing decision text."""
    return (
        f"MATCH (:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        f"project_id: $project_id}})-[:{_MADE}]->"
        f"(d:{_DECISION} {{{HISTORY_RECORD_PROPERTY}: true, id: $id}}) "
        "SET d.status = $status, d.rejection_reason = $reason, "
        "d.rejected_by = $by, d.review_state = 'clear', d.review_reason = null "
        f"WITH d MATCH (p:{_PROJECT} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, project_id: $project_id}}) "
        "SET d.review_pending = true, p.review_incomplete = true, "
        "p.review_epoch = coalesce(p.review_epoch, 0) + 1 "
        "RETURN d.id AS id"
    )


def decision_page_query() -> str:
    """Build a project-scoped decision list for one task."""
    return (
        f"MATCH (t:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id, name: $task_name})"
        f"-[:{_MADE}]->(d:{_DECISION} {{{HISTORY_RECORD_PROPERTY}: true}}) "
        "WHERE $include_history OR d.status = 'active' "
        f"WITH t, d, $project_id AS project_id "
        f"OPTIONAL MATCH (p:{_PROJECT} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, project_id: project_id}}) "
        f"OPTIONAL MATCH (d)-[:{_HAS_SUPPORT}]->"
        f"(s:{_SUPPORT} {{{HISTORY_RECORD_PROPERTY}: true, current: true}}) "
        "WITH t, d, p, s ORDER BY s.current DESC, s.ordinal "
        "WITH t, d, p, collect(s) AS supports "
        "RETURN d AS decision, supports, t.name AS task_name, "
        "coalesce(p.review_incomplete, false) AS review_incomplete "
        "ORDER BY d.created_at DESC LIMIT $limit"
    )


def task_review_decisions_query() -> str:
    """Build a bounded read of active decisions that need review for a task."""
    return (
        f"MATCH (t:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id, id: $task_id})"
        f"-[:{_MADE}]->(d:{_DECISION} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, status: 'active'}}) "
        f"MATCH (p:{_PROJECT} {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id}) "
        "WHERE (d.review_state = 'needs_review' OR "
        "p.review_incomplete) "
        f"OPTIONAL MATCH (d)-[:{_HAS_SUPPORT}]->"
        f"(s:{_SUPPORT} {{{HISTORY_RECORD_PROPERTY}: true, current: true}}) "
        "WITH t, d, p, s ORDER BY s.current DESC, s.ordinal "
        "WITH t, d, p, collect(s) AS supports "
        "RETURN d AS decision, supports, t.name AS task_name, "
        "p.review_incomplete AS review_incomplete "
        "ORDER BY d.created_at DESC LIMIT $limit"
    )


def task_conflict_keys_query() -> str:
    """Build a bounded read of choice keys conflicting with one task."""
    return (
        f"MATCH (t:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id, id: $task_id})"
        f"-[:{_MADE}]->(d:{_DECISION} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, status: 'active'}}) "
        f"MATCH (other:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        f"project_id: $project_id}})-[:{_MADE}]->"
        f"(candidate:{_DECISION} {{{HISTORY_RECORD_PROPERTY}: true, "
        "status: 'active', choice_key: d.choice_key}) "
        "WHERE other.id <> t.id AND candidate.conclusion <> d.conclusion "
        "RETURN DISTINCT d.choice_key AS choice_key "
        "ORDER BY choice_key LIMIT $limit"
    )


def task_conflict_decisions_query() -> str:
    """Build a read of active decisions for the requested conflicting choices."""
    return (
        f"MATCH (t:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        f"project_id: $project_id}})-[:{_MADE}]->"
        f"(d:{_DECISION} {{{HISTORY_RECORD_PROPERTY}: true, "
        "status: 'active'}) "
        "WHERE d.choice_key IN $choice_keys "
        f"WITH t, d, $project_id AS project_id "
        f"OPTIONAL MATCH (p:{_PROJECT} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, project_id: project_id}}) "
        f"OPTIONAL MATCH (d)-[:{_HAS_SUPPORT}]->"
        f"(s:{_SUPPORT} {{{HISTORY_RECORD_PROPERTY}: true, current: true}}) "
        "WITH t, d, p, s ORDER BY s.current DESC, s.ordinal "
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
        f"MATCH (t:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id, name: $name}) "
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
        f"MERGE (p:{_PROJECT} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, project_id: $project_id}}) "
        "ON CREATE SET p.review_incomplete = false, p.review_epoch = 0 "
        f"CREATE (t:{_TASK} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, id: $id, "
        "project_id: $project_id, name: $name, "
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
        f"MATCH (t:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        "id: $task_id, project_id: $project_id}) "
        "SET t.event_seq = coalesce(t.event_seq, 0) + 1 "
        "WITH t, t.event_seq AS seq "
        f"CREATE (t)-[:{_HAS_EVENT}]->(e:{_EVENT} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, task_id: t.id, seq: seq, "
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
        f"MATCH (e:{_EVENT} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, task_id: $task_id, seq: $seq}}) "
        "SET e.id = $id RETURN e.id AS id"
    )


def event_by_seq_query() -> str:
    """Build Cypher finding one event of a task by its sequence number.

    Returns:
        Parameterized Cypher expecting ``$project_id``, ``$task_id`` and
        ``$seq``. Returns no row when the event does not exist in that project.
    """
    return (
        f"MATCH (t:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        "id: $task_id, project_id: $project_id})"
        f"-[:{_HAS_EVENT}]->(e:{_EVENT} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, seq: $seq}}) "
        "RETURN e.id AS id, e.task_id AS task_id, e.seq AS seq, e.kind AS kind, "
        "e.role AS role, e.name AS name, e.payload AS payload, "
        "e.payload_sha256 AS payload_sha256, e.truncated AS truncated, "
        "e.author AS author, e.at AS at, e.redacted_at AS redacted_at"
    )


def events_page_query() -> str:
    """Build Cypher reading one page of a task's events in sequence order.

    Returns:
        Parameterized Cypher expecting ``$project_id``, ``$task_id``,
        ``$after_seq`` and ``$limit``. Returns the event fields in sequence
        order, starting after ``$after_seq``.
    """
    return (
        f"MATCH (t:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        "id: $task_id, project_id: $project_id})"
        f"-[:{_HAS_EVENT}]->(e:{_EVENT} {{{HISTORY_RECORD_PROPERTY}: true}}) "
        "WHERE e.seq > $after_seq "
        "RETURN e.id AS id, e.task_id AS task_id, e.seq AS seq, e.kind AS kind, "
        "e.role AS role, e.name AS name, e.payload AS payload, "
        "e.payload_sha256 AS payload_sha256, e.truncated AS truncated, "
        "e.author AS author, e.at AS at, e.redacted_at AS redacted_at "
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
        f"MATCH (t:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        "id: $task_id, project_id: $project_id}) "
        f"MERGE (s:{_STEP} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, id: $step_id}}) "
        "ON CREATE SET s.task_id = $task_id, s.name = $name "
        f"MERGE (t)-[:{_HAS_STEP}]->(s) "
        "SET s.kind = $kind, s.state = $state, "
        "s.result_event_seq = $result_event_seq, s.updated_seq = $updated_seq, "
        "s.result_basis = $result_basis, s.result_supports = $result_supports "
        "RETURN s.id AS id, s.task_id AS task_id, s.name AS name, s.kind AS kind, "
        "s.state AS state, s.result_event_seq AS result_event_seq, "
        "s.updated_seq AS updated_seq, s.result_basis AS result_basis, "
        "s.result_supports AS result_supports"
    )


def step_state_counts_query() -> str:
    """Build Cypher counting a task's steps in each state.

    Returns:
        Parameterized Cypher expecting ``$project_id`` and ``$task_id``. Returns
        one row per state that has steps, with ``state`` and ``count``.
    """
    return (
        f"MATCH (t:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        "id: $task_id, project_id: $project_id})"
        f"-[:{_HAS_STEP}]->(s:{_STEP} {{{HISTORY_RECORD_PROPERTY}: true}}) "
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
        f"MATCH (t:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        "id: $task_id, project_id: $project_id})"
        f"-[:{_HAS_STEP}]->(s:{_STEP} {{{HISTORY_RECORD_PROPERTY}: true}}) "
        f"OPTIONAL MATCH (t)-[:{_HAS_EVENT}]->(e:{_EVENT} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, seq: s.result_event_seq}}) "
        "RETURN s.name AS name, s.kind AS kind, s.state AS state, "
        "s.result_event_seq AS result_event_seq, "
        "coalesce(s.result_basis, 'unknown') AS result_basis, "
        "coalesce(s.result_supports, '[]') AS result_supports, "
        "CASE WHEN s.state <> 'completed' THEN 'unknown' "
        "WHEN e.id IS NULL OR e.redacted_at IS NOT NULL OR e.truncated "
        "THEN 'unavailable' "
        "WHEN s.result_basis = 'independent' THEN 'reusable' "
        "WHEN coalesce(s.result_basis, 'unknown') <> 'supported' THEN 'unknown' "
        "WHEN coalesce(s.result_supports, '[]') = '[]' THEN 'unavailable' "
        "WHEN e.id IS NULL OR e.redacted_at IS NOT NULL OR e.truncated "
        "THEN 'unavailable' ELSE 'reusable' END AS result_validity "
        f"ORDER BY CASE s.state {ranks} ELSE {len(STEP_STATE_ORDER)} END, s.name "
        "LIMIT $limit"
    )


def steps_in_state_page_query() -> str:
    """Build Cypher reading one page of a task's steps in one state, by name."""
    return (
        f"MATCH (t:{_TASK} {{{HISTORY_RECORD_PROPERTY}: true, "
        "id: $task_id, project_id: $project_id})"
        f"-[:{_HAS_STEP}]->(s:{_STEP} {{{HISTORY_RECORD_PROPERTY}: true}}) "
        "WHERE s.state = $state AND ($after_name IS NULL OR s.name > $after_name) "
        f"OPTIONAL MATCH (t)-[:{_HAS_EVENT}]->(e:{_EVENT} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, seq: s.result_event_seq}}) "
        "RETURN s.name AS name, s.kind AS kind, s.state AS state, "
        "s.result_event_seq AS result_event_seq, "
        "coalesce(s.result_basis, 'unknown') AS result_basis, "
        "coalesce(s.result_supports, '[]') AS result_supports, "
        "CASE WHEN s.state <> 'completed' THEN 'unknown' "
        "WHEN e.id IS NULL OR e.redacted_at IS NOT NULL OR e.truncated "
        "THEN 'unavailable' "
        "WHEN s.result_basis = 'independent' THEN 'reusable' "
        "WHEN coalesce(s.result_basis, 'unknown') <> 'supported' THEN 'unknown' "
        "WHEN coalesce(s.result_supports, '[]') = '[]' THEN 'unavailable' "
        "WHEN e.id IS NULL OR e.redacted_at IS NOT NULL OR e.truncated "
        "THEN 'unavailable' ELSE 'reusable' END AS result_validity "
        "ORDER BY s.name LIMIT $limit"
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
        f"MERGE (r:{_REQUEST} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id, request_id: $request_id}) "
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
        f"MATCH (r:{_REQUEST} "
        f"{{{HISTORY_RECORD_PROPERTY}: true, "
        "project_id: $project_id, request_id: $request_id}) "
        "SET r.result_json = $result_json RETURN count(r) AS stored"
    )
