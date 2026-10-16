"""Structured final answer produced by the default evidence agent."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentAnswer(BaseModel):
    """A final answer with an explicit evidence-support assessment."""

    model_config = ConfigDict(frozen=True)

    answer: str
    support_status: Literal["supported", "insufficient_evidence"]
    citations: list[str] = Field(default_factory=list)
