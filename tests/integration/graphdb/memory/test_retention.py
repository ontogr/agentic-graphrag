"""Retention operations against a real project memory graph."""

from agrag.common.data_models.decision import EventSupportInput
from agrag.common.data_models.retention import RetentionErrorCode
from agrag.common.data_models.task import (
    EventKind,
    StepResultBasis,
    StepResultValidity,
    StepState,
)
from agrag.memory.decisions import DecisionMemory
from agrag.memory.retention import RetentionMemory
from agrag.memory.tasks import TaskMemory


class TestRetentionMemory:
    """Project-scoped event and task retention behavior."""

    async def test_redact_event_is_idempotent_and_preserves_event_identity(
        self, store, project, other_project
    ):
        """Redaction removes body text and retains event metadata and hash."""
        tasks = TaskMemory(store, project_id=project, agent_id="agent")
        await tasks.create_task("notes", "record notes")
        event = await tasks.record_event(
            "notes", EventKind.NOTE, payload="private text", request_id="event-1"
        )
        await tasks.set_step(
            "notes",
            "use tool output",
            StepState.COMPLETED,
            result_event_seq=event.event.seq,
            result_basis=StepResultBasis.SUPPORTED,
            supports=[EventSupportInput(task_name="notes", seq=event.event.seq)],
        )
        decision = await DecisionMemory(
            store, project_id=project, agent_id="agent"
        ).record_decision(
            "notes",
            "private-event",
            "use the tool output",
            "event support",
            supports=[EventSupportInput(task_name="notes", seq=event.event.seq)],
        )
        assert decision.recorded
        retention = RetentionMemory(store, project, "agent")

        result = await retention.redact_event(
            str(event.event.id), request_id="redact-1"
        )
        replay = await retention.redact_event(
            str(event.event.id), request_id="redact-1"
        )
        reused = await retention.redact_event("another-event-id", request_id="redact-1")
        foreign = await RetentionMemory(store, other_project, "agent").redact_event(
            str(event.event.id)
        )
        rows = await store.execute_read(
            "MATCH (t:MemoryTask {project_id: $project_id})-[:HAS_EVENT]->"
            "(e:MemoryEvent {id: $event_id}) RETURN e AS event",
            {"project_id": project, "event_id": str(event.event.id)},
        )

        assert result.recorded and replay == result
        assert not reused.recorded
        assert reused.error is RetentionErrorCode.REQUEST_ID_REUSED
        assert not foreign.recorded
        assert rows[0]["event"]["payload"] == "[REDACTED]"
        assert rows[0]["event"]["payload_sha256"] == event.event.payload_sha256
        assert rows[0]["event"]["id"] == str(event.event.id)
        assert rows[0]["event"]["seq"] == event.event.seq
        assert rows[0]["event"]["kind"] == event.event.kind.value
        assert rows[0]["event"]["redacted_at"] is not None
        exact = await tasks.fetch_event("notes", event.event.seq)
        assert exact.event is not None
        assert exact.event.redacted_at is not None
        assert exact.event.payload == "[REDACTED]"
        replayed_event = await tasks.record_event(
            "notes", EventKind.NOTE, payload="private text", request_id="event-1"
        )
        assert replayed_event.event.payload == "[REDACTED]"
        assert str(decision.decision.id) in result.affected_decision_ids
        current = await DecisionMemory(
            store, project_id=project, agent_id="agent"
        ).get_decision(decision.decision.id)
        assert current.decision.review_state.value == "needs_review"
        view = await tasks.get_task("notes")
        completed = view.view.steps[StepState.COMPLETED][0]
        assert completed.state is StepState.COMPLETED
        assert completed.result_validity is StepResultValidity.UNAVAILABLE

    async def test_delete_task_flags_event_dependents_and_removes_owned_memory(
        self, store, project
    ):
        """Deleting a source task flags direct dependents and removes its graph."""
        tasks = TaskMemory(store, project_id=project, agent_id="agent")
        await tasks.create_task("source", "source work")
        await tasks.create_task("consumer", "dependent work")
        event = await tasks.record_event("source", EventKind.NOTE, payload="source")
        consumer_event = await tasks.record_event(
            "consumer", EventKind.NOTE, payload="consumer"
        )
        decisions = DecisionMemory(store, project_id=project, agent_id="agent")
        decision = await decisions.record_decision(
            "consumer",
            "choice",
            "keep",
            "based on source",
            supports=[EventSupportInput(task_name="source", seq=event.event.seq)],
        )

        result = await RetentionMemory(store, project, "agent").delete_task("source")
        decision_rows = await store.execute_read(
            "MATCH (t:MemoryTask {project_id: $project_id})-[:MADE]->"
            "(d:MemoryDecision {id: $id}) "
            "RETURN d.review_state AS review_state, "
            "d.review_reason AS review_reason",
            {"project_id": project, "id": str(decision.decision.id)},
        )
        task_after = await tasks.list_events("source")
        consumer_after = await tasks.list_events("consumer")

        assert result.recorded
        assert result.affected_decision_ids == [str(decision.decision.id)]
        assert decision_rows == [
            {"review_state": "needs_review", "review_reason": "source_removed"}
        ]
        assert not task_after.found
        assert consumer_after.events[0].id == consumer_event.event.id
