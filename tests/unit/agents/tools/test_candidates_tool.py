"""Candidate-tool output keeps unreviewed records distinct from graph evidence."""

from uuid import uuid4

from agrag.agents.tools.candidates import make_search_candidates_tool
from agrag.common.data_models.candidate import CandidateKind, CandidateRecord


class _CandidateSearch:
    """Supply fixed records through the public engine method shape."""

    def __init__(self, records: list[CandidateRecord]) -> None:
        self.records = records

    async def search_candidates(
        self, query: str, *, kind: CandidateKind | None = None, limit: int = 10
    ) -> list[CandidateRecord]:
        return self.records[:limit]


class TestSearchCandidatesTool:
    """Tool results identify candidates as unreviewed and never as citations."""

    async def test_marks_each_candidate_unreviewed(self) -> None:
        """Candidate output carries a warning in its header and every row."""
        record = CandidateRecord(
            kind="relation",
            label="WORKS_FOR",
            text="",
            source_text="Ada",
            target_text="Acme",
            confidence=0.6,
            reason="off_pattern",
            chunk_id=uuid4(),
            count=3,
        )
        tool = make_search_candidates_tool(_CandidateSearch([record]))

        response = await tool.ainvoke({"query": "Ada Acme"})

        lines = response.splitlines()
        assert "not checked by a person" in lines[0]
        assert lines[1].startswith("unreviewed relation WORKS_FOR")
        assert "Ada -> Acme" in lines[1]
        assert "seen 3 times" in lines[1]

    async def test_reports_when_no_candidate_matches(self) -> None:
        """An empty result does not imply graph evidence."""
        tool = make_search_candidates_tool(_CandidateSearch([]))

        assert await tool.ainvoke({"query": "unknown"}) == (
            "No unreviewed candidates match."
        )
