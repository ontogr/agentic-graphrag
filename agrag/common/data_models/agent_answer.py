"""Structured final answer produced by the default evidence agent."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentAnswer(BaseModel):
    """A final answer with an explicit evidence-support assessment."""

    model_config = ConfigDict(frozen=True)

    answer: str = Field(
        description=(
            "Final answer text. Cite fetched evidence inline in square brackets "
            "immediately after each supported claim, using its full evidence id "
            "(for example [ev1:c:...])."
        )
    )
    support_status: Literal["supported", "insufficient_evidence"]
    citations: list[str] = Field(
        default_factory=list,
        description=(
            "Evidence ids cited inline in answer. This list does not replace "
            "the inline citations that connect each claim to its evidence."
        ),
    )
