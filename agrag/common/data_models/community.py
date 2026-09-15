"""The Community model: a Leiden-detected entity cluster with an LLM report."""

from uuid import UUID

from pydantic import Field

from agrag.common.data_models.data_point import DataPoint
from agrag.common.data_models.graph_record import NodeRecord


COMMUNITY_LABEL = "Community"
MEMBER_OF_RELATION = "MEMBER_OF"


class Community(DataPoint):
    """A cluster of entities detected by hierarchical Leiden, with an LLM report.

    Attributes:
        title: A short, human-readable name for the community.
        summary: A prose summary of what the community is about.
        rating: An importance rating for this community, 0-10.
        rating_explanation: One sentence explaining the rating.
        findings: Distinct factual claims the report supports.
        member_ids: Ids of every Entity in this community, ordered by
            internal weighted degree descending (see compute_communities) --
            the highest-centrality, most representative members first.
        internal_weight: Total weight of edges where both endpoints are
            members of this community. A free-to-compute (no extra query,
            no new dependency) importance signal, used in place of raw
            member count to decide which communities get a real LLM report
            -- a small but densely-attested community can matter more than
            a larger sparse one.
        embedding: The community's dense vector, computed from title and
            summary. None before the report/embedding stage runs.
    """

    title: str
    summary: str
    rating: float = Field(ge=0.0, le=10.0)
    rating_explanation: str
    findings: list[str] = Field(default_factory=list)
    member_ids: list[UUID] = Field(default_factory=list)
    internal_weight: float = 0.0
    embedding: list[float] | None = None

    @property
    def embedding_text(self) -> str:
        """Return the text this community's embedding is computed from."""
        return f"{self.title}: {self.summary}"

    def to_node_record(self) -> NodeRecord:
        """Return this community as a GraphStore write record."""
        properties: dict[str, object] = {
            "title": self.title,
            "summary": self.summary,
            "rating": self.rating,
            "rating_explanation": self.rating_explanation,
            "findings": self.findings,
            "member_ids": [str(m) for m in self.member_ids],
            "internal_weight": self.internal_weight,
            "created_at": self.created_at.isoformat(),
        }
        if self.embedding is not None:
            properties["embedding"] = self.embedding
        return NodeRecord(id=self.id, labels=[COMMUNITY_LABEL], properties=properties)
