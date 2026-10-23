"""Smoke tests for evaluation corpus readiness and model scoring.

Check hybrid search and evidence fetch without an LLM before model scoring.
Runs the real agent over the tiny corpus and scores its answer with a
``GEval`` from the real judge. It checks that the pieces connect,
not the answer quality: the score only has to fall in ``[0, 1]``. The judge
and the agent model ids print to the log so a run shows what graded what.
"""

from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from agrag.agents.settings import AgentLLMSettings
from agrag.common.data_models.evidence import (
    EvidenceSearchMode,
    EvidenceSearchStatus,
    FetchStatus,
)
from agrag.eval.judge import ChatModelJudge
from agrag.evidence import fetch_evidence, search_evidence
from tests.integration.eval.conftest import AnswerQualityGraph, TinyCorpus


QUESTION = "Who designed the Lumen-9 lifting arm at Zephyra Robotics?"
EXPECTED = "Tobias Renn designed the Lumen-9 lifting arm."


async def test_tiny_corpus_has_searchable_and_fetchable_evidence(
    tiny_corpus: TinyCorpus,
) -> None:
    """The trajectory fixture supports hybrid search before an agent starts."""
    found = await search_evidence(
        tiny_corpus.store,
        tiny_corpus.embedder,
        "Tobias Renn",
        mode=EvidenceSearchMode.HYBRID,
        limit=5,
        scope=tiny_corpus.scope,
    )
    assert found.status is EvidenceSearchStatus.OK
    assert found.hits
    fetched = await fetch_evidence(
        tiny_corpus.store,
        [found.hits[0].evidence_id],
        scope=tiny_corpus.scope,
        max_chars=10_000,
    )
    assert fetched.outcomes[0].status is FetchStatus.OK
    assert fetched.outcomes[0].text is not None
    assert "Tobias Renn" in fetched.outcomes[0].text


async def test_answer_quality_graph_has_searchable_and_fetchable_evidence(
    answer_quality_graph: AnswerQualityGraph,
) -> None:
    """The answer fixture supports hybrid search before an agent starts."""
    found = await search_evidence(
        answer_quality_graph.store,
        answer_quality_graph.embedder,
        "foreign currency",
        mode=EvidenceSearchMode.HYBRID,
        limit=5,
        scope=answer_quality_graph.scope,
    )
    assert found.status is EvidenceSearchStatus.OK
    assert found.hits
    fetched = await fetch_evidence(
        answer_quality_graph.store,
        [found.hits[0].evidence_id],
        scope=answer_quality_graph.scope,
        max_chars=10_000,
    )
    assert fetched.outcomes[0].status is FetchStatus.OK
    assert fetched.outcomes[0].text is not None
    assert "foreign currency" in fetched.outcomes[0].text.lower()


async def test_agent_answer_scores_in_unit_range(
    judge: ChatModelJudge,
    agent_factory: Callable[[], Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A real agent answer gets a GEval score between 0 and 1."""
    agent = agent_factory()
    result = await agent.ainvoke(
        {"task_name": f"harness-{uuid4().hex[:8]}", "question": QUESTION}
    )
    metric = GEval(
        name="Correctness",
        criteria=(
            "Check whether the actual output states the same fact as the "
            "expected output. Penalize contradictions and missing facts."
        ),
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=judge,
        async_mode=False,
    )

    await metric.a_measure(
        LLMTestCase(
            input=QUESTION,
            actual_output=result["answer"],
            expected_output=EXPECTED,
        )
    )

    with capsys.disabled():
        agent_model = AgentLLMSettings.from_openai_compatible_env().clients[0].model
        print(f"\nagent model: {agent_model}")
        print(f"judge model: {judge.get_model_name()}")
        print(f"eval score: {metric.score}")
    assert metric.score is not None
    assert 0.0 <= metric.score <= 1.0
