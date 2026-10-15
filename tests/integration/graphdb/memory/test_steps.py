"""Integration tests for steps and the bounded resume view of a task.

The resume view must read the same from a new TaskMemory object on the same
database, which stands in for a fresh process. It must never include event
bodies.
"""

from agrag.common.data_models.task import EventKind, StepKind, StepState
from agrag.graphdb.base import GraphStore
from agrag.memory import TaskMemory


class TestTaskView:
    """The resume view keeps every step state and bounds its size."""

    async def test_keeps_all_five_step_states_for_a_new_instance(
        self, store: GraphStore, project: str
    ) -> None:
        """A new TaskMemory reads each step with its state and result reference."""
        memory = TaskMemory(store, project_id=project, agent_id="agent-a")
        await memory.create_task("audit", "Audit the vendor list")
        await memory.record_event(
            "audit", EventKind.TOOL_RESULT, name="fetch", payload="vendor rows"
        )
        await memory.set_step(
            "audit", "fetch vendors", StepState.COMPLETED, result_event_seq=1
        )
        await memory.set_step("audit", "match names", StepState.IN_PROGRESS)
        await memory.set_step("audit", "check tax ids", StepState.FAILED)
        await memory.set_step("audit", "confirm address", StepState.UNKNOWN)
        await memory.set_step("audit", "send letters", StepState.NOT_STARTED)

        fresh = TaskMemory(store, project_id=project, agent_id="agent-b")
        lookup = await fresh.get_task("audit")

        assert lookup.found is True
        assert lookup.view is not None
        view = lookup.view
        assert view.goal == "Audit the vendor list"
        assert view.last_event_seq == 1
        assert view.step_counts == dict.fromkeys(StepState, 1)
        assert [s.name for s in view.steps[StepState.COMPLETED]] == ["fetch vendors"]
        assert view.steps[StepState.COMPLETED][0].result_event_seq == 1
        assert [s.name for s in view.steps[StepState.UNKNOWN]] == ["confirm address"]
        assert view.steps_truncated is False

    async def test_caps_sixty_steps_and_repeats_the_same_view(
        self, store: GraphStore, project: str
    ) -> None:
        """Sixty steps show at most fifty, report full counts, and read identically."""
        memory = TaskMemory(store, project_id=project, agent_id="agent-a")
        await memory.create_task("bulk", "Process sixty items")
        for index in range(10):
            await memory.set_step(
                "bulk", f"open-{index:02d}", StepState.IN_PROGRESS, kind=StepKind.READ
            )
        for index in range(50):
            await memory.set_step("bulk", f"done-{index:02d}", StepState.COMPLETED)

        fresh = TaskMemory(store, project_id=project, agent_id="agent-b")
        first = await fresh.get_task("bulk")
        second = await fresh.get_task("bulk")

        assert first.view is not None
        assert first.view == second.view
        view = first.view
        shown = [step for group in view.steps.values() for step in group]
        assert len(shown) == 50
        assert view.steps_truncated is True
        assert view.step_counts[StepState.IN_PROGRESS] == 10
        assert view.step_counts[StepState.COMPLETED] == 50
        assert sum(view.step_counts.values()) == 60
        assert all(
            step.name.startswith("open-") for step in view.steps[StepState.IN_PROGRESS]
        )

    async def test_view_holds_no_event_bodies(
        self, store: GraphStore, project: str
    ) -> None:
        """The resume view never carries the text of an event."""
        memory = TaskMemory(store, project_id=project, agent_id="agent-a")
        await memory.create_task("private", "Keep bodies out of the view")
        await memory.record_event(
            "private", EventKind.MESSAGE, payload="BODY-SENTINEL-7f3a"
        )

        lookup = await memory.get_task("private")

        assert lookup.view is not None
        assert "BODY-SENTINEL-7f3a" not in lookup.view.model_dump_json()

    async def test_unknown_task_gives_a_not_found_result(
        self, store: GraphStore, project: str
    ) -> None:
        """Reading a task that does not exist returns found false and no view."""
        memory = TaskMemory(store, project_id=project, agent_id="agent-a")

        lookup = await memory.get_task("never created")

        assert lookup.found is False
        assert lookup.view is None
