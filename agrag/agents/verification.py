"""The verifier subagent's structured verdict."""

from collections.abc import Sequence
from typing import Any, Literal

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, Field

from agrag.agents.prompts import VERIFIER_SYSTEM


# LangGraph steps one call may use. When the model answers without the verdict
# tool, the agent asks again, so this bounds the retries.
_MAX_STEPS = 6


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

    Runs the agent that the verifier subagent runs: ``VERIFIER_SYSTEM`` as the
    system prompt, one user message, and ``VerificationResult`` as the response
    format. The response format is handled as it is in a full run, so the model
    must answer through the verdict tool. This calibrates the verifier prompt and
    model on a fixed input format. It does not test the text the planner writes
    when it delegates to the verifier.

    Args:
        model: A LangChain chat model.
        question: The original question.
        sub_questions: The sub-questions the question was split into.
        findings: The researcher's findings with citation keys such as ``E1``,
            and the evidence text for each key.

    Returns:
        The verifier's verdict.

    Raises:
        ValueError: The model returned no verdict, after the agent asked again a
            few times.
    """
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(sub_questions, 1))
    message = (
        f"Original question:\n{question}\n\n"
        f"Sub-questions:\n{numbered}\n\n"
        f"Researcher findings:\n{findings}"
    )
    agent = create_agent(
        model, system_prompt=VERIFIER_SYSTEM, response_format=VerificationResult
    )
    try:
        state = await agent.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config={"recursion_limit": _MAX_STEPS},
        )
    except GraphRecursionError as error:
        raise ValueError("the verifier returned no verdict") from error
    result = state.get("structured_response")
    if result is None:
        raise ValueError("the verifier returned no verdict")
    return VerificationResult.model_validate(result)
