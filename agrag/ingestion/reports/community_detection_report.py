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
        failures: Failures embedding an applied community's report text.
            Always empty when apply is False.
    """

    communities: list[Community] = Field(default_factory=list)
    applied: bool = False
    failures: list[StageFailure] = Field(default_factory=list)
