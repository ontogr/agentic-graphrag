"""Models for theme search over detected communities.

A theme is a community of related entities found by the last community
detection run. A hit carries the community id, the passages in the caller's
scope that mention its member entities, and the names of those members.
Community report text (title, summary, findings) is never returned: community
nodes carry no document scope, so their text may reflect documents outside the
caller's scope.
"""

from pydantic import BaseModel, Field

from agrag.common.data_models.entity_search import SupportingPassage
from agrag.common.data_models.evidence import (
    EvidenceSearchStatus,
    IndexState,
    LegFailure,
)


class ThemeHit(BaseModel):
    """One theme found by theme search.

    Attributes:
        theme_id: The id of the community node.
        score: The vector similarity of the query to the community report
            embedding. An ordering value. Higher scores rank first. It is not a
            confidence, and it is not a probability that the theme is relevant.
        entities: Up to five names of member entities that a visible in-scope
            passage mentions.
        passages: Visible in-scope passages that mention member entities, best
            first. Each passage is an evidence id. Fetch it to read the text.
    """

    theme_id: str
    score: float
    entities: list[str] = Field(default_factory=list)
    passages: list[SupportingPassage] = Field(default_factory=list)


class ThemeResult(BaseModel):
    """The result of one theme search call.

    Attributes:
        status: The overall outcome. A failed leg never shows as NO_MATCH.
        themes: The themes, best first.
        truncated: True when fewer than ``limit`` themes remained and the vector
            read filled its candidate window, so more themes may exist.
        index_state: Whether the needed index was ready. None when no index was
            checked.
        failures: The legs that failed. Empty when every leg ran.
    """

    status: EvidenceSearchStatus
    themes: list[ThemeHit] = Field(default_factory=list)
    truncated: bool = False
    index_state: IndexState | None = None
    failures: list[LegFailure] = Field(default_factory=list)
