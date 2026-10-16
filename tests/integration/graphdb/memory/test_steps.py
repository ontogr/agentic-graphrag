"""Integration tests for steps and the bounded resume view of a task.

The resume view must read the same from a new TaskMemory object on the same
database, which stands in for a fresh process. It must never include event
bodies.
"""

from agrag.common.data_models.decision import DocumentSupportInput
from agrag.common.data_models.task import (
    EventKind,
    StepKind,
    StepResultBasis,
    StepResultValidity,
    StepState,
)
from agrag.evidence import fetch
from agrag.graphdb.base import GraphStore
from agrag.memory import TaskMemory
from tests.integration.graphdb.memory.conftest import DocumentEnv
from tests.integration.retrieval.evidence._corpus import (
    KEEP_TEXT,
    make_document,
    span_evidence_id,
)


class TestTaskView:
    """The resume view keeps every step state and bounds its size."""

    async def test_source_activation_invalidates_completed_result(
        self, store: GraphStore, project: str, documents: DocumentEnv
    ) -> None:
        """Unrelated updates preserve reuse; a new cited activation requires review."""
        memory = TaskMemory(store, project_id=project, agent_id="agent-a")
        await memory.create_task("source-result", "Analyze a policy")
        event = await memory.record_event(
            "source-result", EventKind.NOTE, payload="Policy analysis"
        )
        evidence_id = span_evidence_id(documents.keep, KEEP_TEXT, 0, 60)
        fetched = await fetch(
            store, [evidence_id], scope=frozenset({documents.keep}), max_chars=2000
        )
        recorded = await memory.set_step(
            "source-result",
            "analyze",
            StepState.COMPLETED,
            result_event_seq=event.event.seq,
            result_basis=StepResultBasis.SUPPORTED,
            supports=[DocumentSupportInput(evidence_id=evidence_id)],
            fetched_evidence=fetched,
        )
        assert recorded.recorded is True
        first = await memory.list_steps_page("source-result", StepState.COMPLETED)
        assert first.steps[0].result_validity is StepResultValidity.REUSABLE
        await documents.graph.add(
            documents=[make_document(documents.harbor, "Unrelated replacement text.")]
        )
        unaffected = await memory.list_steps_page("source-result", StepState.COMPLETED)
        assert unaffected.steps[0].result_validity is StepResultValidity.REUSABLE
        await documents.graph.add(
            documents=[
                make_document(documents.keep, KEEP_TEXT + "\nNew policy qualification.")
            ]
        )
        changed = await memory.list_steps_page("source-result", StepState.COMPLETED)
        assert changed.steps[0].state is StepState.COMPLETED
        assert changed.steps[0].result_validity is StepResultValidity.NEEDS_REVIEW
        assert changed.steps[0].result_supports[0].evidence_id == evidence_id

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

    async def test_lists_steps_in_bounded_pages_with_a_name_cursor(
        self, store: GraphStore, project: str
    ) -> None:
        """A page exposes the next step name without loading later steps."""
        memory = TaskMemory(store, project_id=project, agent_id="agent-a")
        await memory.create_task("paged", "Read steps a page at a time")
        for name in ("step-a", "step-b", "step-c"):
            await memory.set_step("paged", name, StepState.COMPLETED)

        first = await memory.list_steps_page("paged", StepState.COMPLETED, limit=2)
        second = await memory.list_steps_page(
            "paged",
            StepState.COMPLETED,
            after_name=first.next_after_name,
            limit=2,
        )

        assert [step.name for step in first.steps] == ["step-a", "step-b"]
        assert first.truncated is True
        assert first.next_after_name == "step-b"
        assert [step.name for step in second.steps] == ["step-c"]
        assert second.truncated is False

    async def test_independent_completed_result_remains_reusable_after_other_event(
        self, store: GraphStore, project: str
    ) -> None:
        """Independent outputs do not depend on later unrelated task events."""
        memory = TaskMemory(store, project_id=project, agent_id="agent-a")
        await memory.create_task("independent", "Keep independent work reusable")
        await memory.record_event("independent", EventKind.NOTE, payload="result")
        await memory.set_step(
            "independent",
            "calculate",
            StepState.COMPLETED,
            result_event_seq=1,
            result_basis=StepResultBasis.INDEPENDENT,
        )
        await memory.record_event("independent", EventKind.NOTE, payload="unrelated")

        page = await memory.list_steps_page("independent", StepState.COMPLETED)

        assert page.steps[0].result_validity is StepResultValidity.REUSABLE

    async def test_supported_result_without_support_references_is_not_reusable(
        self, store: GraphStore, project: str
    ) -> None:
        """A supported result with no provenance cannot be reused."""
        memory = TaskMemory(store, project_id=project, agent_id="agent-a")
        await memory.create_task("unsupported", "Do not trust missing provenance")
        await memory.record_event("unsupported", EventKind.NOTE, payload="result")
        result = await memory.set_step(
            "unsupported",
            "analyze",
            StepState.COMPLETED,
            result_event_seq=1,
            result_basis=StepResultBasis.SUPPORTED,
        )

        assert result.recorded is False
        assert result.error.value == "support_required"
