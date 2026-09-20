"""The verifier subagent's structured verdict."""

from typing import Literal

from pydantic import BaseModel, Field


class VerificationResult(BaseModel):
    """The verifier's structured verdict on the researcher's findings.

    The verifier returns this through its ``response_format``, so the
    planner reads a typed verdict out of the task tool's result instead
    of parsing free-form prose.

    Attributes:
        reasoning: What the independent per-sub-question checks found,
            written before the verdict is decided.
        status: The overall verdict. ``PASS`` means every sub-question
            has supporting evidence and nothing contradicts; a re-delegation
            after this verdict is not a retry. ``INSUFFICIENT`` means one
            or more sub-questions lack supporting evidence, listed in
            ``missing_evidence``. ``CONTRADICTORY`` means cited evidence
            conflicts, which re-researching cannot resolve.
        missing_evidence: The sub-questions and evidence gaps to close,
            filled when the status is ``INSUFFICIENT``.
    """

    reasoning: str
    status: Literal["PASS", "INSUFFICIENT", "CONTRADICTORY"]
    missing_evidence: list[str] = Field(default_factory=list)
