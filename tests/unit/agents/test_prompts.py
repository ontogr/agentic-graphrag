"""Tests for the planner/researcher/verifier prompt constants.

Asserts the delegation, retry, and substitution contracts the agent build
depends on: the placeholders exist before substitution and are gone after
it, and the behavioral instructions survive future edits.
"""

from agrag.agents.prompts import PLANNER_SYSTEM, RESEARCHER_SYSTEM, VERIFIER_SYSTEM


class TestPlannerSystem:
    """PLANNER_SYSTEM carries the loop instructions."""

    def test_mentions_task_tool_delegation(self) -> None:
        """The planner is told to delegate to the researcher and verifier."""
        assert "task tool" in PLANNER_SYSTEM
        assert "researcher" in PLANNER_SYSTEM
        assert "verifier" in PLANNER_SYSTEM

    def test_insufficient_retries_and_contradictory_does_not(self) -> None:
        """INSUFFICIENT retries; CONTRADICTORY surfaces a caveat instead."""
        assert "INSUFFICIENT" in PLANNER_SYSTEM
        assert "CONTRADICTORY" in PLANNER_SYSTEM
        assert "do not retry" in PLANNER_SYSTEM

    def test_has_max_research_attempts_placeholder(self) -> None:
        """The attempt-count placeholder is present before substitution."""
        assert "{max_research_attempts}" in PLANNER_SYSTEM

    def test_replace_leaves_no_placeholder_behind(self) -> None:
        """Substitution actually lands; a typo'd name would no-op silently."""
        filled = PLANNER_SYSTEM.replace("{max_research_attempts}", "3")
        assert "{max_research_attempts}" not in filled

    def test_insufficient_evidence_has_a_stable_final_answer_marker(self) -> None:
        """Incomplete research produces an explicit answer prefix."""
        assert 'begin the final answer with "Insufficient evidence:"' in PLANNER_SYSTEM


class TestResearcherSystem:
    """RESEARCHER_SYSTEM carries the schema-aware research instructions."""

    def test_has_schema_summary_placeholder(self) -> None:
        """The schema placeholder make_researcher_spec depends on exists."""
        assert "{schema_summary}" in RESEARCHER_SYSTEM

    def test_replace_leaves_no_placeholder_behind(self) -> None:
        """Substitution of the larger schema payload actually lands."""
        filled = RESEARCHER_SYSTEM.replace("{schema_summary}", "Entities: Person")
        assert "{schema_summary}" not in filled
        assert "Entities: Person" in filled

    def test_carries_citation_and_feedback_instructions(self) -> None:
        """Citation keys and missing-evidence feedback framing survive."""
        assert "citation keys" in RESEARCHER_SYSTEM
        assert "feedback" in RESEARCHER_SYSTEM


class TestVerifierSystem:
    """VERIFIER_SYSTEM carries the factored checking instructions."""

    def test_checks_each_sub_question_independently(self) -> None:
        """The factored instruction is present."""
        assert "independently" in VERIFIER_SYSTEM

    def test_names_all_three_verdicts(self) -> None:
        """Every VerificationResult status is described."""
        assert "PASS" in VERIFIER_SYSTEM
        assert "INSUFFICIENT" in VERIFIER_SYSTEM
        assert "CONTRADICTORY" in VERIFIER_SYSTEM

    def test_reasoning_before_verdict(self) -> None:
        """The verifier checks first and decides after."""
        assert "reasoning first" in VERIFIER_SYSTEM
