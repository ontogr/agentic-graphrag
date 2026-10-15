"""Durable task state with raw events and steps, scoped to one project.

``TaskMemory`` writes named tasks, appends raw events and sets steps in the
graph store. Each write runs in one transaction, so event sequence numbers are
gapless under concurrent appends and a failed write leaves no partial state.
The project and the author come from the constructor, never from a method
argument. Nothing here calls a model or an embedder.
"""

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, NamedTuple, TypeVar
from uuid import NAMESPACE_OID, UUID, uuid5

from agrag.common.data_models.decision import ConflictGroup, Decision
from agrag.common.data_models.task import (
    EVENT_LABEL,
    HAS_EVENT,
    HAS_STEP,
    PROJECT_LABEL,
    REQUEST_LABEL,
    STEP_LABEL,
    STEP_STATE_ORDER,
    TASK_LABEL,
    CreateTaskResult,
    Event,
    EventKind,
    EventPage,
    MemoryErrorCode,
    RecordEventResult,
    SetStepResult,
    Step,
    StepKind,
    StepState,
    StepSummary,
    Task,
    TaskLookup,
    TaskStatus,
    TaskView,
    WriteResult,
)
from agrag.cypher.memory import (
    append_event_query,
    claim_request_query,
    create_task_query,
    event_by_seq_query,
    events_page_query,
    find_task_query,
    memory_schema_queries,
    set_event_id_query,
    step_page_query,
    step_state_counts_query,
    store_request_result_query,
    task_conflict_decisions_query,
    task_conflict_keys_query,
    task_review_decisions_query,
    upsert_step_query,
)
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.graphdb.errors import GraphStoreConstraintViolationError
from agrag.memory.decisions import _decision_from_row


MAX_PAYLOAD_CHARACTERS = 32_000
MAX_REQUEST_ID_LENGTH = 64
STEP_VIEW_LIMIT = 50
EVENT_PAGE_LIMIT = 200
_WRITE_ATTEMPTS = 3

_ResultT = TypeVar("_ResultT", bound=WriteResult)
_Reader = GraphStore | GraphStoreTransaction


class BoundedPayload(NamedTuple):
    """An event payload cut to the storage limit.

    Attributes:
        payload: The stored text, at most ``MAX_PAYLOAD_CHARACTERS`` long.
        truncated: Whether the stored text is shorter than the full text.
        payload_sha256: SHA-256 of the full text, encoded as UTF-8.
    """

    payload: str
    truncated: bool
    payload_sha256: str


class _WriteRefusedError(Exception):
    """Stops a write before it is recorded so its transaction rolls back."""

    def __init__(self, code: MemoryErrorCode) -> None:
        """Remember the error code to return to the caller.

        Args:
            code: The fixed error code of the refusal.
        """
        super().__init__(code.value)
        self.code = code


def bound_payload(text: str) -> BoundedPayload:
    """Cut an event payload to the storage limit and hash the full text.

    Args:
        text: The full payload.

    Returns:
        The stored text, whether it was cut, and the hash of the full text.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if len(text) <= MAX_PAYLOAD_CHARACTERS:
        return BoundedPayload(text, False, digest)
    return BoundedPayload(text[:MAX_PAYLOAD_CHARACTERS], True, digest)


def build_task_view(
    *,
    task_name: str,
    goal: str,
    status: TaskStatus,
    last_event_seq: int,
    step_counts: Mapping[StepState, int],
    steps: Sequence[StepSummary],
    decisions: Sequence[Decision] = (),
    decision_count: int | None = None,
    review_decisions: Sequence[Decision] = (),
    conflicts: Sequence[ConflictGroup] = (),
    conflicts_truncated: bool = False,
) -> TaskView:
    """Assemble a resume view from a task's counts and step summaries.

    The steps are sorted by ``STEP_STATE_ORDER`` and then by name, and the
    first ``STEP_VIEW_LIMIT`` of them are shown. Counts come from the caller
    and include steps that are not shown.

    Args:
        task_name: The task name.
        goal: The task goal.
        status: The task status.
        last_event_seq: The sequence number of the last event, or 0.
        step_counts: The number of steps in each state. Missing states count
            as zero.
        steps: Step summaries to choose from. The list may be longer than the
            cap, or cover only part of the task.
        decisions: Active decisions to include in the bounded resume view.
        decision_count: Total active decisions before applying the view cap.
        review_decisions: Active decisions that need review.
        conflicts: Cross-task conflicts touching this task.
        conflicts_truncated: Whether more than ten conflicts match.

    Returns:
        The view. ``steps_truncated`` is true when the counts exceed the
        number of shown steps.
    """
    rank = {state: index for index, state in enumerate(STEP_STATE_ORDER)}
    shown = sorted(steps, key=lambda step: (rank[step.state], step.name))
    shown = shown[:STEP_VIEW_LIMIT]
    grouped: dict[StepState, list[StepSummary]] = {
        state: [] for state in STEP_STATE_ORDER
    }
    for step in shown:
        grouped[step.state].append(step)
    counts = {state: step_counts.get(state, 0) for state in STEP_STATE_ORDER}
    return TaskView(
        task_name=task_name,
        goal=goal,
        status=status,
        last_event_seq=last_event_seq,
        steps=grouped,
        step_counts=counts,
        steps_truncated=sum(counts.values()) > len(shown),
        decisions=list(decisions[:20]),
        decision_count=decision_count if decision_count is not None else len(decisions),
        decisions_truncated=(decision_count or len(decisions)) > 20,
        review_decisions=list(review_decisions[:20]),
        conflicts=list(conflicts[:10]),
        conflicts_truncated=conflicts_truncated or len(conflicts) > 10,
    )


def _uuid(*parts: str | int | UUID) -> UUID:
    """Derive a stable UUID from a list of parts, as the structure keys do."""
    return uuid5(NAMESPACE_OID, json.dumps([str(part) for part in parts]))


def _digest(operation: str, arguments: Mapping[str, Any]) -> str:
    """Hash an operation name with its arguments in canonical JSON form."""
    body = json.dumps(
        {"operation": operation, "arguments": arguments},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


async def _find_task(reader: _Reader, project_id: str, name: str) -> Task | None:
    """Read one task of a project by name, or return None when it is absent."""
    rows = await reader.execute_read(
        find_task_query(), {"project_id": project_id, "name": name}
    )
    if not rows:
        return None
    return Task.model_validate(rows[0])


class TaskMemory:
    """Durable task state for one project, written on behalf of one agent.

    Operations take the project and author from this constructor. Each write
    takes an optional ``request_id``. A repeated write with the same id and
    arguments returns the stored result, and the same id with other arguments
    returns ``request_id_reused``.

    """

    def __init__(self, store: GraphStore, *, project_id: str, agent_id: str) -> None:
        """Bind the store to one project and one agent.

        Args:
            store: The graph store that holds the task memory.
            project_id: The project every operation is scoped to. Use a value
                from trusted configuration.
            agent_id: The author recorded on tasks and events.
        """
        self._store = store
        self._project_id = project_id
        self._agent_id = agent_id
        self._schema_ready = False
        self._schema_lock = asyncio.Lock()

    async def create_task(
        self, name: str, goal: str, *, request_id: str | None = None
    ) -> CreateTaskResult:
        """Create a task, or return the existing task of that name.

        Args:
            name: The task name, unique within the project.
            goal: The goal. An existing task of the same name must have the
                same goal.
            request_id: Optional id of at most 64 characters for a safe retry.

        Returns:
            The task when recorded. Otherwise ``task_exists`` when the name is
            taken by a task with another goal.
        """
        arguments = {"name": name, "goal": goal}
        return await self._write(
            operation="create_task",
            arguments=arguments,
            request_id=request_id,
            result_type=CreateTaskResult,
            effect=lambda tx: self._create_task_effect(tx, name, goal),
        )

    async def record_event(
        self,
        task_name: str,
        kind: EventKind,
        *,
        role: str | None = None,
        name: str | None = None,
        payload: str,
        request_id: str | None = None,
    ) -> RecordEventResult:
        """Append one raw event to a task.

        The payload is cut to ``MAX_PAYLOAD_CHARACTERS`` when longer, and the
        event records the hash of the full text. No model is called.

        Args:
            task_name: The task the event belongs to.
            kind: The kind of event.
            role: The speaker role for a message, or None.
            name: The tool or source name for a tool event, or None.
            payload: The event text.
            request_id: Optional id of at most 64 characters for a safe retry.

        Returns:
            The event when recorded. Otherwise ``task_not_found``.
        """
        bounded = bound_payload(payload)
        arguments = {
            "task_name": task_name,
            "kind": kind.value,
            "role": role,
            "name": name,
            "payload_sha256": bounded.payload_sha256,
        }
        return await self._write(
            operation="record_event",
            arguments=arguments,
            request_id=request_id,
            result_type=RecordEventResult,
            effect=lambda tx: self._append_event_effect(
                tx,
                task_name=task_name,
                kind=kind,
                role=role,
                name=name,
                bounded=bounded,
            ),
        )

    async def set_step(
        self,
        task_name: str,
        name: str,
        state: StepState,
        *,
        kind: StepKind = StepKind.OTHER,
        result_event_seq: int | None = None,
        request_id: str | None = None,
    ) -> SetStepResult:
        """Create or update a step of a task.

        Args:
            task_name: The task the step belongs to.
            name: The step name, unique within the task.
            state: The new state. Use ``unknown`` when the outcome is not known.
            kind: The broad category of the step.
            result_event_seq: The sequence number of the event that holds the
                result, or None.
            request_id: Optional id of at most 64 characters for a safe retry.

        Returns:
            The step when recorded. Otherwise ``task_not_found`` or
            ``event_not_found`` when ``result_event_seq`` names no event.
        """
        arguments = {
            "task_name": task_name,
            "name": name,
            "state": state.value,
            "kind": kind.value,
            "result_event_seq": result_event_seq,
        }
        return await self._write(
            operation="set_step",
            arguments=arguments,
            request_id=request_id,
            result_type=SetStepResult,
            effect=lambda tx: self._set_step_effect(
                tx,
                task_name=task_name,
                name=name,
                state=state,
                kind=kind,
                result_event_seq=result_event_seq,
            ),
        )

    async def get_task(self, name: str) -> TaskLookup:
        """Read the bounded resume view of a task.

        The view has the goal, status, last event sequence number and the first
        steps in view order, with counts for every state. It has no event
        bodies.

        Args:
            name: The task name.

        Returns:
            The view when the task exists in this project. Otherwise
            ``found`` is false.
        """
        task = await _find_task(self._store, self._project_id, name)
        if task is None:
            return TaskLookup(found=False)
        params = {"project_id": self._project_id, "task_id": str(task.id)}
        count_rows = await self._store.execute_read(step_state_counts_query(), params)
        counts = {StepState(row["state"]): int(row["count"]) for row in count_rows}
        page_rows = await self._store.execute_read(
            step_page_query(), {**params, "limit": STEP_VIEW_LIMIT}
        )
        steps = [StepSummary.model_validate(row) for row in page_rows]
        decision_rows = await self._store.execute_read(
            "MATCH (t:MemoryTask {project_id: $project_id, id: $task_id})"
            "-[:MADE]->(d:MemoryDecision {status: 'active'}) "
            "OPTIONAL MATCH (d)-[:HAS_SUPPORT]->(s:MemorySupport) "
            "WITH t, d, s ORDER BY s.ordinal "
            "WITH t, d, collect(s) AS supports "
            "RETURN d AS decision, supports, t.name AS task_name "
            "ORDER BY d.created_at DESC LIMIT 21",
            params,
        )
        decisions = [_decision_from_row(row) for row in decision_rows[:20]]
        decision_count = await self._store.execute_read(
            "MATCH (t:MemoryTask {project_id: $project_id, id: $task_id})"
            "-[:MADE]->(d:MemoryDecision {status: 'active'}) "
            "RETURN count(d) AS count",
            params,
        )
        review_rows = await self._store.execute_read(
            task_review_decisions_query(), {**params, "limit": 21}
        )
        review_decisions = [
            _decision_from_row(row) for row in review_rows[:20]
        ]
        conflict_keys = await self._store.execute_read(
            task_conflict_keys_query(), {**params, "limit": 11}
        )
        keys = [row["choice_key"] for row in conflict_keys[:10]]
        conflict_rows = (
            await self._store.execute_read(
                task_conflict_decisions_query(),
                {"project_id": self._project_id, "choice_keys": keys, "limit": 101},
            )
            if keys
            else []
        )
        decisions_by_key: dict[str, list[Decision]] = {}
        for row in conflict_rows[:100]:
            decision = _decision_from_row(row)
            decisions_by_key.setdefault(decision.choice_key, []).append(decision)
        conflicts = [
            ConflictGroup(
                choice_key=key,
                decisions=decisions_by_key.get(key, [])[:10],
                truncated=len(decisions_by_key.get(key, [])) > 10,
            )
            for key in keys
        ]
        view = build_task_view(
            task_name=task.name,
            goal=task.goal,
            status=task.status,
            last_event_seq=task.event_seq,
            step_counts=counts,
            steps=steps,
            decisions=decisions,
            decision_count=int(decision_count[0]["count"]),
            review_decisions=review_decisions,
            conflicts=conflicts,
            conflicts_truncated=len(conflict_keys) > 10,
        )
        return TaskLookup(found=True, view=view)

    async def list_events(
        self, task_name: str, *, after_seq: int = 0, limit: int = 50
    ) -> EventPage:
        """Read events of a task in sequence order, one page at a time.

        Args:
            task_name: The task name.
            after_seq: Return events with a larger sequence number than this.
            limit: Maximum events in the page, between 1 and 200.

        Returns:
            The page. When the task does not exist, ``found`` is false and the
            page is empty.
        """
        task = await _find_task(self._store, self._project_id, task_name)
        if task is None:
            return EventPage(found=False, events=[], truncated=False)
        size = max(1, min(limit, EVENT_PAGE_LIMIT))
        rows = await self._store.execute_read(
            events_page_query(),
            {
                "project_id": self._project_id,
                "task_id": str(task.id),
                "after_seq": max(0, after_seq),
                "limit": size + 1,
            },
        )
        events = [Event.model_validate(row) for row in rows[:size]]
        truncated = len(rows) > size
        return EventPage(
            found=True,
            events=events,
            truncated=truncated,
            next_after_seq=events[-1].seq if truncated else None,
        )

    async def _write(
        self,
        *,
        operation: str,
        arguments: Mapping[str, Any],
        request_id: str | None,
        result_type: type[_ResultT],
        effect: Callable[[GraphStoreTransaction], Awaitable[_ResultT]],
    ) -> _ResultT:
        """Run one write in a transaction and convert refusals to results.

        A refusal raised inside the transaction rolls it back. A constraint
        violation means another transaction created the same unique key first,
        so the write is retried and then reads that transaction's result.
        """
        if request_id is not None and not (
            0 < len(request_id) <= MAX_REQUEST_ID_LENGTH
        ):
            return result_type(recorded=False, error=MemoryErrorCode.INVALID_REQUEST_ID)
        digest = _digest(operation, arguments)

        async def work(tx: GraphStoreTransaction) -> _ResultT:
            if request_id is None:
                return await effect(tx)
            return await self._claim_and_run(
                tx,
                request_id=request_id,
                digest=digest,
                operation=operation,
                result_type=result_type,
                effect=effect,
            )

        await self._ensure_schema()
        for _ in range(_WRITE_ATTEMPTS - 1):
            try:
                return await self._attempt(work, result_type)
            except GraphStoreConstraintViolationError:
                continue
        return await self._attempt(work, result_type)

    async def _attempt(
        self,
        work: Callable[[GraphStoreTransaction], Awaitable[_ResultT]],
        result_type: type[_ResultT],
    ) -> _ResultT:
        """Run the work once and turn a refusal into a result."""
        try:
            return await self._store.run_in_transaction(work)
        except _WriteRefusedError as refused:
            return result_type(recorded=False, error=refused.code)

    async def _claim_and_run(
        self,
        tx: GraphStoreTransaction,
        *,
        request_id: str,
        digest: str,
        operation: str,
        result_type: type[_ResultT],
        effect: Callable[[GraphStoreTransaction], Awaitable[_ResultT]],
    ) -> _ResultT:
        """Replay a stored result, or run the effect and store its result."""
        rows = await tx.execute_write(
            claim_request_query(),
            {
                "project_id": self._project_id,
                "request_id": request_id,
                "id": str(_uuid("Request", self._project_id, request_id)),
                "operation": operation,
                "payload_sha256": digest,
            },
        )
        claim = rows[0]
        if claim["payload_sha256"] != digest:
            raise _WriteRefusedError(MemoryErrorCode.REQUEST_ID_REUSED)
        if claim["result_json"] is not None:
            return result_type.model_validate_json(claim["result_json"])
        result = await effect(tx)
        await tx.execute_write(
            store_request_result_query(),
            {
                "project_id": self._project_id,
                "request_id": request_id,
                "result_json": result.model_dump_json(),
            },
        )
        return result

    async def _create_task_effect(
        self, tx: GraphStoreTransaction, name: str, goal: str
    ) -> CreateTaskResult:
        """Create the task, or return the existing one when the goal matches."""
        existing = await _find_task(tx, self._project_id, name)
        if existing is not None:
            if existing.goal != goal:
                raise _WriteRefusedError(MemoryErrorCode.TASK_EXISTS)
            return CreateTaskResult(recorded=True, task=existing)
        task_id = _uuid(self._project_id, name)
        created_at = datetime.now(UTC)
        await tx.execute_write(
            create_task_query(),
            {
                "project_id": self._project_id,
                "id": str(task_id),
                "name": name,
                "goal": goal,
                "status": TaskStatus.OPEN.value,
                "author": self._agent_id,
                "created_at": created_at.isoformat(),
            },
        )
        task = Task(
            id=task_id,
            project_id=self._project_id,
            name=name,
            goal=goal,
            status=TaskStatus.OPEN,
            event_seq=0,
            author=self._agent_id,
            created_at=created_at,
        )
        return CreateTaskResult(recorded=True, task=task)

    async def _append_event_effect(
        self,
        tx: GraphStoreTransaction,
        *,
        task_name: str,
        kind: EventKind,
        role: str | None,
        name: str | None,
        bounded: BoundedPayload,
    ) -> RecordEventResult:
        """Append the event with the next sequence number."""
        task = await _find_task(tx, self._project_id, task_name)
        if task is None:
            raise _WriteRefusedError(MemoryErrorCode.TASK_NOT_FOUND)
        recorded_at = datetime.now(UTC)
        rows = await tx.execute_write(
            append_event_query(),
            {
                "project_id": self._project_id,
                "task_id": str(task.id),
                "kind": kind.value,
                "role": role,
                "name": name,
                "payload": bounded.payload,
                "payload_sha256": bounded.payload_sha256,
                "truncated": bounded.truncated,
                "author": self._agent_id,
                "at": recorded_at.isoformat(),
            },
        )
        seq = int(rows[0]["seq"])
        event_id = _uuid("Event", task.id, seq)
        await tx.execute_write(
            set_event_id_query(),
            {"task_id": str(task.id), "seq": seq, "id": str(event_id)},
        )
        event = Event(
            id=event_id,
            task_id=task.id,
            seq=seq,
            kind=kind,
            role=role,
            name=name,
            payload=bounded.payload,
            payload_sha256=bounded.payload_sha256,
            truncated=bounded.truncated,
            author=self._agent_id,
            at=recorded_at,
        )
        return RecordEventResult(recorded=True, event=event)

    async def _set_step_effect(
        self,
        tx: GraphStoreTransaction,
        *,
        task_name: str,
        name: str,
        state: StepState,
        kind: StepKind,
        result_event_seq: int | None,
    ) -> SetStepResult:
        """Create or update the step, checking the result event first."""
        task = await _find_task(tx, self._project_id, task_name)
        if task is None:
            raise _WriteRefusedError(MemoryErrorCode.TASK_NOT_FOUND)
        task_params = {"project_id": self._project_id, "task_id": str(task.id)}
        if result_event_seq is not None:
            found = await tx.execute_read(
                event_by_seq_query(), {**task_params, "seq": result_event_seq}
            )
            if not found:
                raise _WriteRefusedError(MemoryErrorCode.EVENT_NOT_FOUND)
        rows = await tx.execute_write(
            upsert_step_query(),
            {
                **task_params,
                "step_id": str(_uuid("Step", task.id, name)),
                "name": name,
                "kind": kind.value,
                "state": state.value,
                "result_event_seq": result_event_seq,
                "updated_seq": task.event_seq,
            },
        )
        step = Step.model_validate(rows[0])
        return SetStepResult(recorded=True, step=step)

    async def _ensure_schema(self) -> None:
        """Register the task memory labels and create their constraints once."""
        if self._schema_ready:
            return
        async with self._schema_lock:
            if self._schema_ready:
                return
            await self._store.register_labels(
                [TASK_LABEL, EVENT_LABEL, STEP_LABEL, REQUEST_LABEL, PROJECT_LABEL]
            )
            await self._store.register_relation_types([HAS_EVENT, HAS_STEP])
            for query in memory_schema_queries():
                await self._store.execute_write(query)
            self._schema_ready = True
