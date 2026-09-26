"""Fixtures for the judged and real-agent evaluation tests.

``judge`` builds the DeepEval judge from ``EVAL_JUDGE_*`` (falling back to
``LLM_*``) and skips when no key is set, as on fork pull requests.
``tiny_corpus`` ingests three short documents about one invented company into
Neo4j with a fixed extractor and ``_FakeHashedWordEmbedder``, so the graph is the
same on every run. The embedder scores word overlap only, so questions must
share words with the passages they target. ``agent_factory`` builds an agent
over that graph with the real LLM.
``answer_quality_graph`` ingests the FinQA pages of the answer-quality fixture
with a fixed extractor and the same embedder. ``answer_quality_agent_factory``
builds an agent over it.
"""

import asyncio
import hashlib
import importlib.util
import re
import shutil
from collections.abc import AsyncGenerator, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel

from agrag.agents.build import build_agent
from agrag.agents.settings import AgentLLMSettings
from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.vector_record import Distance
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.eval.judge import ChatModelJudge
from agrag.eval.settings import EvalJudgeSettings
from agrag.graphdb import build_graph_store
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.retrieval.search_engine import SearchEngine
from agrag.retrieval.settings import RetrievalSettings
from tests.integration._schema_cleanup import drop_schema_for
from tests.integration.eval._answer_quality import FIXTURE_DIR


_DIMENSIONS = 64
_TOKEN_PATTERN = re.compile(r"\w+")

_PEOPLE = ("Marlow Quist", "Tobias Renn")
_ORGANIZATIONS = ("Zephyra Robotics",)
_PRODUCTS = ("Lumen-9",)

DOCUMENTS = (
    "Zephyra Robotics was founded in 2011 in the city of Halvorn by Marlow Quist. "
    "The company builds warehouse robots. Ref {token}.",
    "Tobias Renn joined Zephyra Robotics in 2016 as chief engineer. "
    "Tobias Renn designed the Lumen-9 lifting arm. Ref {token}.",
    "The Lumen-9 is a warehouse robot that can lift 40 kilograms. "
    "Zephyra Robotics released the Lumen-9 in 2019. Ref {token}.",
)


class _FakeHashedWordEmbedder(Embedder):
    """Embedder that hashes each lower-cased word into one of 64 buckets.

    Vectors are counts of words per bucket, L2-normalised. They are never
    zero, so a cosine vector index accepts them, and similarity follows word
    overlap.
    """

    model = "hashed-words"

    async def dimensions(self) -> int:
        """Return 64 dimensions."""
        return _DIMENSIONS

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one bucket-count vector per text."""
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        """Count the words of ``text`` per bucket and normalise the counts."""
        counts = [0.0] * _DIMENSIONS
        for word in _TOKEN_PATTERN.findall(text.lower()):
            digest = hashlib.sha1(word.encode(), usedforsecurity=False).digest()
            counts[int.from_bytes(digest[:4], "big") % _DIMENSIONS] += 1.0
        norm = sum(value * value for value in counts) ** 0.5
        if norm == 0.0:
            counts[0] = 1.0
            return counts
        return [value / norm for value in counts]


class _FactExtractor(Extractor):
    """Extractor that finds the fixed names of the corpus."""

    def __init__(self, labels: dict[str, str]) -> None:
        """Map each known name to its graph label."""
        self._labels = labels

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return one entity per known name in the chunk text."""
        entities = [
            ExtractedEntity(
                chunk_id=chunk.id,
                label=label,
                text=name,
                char_start=chunk.text.index(name),
                char_end=chunk.text.index(name) + len(name),
            )
            for name, label in self._labels.items()
            if name in chunk.text
        ]
        return ExtractionResult(
            entities=entities, relations=[], extractor_name="eval-corpus"
        )


@dataclass
class TinyCorpus:
    """The ingested corpus and the handles tests use to query it.

    Attributes:
        engine: Retrieval over the corpus graph.
        store: The connected graph store.
        labels: The entity labels created for this run.
        token: Text unique to this run, present in every chunk.
    """

    engine: SearchEngine
    store: GraphStore
    labels: tuple[str, ...]
    token: str


@dataclass
class AnswerQualityGraph:
    """The ingested answer-quality corpus.

    Attributes:
        engine: Retrieval over the corpus graph.
    """

    engine: SearchEngine


class _ThrottledJudge(ChatModelJudge):
    """Judge that runs at most four calls at once and retries an empty reply.

    The endpoint answers 429 when the median-of-3 metrics and the per-sentence
    citation checks all call it together. It also sometimes returns an empty
    reply, which no schema can parse.
    """

    _limit = 4
    _attempts = 3

    def __init__(self, chat_model: Any, name: str) -> None:
        """Bind the chat model and create the call gate."""
        super().__init__(chat_model, name)
        self._gate = asyncio.Semaphore(self._limit)

    async def a_generate(
        self, prompt: str, schema: type[BaseModel] | None = None
    ) -> Any:
        """Run one judge call once a slot is free."""
        async with self._gate:
            for _ in range(self._attempts - 1):
                try:
                    return await super().a_generate(prompt, schema)
                except ValueError:
                    continue
            return await super().a_generate(prompt, schema)


@pytest.fixture
def judge() -> ChatModelJudge:
    """Build the DeepEval judge, or skip when no judge model is configured."""
    try:
        settings = EvalJudgeSettings.from_openai_compatible_env()
    except ValueError:
        pytest.skip("Eval judge model not configured")
    if not settings.client.api_key:
        pytest.skip("Eval judge API key not configured")
    plain = ChatModelJudge.from_settings(settings)
    # The client backs off on 429 replies.
    chat_model = plain.load_model().model_copy(update={"max_retries": 8})
    return _ThrottledJudge(chat_model, plain.get_model_name())


@pytest.fixture
async def tiny_corpus() -> AsyncGenerator[TinyCorpus, None]:
    """Ingest the invented company corpus into a fresh set of labels."""
    if importlib.util.find_spec("neo4j") is None:
        pytest.skip("neo4j extra not installed")
    store = build_graph_store("neo4j")
    token = f"run{uuid4().hex[:8]}"
    suffix = uuid4().hex[:8]
    person = validate_identifier(f"Person_{suffix}")
    organization = validate_identifier(f"Organization_{suffix}")
    product = validate_identifier(f"Product_{suffix}")
    labels = (person, organization, product)
    schema = GraphSchema(
        name="eval_corpus",
        version="1",
        entities=[
            EntityType(label=person, description="A person."),
            EntityType(label=organization, description="A company."),
            EntityType(label=product, description="A product."),
        ],
        relations=[],
    )
    embedder = _FakeHashedWordEmbedder()
    connected = False
    try:
        await store.connect()
        connected = True
        for label in (*labels, CHUNK_LABEL):
            await store.ensure_vector_index(
                label=label,
                vector_property="embedding",
                dimensions=_DIMENSIONS,
                distance=Distance.COSINE,
            )
        name_labels = {
            **dict.fromkeys(_PEOPLE, person),
            **dict.fromkeys(_ORGANIZATIONS, organization),
            **dict.fromkeys(_PRODUCTS, product),
        }
        graph = Graph(
            schema=schema,
            graph_store=store,
            embedder=embedder,
            extractor=_FactExtractor(name_labels),
        )
        for template in DOCUMENTS:
            await graph.add(text=template.format(token=token))
        engine = SearchEngine(
            graph_store=store,
            embedder=embedder,
            settings=RetrievalSettings(entity_top_k=10, chunk_top_k=10),
            graph_schema=schema,
        )
        yield TinyCorpus(engine=engine, store=store, labels=labels, token=token)
    finally:
        if connected:
            try:
                await store.execute_write(
                    f"MATCH (c:{CHUNK_LABEL}) WHERE c.text CONTAINS $token "
                    "DETACH DELETE c",
                    {"token": token},
                )
                for label in labels:
                    await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
                # CHUNK_LABEL's index and constraints are global: every suite
                # writes CHUNK_LABEL, and its schema cannot be dropped per
                # test. Deleting this fixture's own chunk ids by token, above,
                # leaves a concurrent suite's chunk data alone.
                await drop_schema_for(store, *labels)
            finally:
                await store.close()
        else:
            await store.close()


@pytest.fixture
def agent_factory(request: pytest.FixtureRequest) -> Callable[[], Any]:
    """Return a function that builds an agent over the corpus with the real LLM."""
    settings = AgentLLMSettings.from_openai_compatible_env()
    if not settings.clients[0].api_key:
        pytest.skip("Agent LLM API key not configured")
    tiny_corpus: TinyCorpus = request.getfixturevalue("tiny_corpus")

    def build() -> Any:
        """Build a new agent, so each test gets its own run state."""
        return build_agent(engine=tiny_corpus.engine, llm_settings=settings)

    return build


@pytest.fixture
async def answer_quality_graph(
    tmp_path: Path,
) -> AsyncGenerator[AnswerQualityGraph, None]:
    """Ingest the FinQA pages with the real extractor into a fresh set of labels."""
    if importlib.util.find_spec("neo4j") is None:
        pytest.skip("neo4j extra not installed")
    documents = tmp_path / "documents"
    shutil.copytree(FIXTURE_DIR / "documents", documents)
    store = build_graph_store("neo4j")
    suffix = uuid4().hex[:8]
    company = validate_identifier(f"Company_{suffix}")
    metric = validate_identifier(f"FinancialMetric_{suffix}")
    period = validate_identifier(f"Period_{suffix}")
    labels = (company, metric, period)
    # A fixed extractor keeps the graph the same on every run and needs no LLM.
    # Extraction quality has its own evaluation.
    names = {
        "euro": metric,
        "pound sterling": metric,
        "indian rupee": metric,
        "total impact": metric,
        "foreign currency": metric,
        "2012": period,
        "2011": period,
        "2010": period,
    }
    schema = GraphSchema(
        name="answer_quality",
        version="1",
        entities=[
            EntityType(label=company, description="A company or business unit."),
            EntityType(
                label=metric,
                description="A financial measure, such as revenue or net income.",
            ),
            EntityType(label=period, description="A year, quarter or date."),
        ],
        relations=[],
    )
    embedder = _FakeHashedWordEmbedder()
    connected = False
    try:
        await store.connect()
        connected = True
        for label in (*labels, CHUNK_LABEL):
            await store.ensure_vector_index(
                label=label,
                vector_property="embedding",
                dimensions=_DIMENSIONS,
                distance=Distance.COSINE,
            )
        graph = Graph(
            schema=schema,
            graph_store=store,
            embedder=embedder,
            extractor=_FactExtractor(names),
        )
        await graph.add(source=documents)
        engine = SearchEngine(
            graph_store=store,
            embedder=embedder,
            settings=RetrievalSettings(entity_top_k=10, chunk_top_k=10),
            graph_schema=schema,
        )
        yield AnswerQualityGraph(engine=engine)
    finally:
        if connected:
            try:
                await store.execute_write(
                    f"MATCH (d:{DOCUMENT_LABEL}) WHERE d.uri STARTS WITH $prefix "
                    f"OPTIONAL MATCH (c:{CHUNK_LABEL})-[:PART_OF]-(d) "
                    "DETACH DELETE c, d",
                    {"prefix": str(documents)},
                )
                await store.execute_write(
                    "MATCH (j:CutoverJob) WHERE j.document_key STARTS WITH $prefix "
                    "DETACH DELETE j",
                    {"prefix": str(documents)},
                )
                for label in labels:
                    await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
                await drop_schema_for(store, *labels)
            finally:
                await store.close()
        else:
            await store.close()


@pytest.fixture
def answer_quality_agent_factory(
    request: pytest.FixtureRequest,
) -> Callable[..., Any]:
    """Return a function that builds an agent over the FinQA graph."""
    settings = AgentLLMSettings.from_openai_compatible_env()
    if not settings.clients[0].api_key:
        pytest.skip("Agent LLM API key not configured")
    graph: AnswerQualityGraph = request.getfixturevalue("answer_quality_graph")

    def build(tracer: Any = None) -> Any:
        """Build a new agent, so each question gets its own run state."""
        return build_agent(engine=graph.engine, llm_settings=settings, tracer=tracer)

    return build
