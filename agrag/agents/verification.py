"""The verifier subagent's structured verdict."""

from collections.abc import Sequence
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agrag.agents.prompts import VERIFIER_SYSTEM


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


async def verify_findings(
    model: Any,
    question: str,
    sub_questions: Sequence[str],
    findings: str,
) -> VerificationResult:
    """Run the verifier on fixed inputs and return its structured verdict.

    Reproduces what the verifier subagent does: ``VERIFIER_SYSTEM`` as the system
    prompt, one user message, and ``VerificationResult`` as structured output.
    It calibrates the verifier prompt and model on a fixed input format. It does
    not test the text the planner writes when it delegates to the verifier.

    Args:
        model: A LangChain chat model.
        question: The original question.
        sub_questions: The sub-questions the question was split into.
        findings: The researcher's findings with citation keys such as ``E1``.

    Returns:
        The verifier's verdict.

    Raises:
        ValueError: The model returned no verdict.
    """
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(sub_questions, 1))
    message = (
        f"Original question:\n{question}\n\n"
        f"Sub-questions:\n{numbered}\n\n"
        f"Researcher findings:\n{findings}"
    )
    structured = model.with_structured_output(
        VerificationResult, method="function_calling"
    )
    result = await structured.ainvoke(
        [SystemMessage(content=VERIFIER_SYSTEM), HumanMessage(content=message)]
    )
    if result is None:
        raise ValueError("the model returned no verdict")
    return VerificationResult.model_validate(result)
