"""Checks the bounded tool set exposed by a default task agent."""

from unittest.mock import MagicMock

from agrag.agents.tools.core import make_core_tools


class TestCoreTools:
    """The default agent exposes only scoped evidence and memory operations."""

    def test_returns_evidence_navigation_task_and_decision_tools(self) -> None:
        """Tool names expose the single-agent operations and no delegation."""
        tools, _ = make_core_tools(
            graph_store=MagicMock(),
            embedder=MagicMock(),
            scope=frozenset({"doc-1"}),
            task_name="task-1",
            memory=MagicMock(),
            decisions=MagicMock(),
            fetched_ids=[],
            fetched_outcomes=[],
            max_chars=1_000,
            max_tool_calls=10,
        )

        assert {tool.name for tool in tools} == {
            "discover_evidence",
            "fetch_evidence",
            "navigate",
            "find_entities",
            "explore",
            "check_citations",
            "get_task",
            "set_step",
            "record_decision",
            "supersede_decision",
            "search_decisions",
            "get_event",
            "list_events",
            "list_steps",
            "get_decision",
            "list_support_history",
            "list_decisions",
            "list_decisions_for_review",
            "reaffirm_decision",
            "continue_decision_review",
        }
