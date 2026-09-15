"""Graph.detect_communities()'s result type."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agrag.common.data_models.community import Community
from agrag.ingestion.stats import StageFailure


class CommunityDetectionReport(BaseModel):
    """Report from Graph.detect_communities().

    Attributes:
        communities: The communities this call found, whether applied or not.
        applied: Whether the communities were written.
        failures: Failures generating an applied community's LLM report or
            embedding its report text. A failed community still gets
            written, with a heuristic report or a missing embedding in
            place of the failed step. Always empty when apply is False.
    """

    communities: list[Community] = Field(default_factory=list)
    applied: bool = False
    failures: list[StageFailure] = Field(default_factory=list)
