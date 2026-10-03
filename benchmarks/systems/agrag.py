"""agrag as a system under test."""

import importlib.util
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from langgraph.errors import GraphRecursionError
from opentelemetry.trace import Tracer

from agrag.agents.build import build_agent
from agrag.agents.settings import AgentLLMSettings, AgentSettings
from agrag.chunking import Chunking
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.relation import Relation
from agrag.cypher.entities import load_chunks_by_id_query
from agrag.embedding.sentence_transformers import SentenceTransformerEmbedder
from agrag.embedding.settings import EmbeddingSettings
from agrag.eval import ChatModelJudge, EvalJudgeSettings, final_answer
from agrag.graphdb import GraphStore
from agrag.ingestion import Graph
from agrag.ingestion.extract import BAMLExtractor, ExtractionLLMSettings
from agrag.ingestion.resolve.zone_classifier import MAX_LLM_PAIRS
from agrag.retrieval.search_engine import SearchEngine
from benchmarks.harness.config import RunLimits
from benchmarks.models import BenchmarkQuestion
from benchmarks.systems.base import AgentFailureError, CitedChunk, SystemAnswer


_CITATION_KEY = re.compile(r"\b[EGRCVX]\d+\b")


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
                max_research_attempts=limits.max_research_attempts,
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
        chunking: Chunking,
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
            chunking: The chunking rules for every document.
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
        self._engine = SearchEngine(
            graph_store=store,
            embedder=self._embedder,
            graph_schema=schema,
            tracer=tracer,
        )
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
            extractor=BAMLExtractor(
                settings=self._settings.extraction, tracer=self._tracer
            ),
            tracer=self._tracer,
            chunking=self._chunking,
            max_llm_pairs=self._settings.max_llm_pairs,
        )
        await graph.add(documents=self._documents)

    async def answer(self, question: BenchmarkQuestion) -> SystemAnswer:
        """Answer with a fresh agent, passing the whole conversation.

        Raises:
            AgentFailureError: The agent hit its recursion limit or gave no answer.
        """
        agent = build_agent(
            engine=self._engine,
            llm_settings=self._settings.agent,
            agent_settings=self._settings.agent_loop,
            graph_schema=self._schema,
            tracer=self._tracer,
        )
        try:
            # LangGraph rewrites the list it gets in place, which would replace the
            # question's own message dicts with message objects.
            result = await agent.ainvoke(
                {"messages": [dict(message) for message in question.messages]}
            )
            text = final_answer(result)
        except (GraphRecursionError, ValueError) as error:
            raise AgentFailureError(str(error)) from error
        if not text.strip():
            raise AgentFailureError("empty answer")
        return await self._with_citations(text, result)

    async def _with_citations(self, text: str, result: dict) -> SystemAnswer:
        """Resolve the citation keys in the answer through the run's ledger."""
        ledger = result["ledger"]
        chunks: list[CitedChunk] = []
        other = 0
        source_ids: list[str] = []
        for key in dict.fromkeys(_CITATION_KEY.findall(text)):
            found = ledger.resolve(key)
            if found is None:
                continue
            item = found.item
            if isinstance(item, Chunk):
                provenance = item.provenance
                has_offsets = isinstance(provenance, TextProvenance)
                chunks.append(
                    CitedChunk(
                        uri=self._uri_by_document_id.get(
                            item.document_id, str(item.document_id)
                        ),
                        char_start=provenance.char_start if has_offsets else None,
                        char_end=provenance.char_end if has_offsets else None,
                    )
                )
                continue
            other += 1
            if isinstance(item, (Entity, Relation)):
                source_ids.extend(str(i) for i in item.source_chunk_ids)
        return SystemAnswer(
            text=text,
            cited_chunks=chunks,
            non_chunk_citations=other,
            source_chunks=await self._chunks_by_id(source_ids),
            raw=result,
        )

    async def _chunks_by_id(self, ids: Sequence[str]) -> list[CitedChunk]:
        """Read the document and offsets of stored chunks. A missing id is skipped."""
        if not ids:
            return []
        rows = await self._store.execute_read(
            load_chunks_by_id_query(),
            {"ids": list(dict.fromkeys(ids)), "job_id": None},
        )
        chunks = []
        for row in rows:
            props = row.get("n", row)
            provenance = props.get("provenance")
            if isinstance(provenance, str):
                provenance = json.loads(provenance)
            has_offsets = isinstance(provenance, dict) and provenance.get("kind") == (
                "text"
            )
            uri = self._uri_by_document_id.get(
                UUID(props["document_id"]), props["document_id"]
            )
            chunks.append(
                CitedChunk(
                    uri=uri,
                    char_start=provenance["char_start"] if has_offsets else None,
                    char_end=provenance["char_end"] if has_offsets else None,
                )
            )
        return chunks

    async def teardown(self) -> None:
        """Close the graph store."""
        await self._store.close()
