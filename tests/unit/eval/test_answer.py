"""Tests for the answer-quality builders and the citation accuracy metric.

The judge is scripted: it scores a sentence 10 when the prompt holds the words
"supported claim" and 0 otherwise, and counts the scoring calls. DeepEval's own
scoring is not under test. These tests cover how agrag reads the answer,
splits it into sentences, finds citation keys and combines the results.
"""

from typing import Any
from uuid import uuid4

import pytest
from deepeval.models import DeepEvalBaseLLM
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from agrag.agents.ledger import Ledger
from agrag.agents.result import AgentRunResult
from agrag.common.data_models.query_value import QueryValue
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.search_result import SearchResult
from agrag.eval.answer import (
    CitationAccuracyMetric,
    answer_case,
    final_answer,
)


class _ScriptedJudge(DeepEvalBaseLLM):
    """Judge that scores by keyword and counts scoring calls."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.scoring_calls = 0
        self.scoring_prompts: list[str] = []
        self._fail_on = fail_on
        super().__init__("scripted")

    def load_model(self) -> Any:
        return None

    def get_model_name(self) -> str:
        return "scripted"

    def generate(self, prompt: str, schema: type[BaseModel] | None = None) -> Any:
        if schema is None:
            return ""
        if "steps" in schema.model_fields:
            return schema.model_validate(
                {"steps": ["Compare the output with the context."]}
            )
        self.scoring_calls += 1
        self.scoring_prompts.append(prompt)
        if self._fail_on and self._fail_on in prompt:
            raise RuntimeError("judge failed")
        score = 10 if "supported claim" in prompt else 0
        return schema.model_validate({"reason": "scripted", "score": score})

    async def a_generate(
        self, prompt: str, schema: type[BaseModel] | None = None
    ) -> Any:
        return self.generate(prompt, schema)


def _result(answer: str) -> AgentRunResult:
    """Build a run whose ledger holds one entity (E1) and one value (V1)."""
    ledger = Ledger()
    ledger.render(
        SearchResult(
            item=ResolvedEntity(id=uuid4(), label="Company", name="Acme"),
            score=1.0,
            method="entity",
        )
    )
    ledger.render(SearchResult(item=QueryValue(value=94), score=1.0, method="cypher"))
    return {
        "messages": [{"role": "assistant", "content": answer}],
        "ledger": ledger,
    }


def _run(messages: list[Any]) -> AgentRunResult:
    """Build a run with the given messages and an empty ledger."""
    return {"messages": messages, "ledger": Ledger()}


async def _score(answer: str, judge: _ScriptedJudge | None = None) -> Any:
    """Score ``answer`` and return the metric."""
    metric = CitationAccuracyMetric(judge or _ScriptedJudge())
    await metric.a_measure(answer_case("q", _result(answer), "reference"))
    return metric


class TestFinalAnswer:
    """final_answer reads the last assistant message in every message form."""

    def test_reads_a_dict_message(self) -> None:
        """A message dict gives its content."""
        result = _run([{"role": "assistant", "content": "Done."}])

        assert final_answer(result) == "Done."

    def test_reads_a_message_object_after_a_user_turn(self) -> None:
        """The last AI message wins over earlier and later non-AI messages."""
        result = _run(
            [
                HumanMessage("q"),
                AIMessage("first"),
                AIMessage("second"),
                HumanMessage("thanks"),
            ]
        )

        assert final_answer(result) == "second"

    def test_joins_the_text_blocks_of_block_content(self) -> None:
        """Text blocks join and other block types drop out."""
        blocks: list[str | dict[Any, Any]] = [
            {"type": "text", "text": "Net income "},
            {"type": "tool_use", "id": "x", "name": "n", "input": {}},
            {"type": "text", "text": "rose."},
        ]
        result = _run([AIMessage(content=blocks)])

        assert final_answer(result) == "Net income rose."

    def test_raises_without_an_assistant_message(self) -> None:
        """A run with no assistant message is an error, not an empty answer."""
        with pytest.raises(ValueError, match="no assistant message"):
            final_answer(_run([HumanMessage("q")]))


class TestAnswerCase:
    """answer_case carries the question, reference and the evidence the agent saw."""

    def test_puts_rendered_evidence_in_key_order(self) -> None:
        """retrieval_context is the ledger's rendered text, in key order."""
        case = answer_case("What?", _result("Acme [E1]."), "Acme.")

        assert case.input == "What?"
        assert case.expected_output == "Acme."
        assert case.actual_output == "Acme [E1]."
        assert case.retrieval_context == [
            "[E1] Entity: Acme (Company)",
            "[V1] Value: 94",
        ]
        assert case.metadata == {
            "citations": {
                "E1": "[E1] Entity: Acme (Company)",
                "V1": "[V1] Value: 94",
            }
        }


class TestCitationAccuracyMetric:
    """The metric scores each cited sentence and combines precision and recall."""

    async def test_judge_checks_claims_and_relationships_against_evidence(self) -> None:
        """The judge gets instructions to check claims, not just entity mentions."""
        judge = _ScriptedJudge()
        await _score("Acme founded in 1994 [E1].", judge)

        assert len(judge.scoring_prompts) == 1
        assert "claims and relationships" in judge.scoring_prompts[0]
        assert "entities or figures appear individually" in judge.scoring_prompts[0]

    @pytest.mark.parametrize(
        "answer",
        [
            "This is a supported claim [E1].",
            "This is a supported claim (E1).",
            "This is a supported claim E1.",
            "This is a supported claim [E1, V1].",
        ],
    )
    async def test_reads_every_key_style(self, answer: str) -> None:
        """Bracket, parenthesis, bare and grouped keys all count as citations."""
        metric = await _score(answer)

        assert metric.score_breakdown["cited_sentences"] == 1
        assert metric.score == 1.0

    @pytest.mark.parametrize(
        "answer", ["This is a supported claim Q1 H1.", "Sales Q1."]
    )
    async def test_ignores_tokens_that_are_not_keys(self, answer: str) -> None:
        """Q1 and H1 are not key prefixes, so the answer has no citation."""
        metric = await _score(answer)

        assert metric.score == 0.0
        assert metric.reason == "The answer has no citations."

    async def test_fabricated_key_is_unsupported_without_a_judge_call(self) -> None:
        """A bracketed key the ledger never assigned costs no judge call."""
        judge = _ScriptedJudge()

        metric = await _score("This is a supported claim [E9].", judge)

        assert judge.scoring_calls == 0
        assert metric.score == 0.0
        assert metric.score_breakdown["citation_precision"] == 0.0

    async def test_fabricated_key_and_supported_sentence_give_half_precision(
        self,
    ) -> None:
        """One fabricated and one supported cited sentence give precision 0.5."""
        answer = "This is a supported claim [E1]. This is a supported claim [E9]."

        metric = await _score(answer)

        assert metric.score_breakdown["citation_precision"] == 0.5
        assert metric.score_breakdown["citation_recall"] == 0.5
        assert metric.score == 0.5

    async def test_unsupported_sentence_lowers_precision(self) -> None:
        """The judge decides support from the cited evidence."""
        answer = "This is a supported claim [E1]. This is an invented claim [V1]."

        metric = await _score(answer)

        assert metric.score_breakdown["supported_sentences"] == 1
        assert metric.score_breakdown["citation_precision"] == 0.5

    async def test_uncited_long_sentences_lower_recall_and_short_ones_do_not(
        self,
    ) -> None:
        """Only uncited sentences of four words or more count against recall."""
        answer = (
            "This is a supported claim [E1]. "
            "Revenue also rose in the following year. "
            "See below."
        )

        metric = await _score(answer)

        assert metric.score_breakdown["citation_precision"] == 1.0
        assert metric.score_breakdown["citation_recall"] == 0.5
        assert metric.score_breakdown["sentences"] == 2

    async def test_does_not_split_after_abbreviations_or_inside_numbers(self) -> None:
        """U.S., Inc. and $6.7 billion stay inside one sentence."""
        answer = (
            "The U.S. Treasury bought Inc. Bonds worth $6.7 billion [E1]. "
            "This is a supported claim [V1]."
        )

        metric = await _score(answer)

        assert metric.score_breakdown["cited_sentences"] == 2
        assert metric.score_breakdown["sentences"] == 2

    async def test_splits_bullet_lines_into_sentences(self) -> None:
        """Each bullet line is its own sentence."""
        answer = "- This is a supported claim [E1]\n- This is an invented claim [V1]"

        metric = await _score(answer)

        assert metric.score_breakdown["cited_sentences"] == 2
        assert metric.score_breakdown["citation_precision"] == 0.5

    async def test_scores_zero_without_citations(self) -> None:
        """An answer with no citation key scores 0 and says why."""
        metric = await _score("Net income rose by ninety four million dollars.")

        assert metric.score == 0.0
        assert metric.reason == "The answer has no citations."
        assert not metric.success

    async def test_skips_an_abstention(self) -> None:
        """The exact abstention text scores 1 with no judge call."""
        judge = _ScriptedJudge()

        metric = await _score("No relevant evidence found.", judge)

        assert metric.score == 1.0
        assert metric.reason == "The agent abstained."
        assert judge.scoring_calls == 0

    async def test_judge_failure_raises(self) -> None:
        """A judge error is not scored as support."""
        judge = _ScriptedJudge(fail_on="supported claim")

        with pytest.raises(RuntimeError, match="judge failed"):
            await _score("This is a supported claim [E1].", judge)

    def test_measure_matches_a_measure(self) -> None:
        """The synchronous path gives the same score."""
        metric = CitationAccuracyMetric(_ScriptedJudge())
        case = answer_case(
            "q",
            _result("This is a supported claim [E1]. This is an invented claim [V1]."),
            "reference",
        )

        assert metric.measure(case) == 0.5
