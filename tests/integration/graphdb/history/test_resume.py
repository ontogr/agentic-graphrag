"""Integration tests for resuming a task after an interruption.

After a stop, a new ConversationHistory reads the task. Every step that is not completed
must be visible so the caller reruns it. A completed step's result must be
reachable through its event sequence number.
"""

from agrag.common.data_models.task import EventKind, StepState
from agrag.graphdb.base import GraphStore
from agrag.history import ConversationHistory


class TestResumeAfterInterruption:
    """A caller reruns only the steps that are not completed."""

    async def test_rerun_set_is_every_step_that_is_not_completed(
        self, store: GraphStore, project: str
    ) -> None:
        """Only the completed step is reused, and its result event is readable."""
        before = ConversationHistory(store, project_id=project, agent_id="agent-a")
        await before.create_task("quarterly", "Prepare the quarterly memo")
        await before.record_event(
            "quarterly", EventKind.TOOL_RESULT, name="fetch", payload="filing text"
        )
        await before.set_step(
            "quarterly", "fetch filing", StepState.COMPLETED, result_event_seq=1
        )
        await before.set_step("quarterly", "draft summary", StepState.IN_PROGRESS)
        await before.set_step("quarterly", "compare figures", StepState.FAILED)
        await before.set_step("quarterly", "check dates", StepState.UNKNOWN)
        await before.set_step("quarterly", "send memo", StepState.NOT_STARTED)
        del before

        after = ConversationHistory(store, project_id=project, agent_id="agent-a")
        lookup = await after.get_task("quarterly")

        assert lookup.view is not None
        view = lookup.view
        completed = {step.name for step in view.steps[StepState.COMPLETED]}
        to_rerun = {
            step.name
            for state, group in view.steps.items()
            if state != StepState.COMPLETED
            for step in group
        }
        assert completed == {"fetch filing"}
        assert to_rerun == {
            "draft summary",
            "compare figures",
            "check dates",
            "send memo",
        }

        result_seq = view.steps[StepState.COMPLETED][0].result_event_seq
        assert result_seq is not None
        page = await after.list_events("quarterly", after_seq=result_seq - 1, limit=1)
        assert page.events[0].kind == EventKind.TOOL_RESULT
        assert page.events[0].payload == "filing text"
