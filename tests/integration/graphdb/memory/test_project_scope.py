"""Integration tests that task memory stays inside one project.

A task created under one project must be invisible to another project, even
when the other project uses the same task name.
"""

from agrag.common.data_models.task import EventKind, MemoryErrorCode, StepState
from agrag.graphdb.base import GraphStore
from agrag.memory import TaskMemory


class TestProjectScope:
    """Reads and writes from another project never reach a task."""

    async def test_task_of_another_project_is_not_found_or_writable(
        self,
        store: GraphStore,
        project: str,
        other_project: str,
    ) -> None:
        """Exact-name reads and writes from project B do not touch project A."""
        owner = TaskMemory(store, project_id=project, agent_id="agent-a")
        await owner.create_task("shared name", "Goal A")
        await owner.record_event("shared name", EventKind.NOTE, payload="from A")
        outsider = TaskMemory(store, project_id=other_project, agent_id="agent-b")

        lookup = await outsider.get_task("shared name")
        page = await outsider.list_events("shared name")
        event = await outsider.record_event(
            "shared name", EventKind.NOTE, payload="from B"
        )
        step = await outsider.set_step("shared name", "step", StepState.COMPLETED)

        assert lookup.found is False
        assert page.found is False
        assert page.events == []
        assert event.recorded is False
        assert event.error == MemoryErrorCode.TASK_NOT_FOUND
        assert step.recorded is False
        assert step.error == MemoryErrorCode.TASK_NOT_FOUND

        owner_view = await owner.get_task("shared name")
        assert owner_view.view is not None
        assert owner_view.view.goal == "Goal A"
        assert owner_view.view.last_event_seq == 1
        assert owner_view.view.step_counts[StepState.COMPLETED] == 0

    async def test_same_name_in_another_project_is_a_separate_task(
        self,
        store: GraphStore,
        project: str,
        other_project: str,
    ) -> None:
        """Creating the same name in project B makes a separate task."""
        first = TaskMemory(store, project_id=project, agent_id="agent-a")
        second = TaskMemory(store, project_id=other_project, agent_id="agent-b")
        created_a = await first.create_task("review", "Goal A")

        created_b = await second.create_task("review", "Goal B")

        assert created_a.task is not None
        assert created_b.task is not None
        assert created_b.task.id != created_a.task.id
        assert created_b.task.goal == "Goal B"
        lookup_a = await first.get_task("review")
        assert lookup_a.view is not None
        assert lookup_a.view.goal == "Goal A"
