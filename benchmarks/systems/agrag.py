"""agrag as a system under test."""

import importlib.util
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from langgraph.errors import GraphRecursionError
from opentelemetry.trace import Tracer

from agrag.agents.build import build_agent
from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.chunking import Chunker
from agrag.common.data_models.document import Document
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.embedding.sentence_transformers import SentenceTransformerEmbedder
from agrag.embedding.settings import EmbeddingSettings
from agrag.eval import ChatModelJudge, EvalJudgeSettings
from agrag.graphdb import GraphStore
from agrag.ingestion import ExtractionSettings, Graph
from agrag.ingestion.extract import BAMLExtractor, ExtractionLLMSettings
from agrag.ingestion.resolve.zone_classifier import MAX_LLM_PAIRS
from benchmarks.harness.config import RunLimits
from benchmarks.models import BenchmarkQuestion
from benchmarks.systems.base import AgentFailureError, CitedChunk, SystemAnswer


@dataclass(frozen=True)
class AgragSettings:
    """The model settings of a run, resolved from the environment once.

    Attributes:
        extraction: The extractor's client config.
        agent: The agent's client config.
        judge: The judge's client config.
        agent_loop: The agent loop limits.
        max_llm_pairs: The most entity pairs per label that resolution sends to
            the LLM.
    """

    extraction: ExtractionLLMSettings
    agent: AgentLLMSettings
    judge: EvalJudgeSettings
    agent_loop: AgentSettings
    max_llm_pairs: int = MAX_LLM_PAIRS

    def make_judge(self, tracer: Tracer) -> ChatModelJudge:
        """Build the judge around the run's tracer."""
        return ChatModelJudge.from_settings(self.judge, tracer=tracer)

    @classmethod
    def from_env(cls, limits: RunLimits | None = None) -> "AgragSettings":
        """Read every role's settings. The judge and agent fall back to ``LLM_*``.

        Args:
            limits: Limits that replace the defaults of resolution and the agent.
        """
        extra: dict[str, int] = {}
        loop = AgentSettings()
        if limits is not None:
            extra = {"max_llm_pairs": limits.max_llm_pairs}
            loop = AgentSettings(
                recursion_limit=limits.recursion_limit,
            )
        return cls(
            extraction=ExtractionLLMSettings.from_openai_compatible_env(),
            agent=AgentLLMSettings.from_openai_compatible_env(),
            judge=EvalJudgeSettings.from_openai_compatible_env(),
            agent_loop=loop,
            **extra,
        )


def require_deepagents() -> None:
    """Raise when ``deepagents`` is missing.

    The fallback agent reads only the last message, so a multi-turn question would
    be answered without its context.
    """
    if importlib.util.find_spec("deepagents") is None:
        raise RuntimeError(
            "the benchmark harness needs deepagents: "
            "install the 'agents' extra (make sync)"
        )


class AgragSystem:
    """Ingests a corpus into one graph store and answers with the agrag agent.

    Attributes:
        name: ``agrag``.
    """

    name = "agrag"

    def __init__(
        self,
        *,
        store: GraphStore,
        schema: GraphSchema,
        chunking: Chunker,
        documents: Sequence[Document],
        settings: AgragSettings,
        tracer: Tracer,
        embedder: SentenceTransformerEmbedder | None = None,
    ) -> None:
        """Build the system over a store that holds exactly one corpus.

        Args:
            store: The graph store of the corpus's own Neo4j service. The store
                carries the tracer.
            schema: The graph schema of the corpus.
            chunking: The chunker for every document.
            documents: The corpus documents. Their uris name the documents of
                cited chunks.
            settings: The resolved model settings.
            tracer: The tracer for every agrag component.
            embedder: The embedder, or None for the default local model.
        """
        require_deepagents()
        self._store = store
        self._schema = schema
        self._chunking = chunking
        self._settings = settings
        self._tracer = tracer
        self._embedder = embedder or SentenceTransformerEmbedder(tracer=tracer)
        self._documents = list(documents)
        self._uri_by_document_id: dict[UUID, str] = {
            Document.node_id_for(document_key=d.resolved_document_key): d.uri
            for d in self._documents
        }

    @staticmethod
    def default_embedder_model() -> str:
        """Return the embedder model id that a run without overrides uses."""
        return EmbeddingSettings().model

    async def ingest(self) -> None:
        """Extract and store the documents, then resolve entities."""
        graph = await Graph.open(
            schema=self._schema,
            graph_store=self._store,
            embedder=self._embedder,
            extraction_settings=ExtractionSettings(mode="llm"),
            llm_extractor=BAMLExtractor(
                settings=self._settings.extraction, tracer=self._tracer
            ),
            tracer=self._tracer,
            chunker=self._chunking,
            max_llm_pairs=self._settings.max_llm_pairs,
        )
        await graph.add(documents=self._documents)

    async def answer(self, question: BenchmarkQuestion) -> SystemAnswer:
        """Answer with a fresh agent, passing the whole conversation.

        Raises:
            AgentFailureError: The agent hit its recursion limit or gave no answer.
        """
        agent = build_agent(
            graph_store=self._store,
            embedder=self._embedder,
            scope=frozenset(d.resolved_document_key for d in self._documents),
            project_id=question.corpus_id,
            agent_id="benchmark-agent",
            llm_settings=self._settings.agent,
            agent_settings=self._settings.agent_loop,
            tracer=self._tracer,
        )
        try:
            result = await agent.ainvoke(
                {"task_name": question.id, "question": question.query}
            )
            text = result["answer"]
        except (GraphRecursionError, ValueError) as error:
            raise AgentFailureError(str(error)) from error
        if result["status"] in {"budget_exhausted", "recording_failed"}:
            raise AgentFailureError(result["status"])
        if not text.strip():
            raise AgentFailureError("empty answer")
        return self._with_citations(text, result)

    def _with_citations(self, text: str, result: dict) -> SystemAnswer:
        """Map validated evidence spans to benchmark source locations."""
        chunks: list[CitedChunk] = []
        for citation in result["citations"]:
            reference = citation.reference
            if reference is None:
                continue
            document_id = reference.document_node_id
            chunks.append(
                CitedChunk(
                    uri=self._uri_by_document_id.get(document_id, str(document_id)),
                    char_start=reference.char_start,
                    char_end=reference.char_end,
                )
            )
        return SystemAnswer(
            text=text,
            cited_chunks=chunks,
            non_chunk_citations=0,
            source_chunks=[],
            raw=result,
        )

    async def teardown(self) -> None:
        """Close the graph store."""
        await self._store.close()
