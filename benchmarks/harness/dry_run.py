"""The dry run: an upper bound on calls and tokens, and the spend cap check."""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agrag.chunking import Chunking
from agrag.common.data_models.document import Document
from benchmarks.harness.config import SPEND_CAPS, CostModel, SpendCap
from benchmarks.harness.record import SpendCapRecord
from benchmarks.models import CorpusManifest


class SpendCapError(Exception):
    """The run has no spend cap, or its bound is above the cap."""


@dataclass(frozen=True)
class DryRun:
    """An upper bound for one run.

    Attributes:
        chunks: The chunk count of each corpus.
        llm_calls: The bound on LLM calls for ingest, answers and grading.
        tokens: The bound on tokens for the same.
    """

    chunks: dict[str, int]
    llm_calls: int
    tokens: int


def count_chunks(documents: Sequence[Document], chunking: Chunking) -> int:
    """Count the chunks ingest would make, without a model."""
    return sum(len(chunking.select(doc)[1].chunk(doc)) for doc in documents)


def dry_run(
    manifest: CorpusManifest,
    documents: Mapping[str, Sequence[Document]],
    *,
    chunking: Chunking,
    cost: CostModel,
    judge_calls_per_question: int,
) -> DryRun:
    """Bound the calls and tokens of a run from chunk counts and question counts.

    Ingest cost follows the chunk count, not the question count, so the bound
    counts chunks.

    Args:
        manifest: The manifest of the run.
        documents: The documents of each corpus, by corpus id.
        chunking: The chunking the run uses.
        cost: The measured cost model.
        judge_calls_per_question: The judge calls one question needs.
    """
    chunks = {c.id: count_chunks(documents[c.id], chunking) for c in manifest.corpora}
    total_chunks = sum(chunks.values())
    n_questions = len(manifest.questions)
    calls = math.ceil(total_chunks * cost.calls_per_chunk) + n_questions * (
        cost.agent_calls_per_question + judge_calls_per_question
    )
    tokens = total_chunks * cost.tokens_per_chunk + n_questions * (
        cost.agent_tokens_per_question
        + judge_calls_per_question * cost.judge_tokens_per_call
    )
    return DryRun(chunks=chunks, llm_calls=calls, tokens=tokens)


def check_cap(
    bound: DryRun,
    domain: str,
    mode: str,
    *,
    max_llm_calls: int | None = None,
    max_tokens: int | None = None,
) -> SpendCapRecord:
    """Check a bound against the cap of its domain and mode.

    The flags replace the cap for one run. The record states that they did.

    Raises:
        SpendCapError: No cap exists for the domain and mode and the flags do not
            give one, or the bound is above the cap.
    """
    base: SpendCap | None = SPEND_CAPS.get((domain, mode))
    llm_calls = max_llm_calls
    tokens = max_tokens
    if base is not None:
        llm_calls = base.llm_calls if llm_calls is None else llm_calls
        tokens = base.tokens if tokens is None else tokens
    if llm_calls is None or tokens is None:
        raise SpendCapError(
            f"no spend cap for {domain} {mode}: add one to SPEND_CAPS or pass "
            "--max-llm-calls and --max-tokens"
        )
    if bound.llm_calls > llm_calls or bound.tokens > tokens:
        raise SpendCapError(
            f"bound of {bound.llm_calls} calls and {bound.tokens} tokens is above "
            f"the cap of {llm_calls} calls and {tokens} tokens"
        )
    return SpendCapRecord(
        llm_calls=llm_calls,
        tokens=tokens,
        overridden=max_llm_calls is not None or max_tokens is not None,
    )
