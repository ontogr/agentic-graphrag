"""Project-scoped redaction and task deletion operations."""

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_OID, uuid5

from agrag.common.data_models.retention import RetentionErrorCode, RetentionResult
from agrag.common.data_models.task import (
    EVENT_LABEL,
    HAS_EVENT,
    HAS_STEP,
    PROJECT_LABEL,
    REQUEST_LABEL,
    STEP_LABEL,
    TASK_LABEL,
)
from agrag.cypher.memory import (
    claim_request_query,
    memory_schema_queries,
    store_request_result_query,
)
from agrag.cypher.retention import (
    delete_task_children_query,
    delete_task_decisions_query,
    delete_task_node_query,
    detach_task_decisions_query,
    event_in_project_query,
    event_supports_query,
    flag_decisions_query,
    redact_event_query,
    task_dependent_decisions_query,
    task_in_project_query,
)
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.graphdb.errors import GraphStoreConstraintViolationError


_MARKER = "[REDACTED]"


def _request_digest(operation: str, arguments: dict[str, Any]) -> str:
    """Hash the operation and arguments in canonical JSON form."""
    body = json.dumps(
        {"operation": operation, "arguments": arguments},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _request_uuid(project_id: str, request_id: str) -> str:
    """Return the stable id for a project-scoped request record."""
    identity = json.dumps(["Request", project_id, request_id])
    return str(uuid5(NAMESPACE_OID, identity))


class _RetentionRefusedError(Exception):
    """A retention validation failure that rolls back the transaction."""

    def __init__(self, error: RetentionErrorCode) -> None:
        super().__init__(error.value)
        self.error = error


class RetentionMemory:
    """Apply retention actions to memory owned by one configured project."""

    def __init__(self, store: GraphStore, project_id: str, agent_id: str) -> None:
        """Bind retention operations to a store, trusted project, and agent."""
        self._store = store
        self._project_id = project_id
        self._agent_id = agent_id
        self._schema_ready = False
        self._schema_lock = asyncio.Lock()

    async def redact_event(
        self, event_id: str, request_id: str | None = None
    ) -> RetentionResult:
        """Replace an event body while keeping its identity and payload hash.

        The event remains in sequence and receives a ``redacted_at`` timestamp.
        A retry with the same request id replays the first result.
        """
        return await self._write(
            "redact_event",
            {"event_id": event_id},
            request_id,
            lambda tx: self._redact(tx, event_id),
        )

    async def delete_task(
        self,
        name: str,
        include_decisions: bool = True,
        request_id: str | None = None,
    ) -> RetentionResult:
        """Delete a task and its events and steps, and optionally its decisions.

        Decisions in other tasks that cite deleted events or decisions are
        directly flagged ``needs_review``. Their ids are returned; no
        transitive review propagation or queueing is performed here.
        """
        return await self._write(
            "delete_task",
            {"name": name, "include_decisions": include_decisions},
            request_id,
            lambda tx: self._delete_task(tx, name, include_decisions),
        )

    async def _redact(
        self, tx: GraphStoreTransaction, event_id: str
    ) -> RetentionResult:
        params = {"project_id": self._project_id, "event_id": event_id}
        rows = await tx.execute_read(event_in_project_query(), params)
        if not rows:
            raise _RetentionRefusedError(RetentionErrorCode.EVENT_NOT_FOUND)
        timestamp = rows[0]["redacted_at"] or datetime.now(UTC).isoformat()
        await tx.execute_write(
            redact_event_query(),
            {**params, "marker": _MARKER, "redacted_at": timestamp},
        )
        supports = await tx.execute_read(event_supports_query(), params)
        affected = sorted(str(row["id"]) for row in supports)
        for decision_id in affected:
            await tx.execute_write(
                flag_decisions_query(),
                {"project_id": self._project_id, "decision_id": decision_id},
            )
        return RetentionResult(
            recorded=True,
            affected_decision_ids=affected,
        )

    async def _delete_task(
        self, tx: GraphStoreTransaction, name: str, include_decisions: bool
    ) -> RetentionResult:
        params = {"project_id": self._project_id, "name": name}
        if not await tx.execute_read(task_in_project_query(), params):
            raise _RetentionRefusedError(RetentionErrorCode.TASK_NOT_FOUND)
        dependent_rows = await tx.execute_read(task_dependent_decisions_query(), params)
        affected = sorted({str(row["id"]) for row in dependent_rows if row["id"]})
        for decision_id in affected:
            await tx.execute_write(
                flag_decisions_query(),
                {"project_id": self._project_id, "decision_id": decision_id},
            )
        await tx.execute_write(delete_task_children_query(), params)
        if include_decisions:
            await tx.execute_write(delete_task_decisions_query(), params)
        else:
            await tx.execute_write(detach_task_decisions_query(), params)
        await tx.execute_write(delete_task_node_query(), params)
        return RetentionResult(recorded=True, affected_decision_ids=affected)

    async def _write(
        self,
        operation: str,
        arguments: dict[str, Any],
        request_id: str | None,
        effect: Callable[[GraphStoreTransaction], Awaitable[RetentionResult]],
    ) -> RetentionResult:
        if request_id is not None and not 0 < len(request_id) <= 64:
            return RetentionResult(
                recorded=False, error=RetentionErrorCode.INVALID_REQUEST_ID
            )
        await self._ensure_schema()
        digest = _request_digest(operation, arguments)

        async def work(tx: GraphStoreTransaction) -> RetentionResult:
            if request_id is None:
                return await effect(tx)
            claims = await tx.execute_write(
                claim_request_query(),
                {
                    "project_id": self._project_id,
                    "request_id": request_id,
                    "id": _request_uuid(self._project_id, request_id),
                    "operation": operation,
                    "payload_sha256": digest,
                },
            )
            if claims[0]["payload_sha256"] != digest:
                raise _RetentionRefusedError(RetentionErrorCode.REQUEST_ID_REUSED)
            if claims[0]["result_json"] is not None:
                return RetentionResult.model_validate_json(claims[0]["result_json"])
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

        for _ in range(3):
            try:
                return await self._store.run_in_transaction(work)
            except _RetentionRefusedError as refused:
                return RetentionResult(recorded=False, error=refused.error)
            except GraphStoreConstraintViolationError:
                continue
        return await self._store.run_in_transaction(work)

    async def _ensure_schema(self) -> None:
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
