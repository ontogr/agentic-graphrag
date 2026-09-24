"""Tests for the planner and researcher prompt constants.

Asserts the placeholders that the agent build substitutes exist in the
templates, so a renamed placeholder fails here instead of silently leaving
braces in the prompt.
"""

from agrag.agents.prompts import PLANNER_SYSTEM, RESEARCHER_SYSTEM


class TestPlannerSystem:
    """PLANNER_SYSTEM carries the loop instructions."""

    def test_has_max_research_attempts_placeholder(self) -> None:
        """The attempt-count placeholder is present before substitution."""
        assert "{max_research_attempts}" in PLANNER_SYSTEM


class TestResearcherSystem:
    """RESEARCHER_SYSTEM carries the schema-aware research instructions."""

    def test_has_schema_summary_placeholder(self) -> None:
        """The schema placeholder make_researcher_spec depends on exists."""
        assert "{schema_summary}" in RESEARCHER_SYSTEM
