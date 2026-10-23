"""Pure parts of task history: payload bounding, resume view and module imports.

The module must not load a model client. The import check runs in a fresh
interpreter so modules loaded by other tests do not affect it.
"""

import hashlib
import subprocess
import sys
import textwrap

import pytest

from agrag.common.data_models.task import (
    STEP_STATE_ORDER,
    StepKind,
    StepState,
    StepSummary,
    TaskStatus,
)
from agrag.history.tasks import (
    MAX_PAYLOAD_CHARACTERS,
    STEP_VIEW_LIMIT,
    bound_payload,
    build_task_view,
)


class TestBoundPayload:
    """A payload longer than the limit is cut and keeps the full-text hash."""

    @pytest.mark.parametrize("length", [0, 1, MAX_PAYLOAD_CHARACTERS])
    def test_keeps_payload_within_the_limit_whole(self, length: int) -> None:
        """Text at or under the limit is stored unchanged and not flagged."""
        text = "a" * length

        bounded = bound_payload(text)

        assert bounded.payload == text
        assert bounded.truncated is False
        assert bounded.payload_sha256 == hashlib.sha256(text.encode()).hexdigest()

    def test_cuts_text_over_the_limit_and_hashes_the_full_text(self) -> None:
        """Text over the limit is cut, flagged, and hashed before the cut."""
        text = "b" * (MAX_PAYLOAD_CHARACTERS + 1)

        bounded = bound_payload(text)

        assert len(bounded.payload) == MAX_PAYLOAD_CHARACTERS
        assert bounded.truncated is True
        assert bounded.payload_sha256 == hashlib.sha256(text.encode()).hexdigest()


def _step(name: str, state: StepState) -> StepSummary:
    """Build a step summary with a fixed kind and no result event."""
    return StepSummary(
        name=name, kind=StepKind.OTHER, state=state, result_event_seq=None
    )


class TestTaskView:
    """The resume view lists steps in state order and caps them."""

    def test_groups_steps_by_state_and_sorts_names_within_each_state(self) -> None:
        """Every state is a key, and names are sorted inside each state."""
        steps = [
            _step("zeta", StepState.COMPLETED),
            _step("beta", StepState.NOT_STARTED),
            _step("alpha", StepState.IN_PROGRESS),
            _step("gamma", StepState.IN_PROGRESS),
        ]
        counts = {
            StepState.COMPLETED: 1,
            StepState.NOT_STARTED: 1,
            StepState.IN_PROGRESS: 2,
        }

        view = build_task_view(
            task_name="t",
            goal="g",
            status=TaskStatus.OPEN,
            last_event_seq=4,
            step_counts=counts,
            steps=steps,
        )

        assert list(view.steps) == list(STEP_STATE_ORDER)
        assert [s.name for s in view.steps[StepState.IN_PROGRESS]] == [
            "alpha",
            "gamma",
        ]
        assert view.steps[StepState.FAILED] == []
        assert view.step_counts[StepState.FAILED] == 0
        assert view.step_counts[StepState.IN_PROGRESS] == 2
        assert view.steps_truncated is False

    def test_caps_shown_steps_and_reports_truncation_with_full_counts(self) -> None:
        """Steps beyond the cap are hidden, and the counts still include them."""
        steps = [_step(f"done-{i:02d}", StepState.COMPLETED) for i in range(60)]
        counts = {StepState.COMPLETED: 60}

        view = build_task_view(
            task_name="t",
            goal="g",
            status=TaskStatus.OPEN,
            last_event_seq=0,
            step_counts=counts,
            steps=steps,
        )

        shown = [s for group in view.steps.values() for s in group]
        assert len(shown) == STEP_VIEW_LIMIT
        assert view.steps_truncated is True
        assert view.step_counts[StepState.COMPLETED] == 60

    def test_hides_completed_steps_before_steps_that_need_work(self) -> None:
        """Under the cap, steps that still need work are shown first."""
        steps = [_step(f"done-{i:02d}", StepState.COMPLETED) for i in range(50)]
        steps.append(_step("retry-me", StepState.FAILED))
        counts = {StepState.COMPLETED: 50, StepState.FAILED: 1}

        view = build_task_view(
            task_name="t",
            goal="g",
            status=TaskStatus.OPEN,
            last_event_seq=0,
            step_counts=counts,
            steps=steps,
        )

        assert [s.name for s in view.steps[StepState.FAILED]] == ["retry-me"]
        assert len(view.steps[StepState.COMPLETED]) == STEP_VIEW_LIMIT - 1
        assert view.steps_truncated is True


class TestModuleImports:
    """Importing the history package loads no model client."""

    def test_import_loads_no_llm_or_embedding_client(self) -> None:
        """A fresh interpreter importing agrag.history has no LLM SDK loaded."""
        check = textwrap.dedent(
            """
            import sys
            from agrag.decisions import DecisionTraces
            from agrag.history import ConversationHistory, HistoryRetention

            assert ConversationHistory.__name__ == "ConversationHistory"
            assert HistoryRetention.__name__ == "HistoryRetention"
            assert DecisionTraces.__name__ == "DecisionTraces"

            forbidden = ("agrag.llm", "openai", "agrag.llm.baml_client")
            loaded = [
                name
                for name in sys.modules
                if any(name == f or name.startswith(f + ".") for f in forbidden)
            ]
            print(",".join(sorted(loaded)))
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", check],
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.stdout.strip() == ""
