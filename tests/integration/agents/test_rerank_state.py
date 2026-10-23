"""Integration tests for the agent run state under a failing rerank stage.

A slow or crashed reranker must not mark an agent run as a partial retrieval,
because the hit set is complete; only the order changed.
"""

import asyncio
from collections.abc import Sequence
from uuid import uuid4

from agrag.agents.middleware import RunState
from agrag.agents.tools.core import make_core_tools
from agrag.chunking import Chunker
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.decisions import DecisionTraces
from agrag.evidence.rerank import Reranker
from agrag.history import ConversationHistory
from agrag.ingestion.graph import Graph
from agrag.retrieval.settings import RetrievalSettings
from tests.integration._backend import await_indexes, build_test_store
from tests.integration.retrieval.evidence._corpus import (
    HARBOR_TEXT,
    BagOfWordsEmbedder,
    NoEntityExtractor,
    make_document,
)


_QUERY = "lighthouse crew repairs"
_TIMEOUT_SETTINGS = RetrievalSettings(rerank_timeout_seconds=0.05)


class _SlowReranker:
    """Reranker that takes longer than the configured rerank timeout."""

    async def __call__(self, query: str, texts: Sequence[str]) -> list[float]:
        """Sleep, then return scores that are never used."""
        await asyncio.sleep(2)
        return [1.0 for _ in texts]


async def _tools_with_state(
    store, harbor_key: str, reranker: Reranker | None
) -> tuple[dict[str, object], RunState]:
    """Build the core tools over one harbor document and return them by name."""
    history = ConversationHistory(store, project_id="rerank-state", agent_id="test")
    decisions = DecisionTraces(store, project_id="rerank-state", agent_id="test")
    tools, run_state = make_core_tools(
        graph_store=store,
        embedder=BagOfWordsEmbedder(),
        scope=frozenset({harbor_key}),
        task_name=f"rerank-{uuid4().hex}",
        history=history,
        decisions=decisions,
        fetched_ids=[],
        fetched_outcomes=[],
        max_chars=12_000,
        max_tool_calls=30,
        retrieval_settings=_TIMEOUT_SETTINGS,
        reranker=reranker,
        timeout=30.0,
    )
    return {tool.name: tool for tool in tools}, run_state


async def test_slow_reranker_does_not_flag_partial_retrieval() -> None:
    """A rerank timeout keeps the run state clean when the search is ok."""
    store = build_test_store()
    graph = await Graph.open(
        schema=GraphSchema(name="rerank-state", version="1", entities=[], relations=[]),
        graph_store=store,
        embedder=BagOfWordsEmbedder(),
        extractor=NoEntityExtractor(),
        chunker=Chunker(size=60),
    )
    run = uuid4().hex
    harbor_key = f"evidence://{run}/harbor"
    await await_indexes(store)
    await graph.add(documents=[make_document(harbor_key, HARBOR_TEXT)])
    try:
        tools, run_state = await _tools_with_state(store, harbor_key, _SlowReranker())

        await tools["search_evidence"].ainvoke({"query": _QUERY})

        assert run_state.retrieval_failed is False
    finally:
        await store.close()
