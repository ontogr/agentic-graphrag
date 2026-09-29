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
        agent_calls_per_question: An upper bound on the agent calls for one question.
        agent_tokens_per_question: An upper bound on the agent tokens for one question.
        judge_tokens_per_call: An upper bound on the tokens of one judge call.
    """

    calls_per_chunk: float
    tokens_per_chunk: int
    agent_calls_per_question: int
    agent_tokens_per_question: int
    judge_tokens_per_call: int


@dataclass(frozen=True)
class SpendCap:
    """The most calls and tokens a run of one domain and mode may need."""

    llm_calls: int
    tokens: int


COST_MODEL: CostModel | None = None

SPEND_CAPS: dict[tuple[str, str], SpendCap] = {}

# About 1000 tokens per chunk, counted with the tokenizer agrag uses elsewhere.
BENCH_CHUNKING = Chunking(
    fallback=RecursiveChunker(tokenizer="o200k_base", chunk_size=1000)
)
