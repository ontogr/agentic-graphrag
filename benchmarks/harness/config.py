"""Cost constants and spend caps.

The per-chunk and per-question figures come from a measurement run on the
configured model. Until they are set, ``dry-run`` and ``run`` refuse to start
instead of guessing. Each domain adds its caps next to its dataset, at 1.5 times
its dry-run bound.
"""

from dataclasses import dataclass

from agrag.chunking import Chunking, RecursiveChunker


@dataclass(frozen=True)
class CostModel:
    """Measured cost of the calls a run makes.

    Attributes:
        calls_per_chunk: LLM calls that ingest one chunk, including the share of
            resolution, merge and community calls (p95).
        tokens_per_chunk: Tokens that ingest one chunk (p95).
        agent_calls_per_question: An estimate of the agent calls for one question.
        agent_tokens_per_question: An estimate of the agent tokens for one question.
        judge_tokens_per_call: An estimate of the tokens of one judge call.
    """

    calls_per_chunk: float
    tokens_per_chunk: int
    agent_calls_per_question: int
    agent_tokens_per_question: int
    judge_tokens_per_call: int


@dataclass(frozen=True)
class SpendCap:
    """The most calls and tokens that the estimate of a run may reach."""

    llm_calls: int
    tokens: int


# Measured on the Legal lite corpus (23 chunks) with the benchmark chunking.
# Extraction takes one call per chunk, and resolution, merge and community calls make
# up most of the rest. Agent figures come from two Legal questions that made 12 and
# 45 calls and used about 136k tokens each on average, counting the calls that tools
# make inside the agent run. Resolution cost can grow faster than the chunk count, so
# measure a larger corpus before you trust a bound for one.
COST_MODEL: CostModel | None = CostModel(
    calls_per_chunk=7,
    tokens_per_chunk=105_000,
    agent_calls_per_question=60,
    agent_tokens_per_question=250_000,
    judge_tokens_per_call=2_000,
)

SPEND_CAPS: dict[tuple[str, str], SpendCap] = {
    ("legal", "lite"): SpendCap(llm_calls=1_200, tokens=7_500_000),
    ("legal", "full"): SpendCap(llm_calls=12_100, tokens=81_000_000),
    ("financial", "lite"): SpendCap(llm_calls=4_000, tokens=47_100_000),
    ("financial", "full"): SpendCap(llm_calls=16_000, tokens=170_000_000),
}

# About 1000 tokens per chunk, counted with the tokenizer agrag uses elsewhere.
BENCH_CHUNKING = Chunking(
    fallback=RecursiveChunker(tokenizer="o200k_base", chunk_size=1000)
)
