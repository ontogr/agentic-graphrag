"""Tests for the shared per-batch ingestion core.

``ingest_chunks()`` is a pure move of ``Graph.add()``'s pipeline body, so
the characterization test runs the same input through both paths and
asserts identical summaries. ``extract_chunks()`` is covered for its
cross-batch index threading.
"""

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.chunking.chunker import ChunkPlacement
from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_record import UpsertFailure, UpsertResult
from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    RelationType,
)
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.stage_failure import StageFailure
from agrag.embedding.base import Embedder
from agrag.ingestion._ingest_pipeline import (
    embed_chunks_stage,
    extract_chunks,
    ingest_chunks,
)
from agrag.ingestion._stage_context import StageContext
from agrag.ingestion._storage import WriteOutcome
from agrag.ingestion.extract import Extractor, LLMExtractor
from agrag.ingestion.graph import Graph
from agrag.ingestion.reports.escalation_report import EscalationReport
from agrag.ingestion.resolve import ResolutionResult
from agrag.ingestion.resolve.candidate_source import GraphCandidateSource
from agrag.ingestion.settings import ExtractionSettings
from agrag.ingestion.stats import IngestStats, MergeStats
from agrag.loaders.types import ErrorPolicy
from agrag.observability import get_tracer
from tests.unit.ingestion._lease_fake import CutoverJobLeaseFake


_SETTINGS = ExtractionSettings()


def _doc(*, key: str, text: str = "hello world") -> Document:
    return Document(
        text=text,
        title="t",
        uri=key,
        document_key=key,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=f"hash-{key}-{text}",
        loader_name="text",
        char_count=len(text),
        line_count=1,
    )


def _chunk(document: Document, *, index: int = 0, text: str = "hello world") -> Chunk:
    return Chunk(
        id=uuid4(),
        document_id=Document.node_id_for(document_key=document.resolved_document_key),
        index=index,
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )


def _placements(chunks: list[Chunk]) -> dict[UUID, ChunkPlacement]:
    """Place each chunk directly under its document node, in index order."""
    return {
        chunk.id: ChunkPlacement(
            chunk_index=chunk.index,
            parent_node_id=chunk.document_id,
            order=chunk.index,
        )
        for chunk in chunks
        if chunk.id is not None
    }


# Schema whose only relation is a Person -> Person KNOWS, so fixtures that
# emit KNOWS keep their relations through schema validation.
_KNOWS_SCHEMA = GraphSchema(
    name="knows",
    version="1",
    entities=[EntityType(label="Person", description="A named individual.")],
    relations=[
        RelationType(
            label="KNOWS",
            description="A person knows another person.",
            patterns=[("Person", "Person")],
        )
    ],
)

# Schema that declares only Person and a Person -> Person RELATED_TO relation.
_RELATED_TO_SCHEMA = GraphSchema(
    name="related-to",
    version="1",
    entities=[EntityType(label="Person", description="A named individual.")],
    relations=[
        RelationType(
            label="RELATED_TO",
            description="A person is related to another person.",
            patterns=[("Person", "Person")],
        )
    ],
)


class _ZeroEmbedder(Embedder):
    """Fake embedder returning zero vectors."""

    model = "fake"

    async def dimensions(self) -> int:
        """Return a small fixed dimension."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a zero vector per text."""
        return [[0.0] * 4 for _ in texts]


class _NoopExtractor(Extractor):
    """Fake extractor returning no entities."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return no entities or relations for any chunk."""
        return ExtractionResult(entities=[], relations=[], extractor_name="noop")


def _store() -> tuple[AsyncMock, dict[str, list[Any]]]:
    """Build a canned store and the calls it records."""
    calls: dict[str, list[Any]] = {"nodes": [], "relations": []}
    store = AsyncMock()

    async def _upsert_nodes(
        label: str, nodes: Sequence[Any], **kwargs: Any
    ) -> UpsertResult:
        calls["nodes"].append((label, list(nodes)))
        return UpsertResult(written=len(nodes))

    async def _upsert_relations(
        relations: Sequence[Any], **kwargs: Any
    ) -> UpsertResult:
        calls["relations"].append(list(relations))
        return UpsertResult(written=len(relations))

    store.upsert_nodes.side_effect = _upsert_nodes
    store.upsert_relations.side_effect = _upsert_relations
    store.execute_read.return_value = []
    lease = CutoverJobLeaseFake()

    async def _execute_write(
        query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        handled = lease.handle_cutover_query(query, parameters)
        return handled if handled is not None else []

    # Graph.add() runs its pipeline as a Cutover Job, so the store has to
    # answer the lease protocol's queries.
    store.execute_write.side_effect = _execute_write

    async def run_in_transaction(work: Any) -> Any:
        return await work(store)

    store.run_in_transaction.side_effect = run_in_transaction
    return store, calls


async def _ingest(
    documents: list[Document],
    chunks: list[Chunk],
    store: AsyncMock,
    *,
    ingestion: IngestStats | None = None,
) -> Any:
    """Run extract_chunks + ingest_chunks over fixed input."""
    extracted = await extract_chunks(
        chunks,
        start_index=0,
        extractor=_NoopExtractor(),
        schema=DEFAULT_SCHEMA,
        error_policy=ErrorPolicy.RAISE,
        settings=_SETTINGS,
        llm_extractor=None,
    )
    batch = await ingest_chunks(
        chunks,
        documents,
        extracted.entities,
        extracted.relations,
        extracted.failures,
        placements=_placements(chunks),
        graph_store=store,
        embedder=_ZeroEmbedder(),
        graph_schema=DEFAULT_SCHEMA,
        error_policy=ErrorPolicy.RAISE,
        ingestion=ingestion or IngestStats(documents=len(documents)),
    )
    return batch.add_result


class TestIngestChunks:
    """ingest_chunks() produces the AddResult shape add() produces."""

    async def test_empty_chunks_writes_only_the_document_node(self) -> None:
        """No chunks still writes the document node and counts no chunk work."""
        store, _ = _store()
        doc = _doc(key="a")

        result = await _ingest([doc], [], store)

        assert result.extraction.chunks_processed == 0
        assert result.merge == MergeStats()
        assert result.storage.nodes_written == 1
        assert result.chunks == []

    async def test_empty_chunks_reports_structure_write_failures(self) -> None:
        """A failed document write shows in storage failures, not silently."""
        store, _ = _store()
        store.upsert_nodes.side_effect = None
        store.upsert_nodes.return_value = UpsertResult(
            failures=[
                UpsertFailure(id="d", error_type="WriteError", error_message="boom")
            ]
        )

        result = await _ingest([_doc(key="a")], [], store)

        assert [f.item_id for f in result.storage.failures] == ["d"]

    async def test_raise_policy_cancels_extractions_still_running(self) -> None:
        """The first failure under RAISE stops the other chunks."""
        finished: list[str] = []

        class _Failing(Extractor):
            async def extract(
                self, chunk: Chunk, schema: GraphSchema
            ) -> ExtractionResult:
                if chunk.text == "bad":
                    raise RuntimeError("boom")
                await asyncio.sleep(0.5)
                finished.append(chunk.text)
                return ExtractionResult(entities=[], relations=[], extractor_name="f")

        doc = _doc(key="a")
        chunks = [_chunk(doc, text=t) for t in ("bad", "slow-1", "slow-2")]

        with pytest.raises(RuntimeError, match="boom"):
            await extract_chunks(
                chunks,
                start_index=0,
                extractor=_Failing(),
                schema=DEFAULT_SCHEMA,
                error_policy=ErrorPolicy.RAISE,
                settings=_SETTINGS,
                llm_extractor=None,
            )

        await asyncio.sleep(0.6)
        assert finished == []

    async def test_a_failed_relation_remap_opens_its_own_span(self) -> None:
        """Under a non-RAISE policy a bad relation is recorded, not raised."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        doc = _doc(key="a")
        chunk = _chunk(doc)

        class _BadRelation(Extractor):
            async def extract(
                self, chunk: Chunk, schema: GraphSchema
            ) -> ExtractionResult:
                entity = ExtractedEntity(
                    chunk_id=chunk.id,
                    label="Person",
                    text="Ada",
                    char_start=0,
                    char_end=3,
                )
                loop = ExtractedRelation.model_construct(
                    chunk_id=chunk.id, label="KNOWS", source_index=0, target_index=0
                )
                return ExtractionResult.model_construct(
                    entities=[entity], relations=[loop], extractor_name="bad"
                )

        extracted = await extract_chunks(
            [chunk],
            start_index=0,
            extractor=_BadRelation(),
            schema=_KNOWS_SCHEMA,
            error_policy=ErrorPolicy.SKIP,
            settings=_SETTINGS,
            llm_extractor=None,
            tracer=provider.get_tracer("test"),
        )

        names = [span.name for span in exporter.get_finished_spans()]
        assert extracted.relations == []
        assert [f.item_id for f in extracted.failures] == [str(chunk.id)]
        assert "agrag.extraction.remap_relations" in names

    async def test_runs_at_most_the_extractor_max_concurrency_at_once(self) -> None:
        """The extractor's limit caps how many chunks are in flight."""
        in_flight = 0
        peak = 0

        class _Limited(Extractor):
            max_concurrency = 2

            async def extract(
                self, chunk: Chunk, schema: GraphSchema
            ) -> ExtractionResult:
                nonlocal in_flight, peak
                in_flight += 1
                peak = max(peak, in_flight)
                await asyncio.sleep(0.01)
                in_flight -= 1
                return ExtractionResult(entities=[], relations=[], extractor_name="x")

        doc = _doc(key="limit")
        chunks = [_chunk(doc, index=i) for i in range(6)]

        await extract_chunks(
            chunks,
            start_index=0,
            extractor=_Limited(),
            schema=DEFAULT_SCHEMA,
            error_policy=ErrorPolicy.RAISE,
            settings=_SETTINGS,
            llm_extractor=None,
        )

        assert peak == 2

    async def test_global_candidate_writes_no_mentioned_in(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A persisted candidate match never fabricates chunk evidence.

        Regression test: synthetic persisted-candidate mentions share
        ``mention_to_entity`` with real mentions, but their chunks were
        never written. Indexing them into this batch's chunk list raised
        ``IndexError``; they must be skipped instead.
        """
        store, calls = _store()
        doc = _doc(key="synthetic")
        chunk = _chunk(doc, text="Ada Lovelace wrote the first algorithm.")
        chunk_id = uuid4()
        chunk.id = chunk_id
        persisted = Entity(id=uuid4(), label="Person", name="Zed Unrelated")
        consulted: list[str] = []

        async def _candidates(
            self: GraphCandidateSource, mention: ExtractedEntity
        ) -> list[tuple[Entity, float]]:
            consulted.append(mention.text)
            return [(persisted, 0.0)]

        monkeypatch.setattr(GraphCandidateSource, "global_candidates_for", _candidates)
        resolver_instance = AsyncMock()
        resolver_instance.resolve.return_value = ResolutionResult(groups=[], matches=[])
        with mock.patch(
            "agrag.ingestion.resolve.resolution.Resolver",
            return_value=resolver_instance,
        ):
            outcome = await ingest_chunks(
                [chunk],
                [doc],
                [
                    ExtractedEntity(
                        chunk_id=chunk_id,
                        label="Person",
                        text="Ada Lovelace",
                        char_start=0,
                        char_end=12,
                    )
                ],
                [],
                [],
                placements=_placements([chunk]),
                graph_store=store,
                embedder=_ZeroEmbedder(),
                graph_schema=DEFAULT_SCHEMA,
                error_policy=ErrorPolicy.RAISE,
                ingestion=IngestStats(documents=1),
                return_chunks=False,
            )
        assert outcome.add_result.merge.failures == []
        assert consulted == ["Ada Lovelace"]
        mentioned = [
            rec
            for batch in calls["relations"]
            for rec in batch
            if rec.type == "MENTIONED_IN"
        ]
        assert len(mentioned) == 1
        assert mentioned[0].start_id == chunk_id

    async def _ingest_two_mentions(
        self,
        monkeypatch: pytest.MonkeyPatch,
        store: AsyncMock,
        error_policy: ErrorPolicy,
    ) -> Any:
        """Ingest "Ada" and "Grace" when the candidate read for "Ada" fails."""
        doc = _doc(key="candidates")
        chunk = _chunk(doc, text="Ada and Grace.")

        async def _candidates(
            self: GraphCandidateSource, mention: ExtractedEntity
        ) -> list[tuple[Entity, float]]:
            if mention.text == "Ada":
                raise RuntimeError("candidate read failed")
            return []

        monkeypatch.setattr(GraphCandidateSource, "global_candidates_for", _candidates)
        mentions = [
            ExtractedEntity(
                chunk_id=chunk.id,
                label="Person",
                text=text,
                char_start=start,
                char_end=start + len(text),
            )
            for text, start in (("Ada", 0), ("Grace", 8))
        ]
        outcome = await ingest_chunks(
            [chunk],
            [doc],
            mentions,
            [],
            [],
            placements=_placements([chunk]),
            graph_store=store,
            embedder=_ZeroEmbedder(),
            graph_schema=DEFAULT_SCHEMA,
            error_policy=error_policy,
            ingestion=IngestStats(documents=1),
        )
        return outcome.add_result

    async def test_failed_candidate_read_is_recorded_and_mention_not_stored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed candidate read is reported and its mention is not resolved."""
        store, _ = _store()

        result = await self._ingest_two_mentions(monkeypatch, store, ErrorPolicy.SKIP)

        assert [failure.item_id for failure in result.merge.failures] == ["Ada"]
        assert result.merge.failures[0].error_message == "candidate read failed"
        assert result.merge.nodes_created == 1

    async def test_failed_candidate_read_raises_under_raise_policy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAISE propagates a failed candidate read."""
        store, _ = _store()

        with pytest.raises(RuntimeError, match="candidate read failed"):
            await self._ingest_two_mentions(monkeypatch, store, ErrorPolicy.RAISE)


class TestIngestMatchesAdd:
    """The extraction is a pure move: add() and the core agree."""

    async def test_same_documents_produce_same_summary(self) -> None:
        """add(documents=...) and extract+ingest return identical summaries."""
        text = "characterization input text for the pipeline core"
        docs = [_doc(key="charlie", text=text)]

        core_store, _ = _store()
        core_chunks = [_chunk(docs[0], index=0, text=text)]
        core_result = await _ingest(docs, core_chunks, core_store)

        add_store, _ = _store()
        graph = await Graph.open(
            schema=DEFAULT_SCHEMA,
            graph_store=add_store,
            embedder=_ZeroEmbedder(),
            extractor=_NoopExtractor(),
        )
        add_result = await graph.add(documents=docs)

        assert core_result.ingestion == add_result.ingestion
        assert core_result.extraction == add_result.extraction
        assert core_result.storage == add_result.storage
        assert core_result.resolution == add_result.resolution
        assert core_result.merge == add_result.merge


class TestHeadingContextEmbedding:
    """embed_heading_path decides whether the embedder sees the heading path."""

    async def _run(
        self, chunk: Chunk, *, embed_heading_path: bool
    ) -> tuple[list[str], list]:
        store, _ = _store()
        writes: list[Any] = []
        original = store.execute_write.side_effect

        async def record(query: str, parameters: Any = None) -> Any:
            if parameters and "records" in parameters:
                writes.extend(parameters["records"])
            return await original(query, parameters)

        store.execute_write.side_effect = record
        embedded: list[str] = []

        class _Recorder(_ZeroEmbedder):
            async def embed(self, texts: Sequence[str]) -> list[list[float]]:
                embedded.extend(texts)
                return await super().embed(texts)

        await ingest_chunks(
            [chunk],
            [_doc(key="h")],
            [],
            [],
            [],
            placements=_placements([chunk]),
            graph_store=store,
            embedder=_Recorder(),
            graph_schema=DEFAULT_SCHEMA,
            error_policy=ErrorPolicy.RAISE,
            ingestion=IngestStats(documents=1),
            embed_heading_path=embed_heading_path,
        )
        return embedded, writes

    def _chunk(self, path: list[str]) -> Chunk:
        return Chunk(
            id=uuid4(),
            document_id=Document.node_id_for(document_key="h"),
            text="body text",
            provenance=TextProvenance(char_start=0, char_end=9),
            heading_path=path,
        )

    async def test_flag_on_embeds_the_heading_path_with_the_text(self) -> None:
        """The embedder gets the contextual text; the guard keeps the raw text."""
        embedded, writes = await self._run(
            self._chunk(["A", "B"]), embed_heading_path=True
        )

        assert embedded == ["A > B\n\nbody text"]
        assert [w["expected_text"] for w in writes if "vector" in w] == ["body text"]

    async def test_flag_off_embeds_the_raw_text(self) -> None:
        """Without the flag the embedder sees only the chunk text."""
        embedded, _ = await self._run(self._chunk(["A"]), embed_heading_path=False)

        assert embedded == ["body text"]

    async def test_chunk_without_headings_embeds_the_raw_text(self) -> None:
        """No headings, no context, even with the flag on."""
        embedded, _ = await self._run(self._chunk([]), embed_heading_path=True)

        assert embedded == ["body text"]


class TestExtractChunks:
    """extract_chunks() remaps relation indices across batch calls."""

    async def test_start_index_shifts_later_batches(self) -> None:
        """A second batch call remaps as one continuous call would."""

        class _PairExtractor(Extractor):
            async def extract(
                self, chunk: Chunk, schema: GraphSchema
            ) -> ExtractionResult:
                first = ExtractedEntity(
                    chunk_id=chunk.id or uuid4(),
                    label="Person",
                    text=f"person-{chunk.index}-a",
                    char_start=0,
                    char_end=1,
                )
                second = ExtractedEntity(
                    chunk_id=first.chunk_id,
                    label="Person",
                    text=f"person-{chunk.index}-b",
                    char_start=2,
                    char_end=3,
                )
                return ExtractionResult(
                    entities=[first, second],
                    relations=[
                        ExtractedRelation(
                            chunk_id=first.chunk_id,
                            label="KNOWS",
                            source_index=0,
                            target_index=1,
                        )
                    ],
                    extractor_name="pair",
                )

        doc = _doc(key="offsets")
        first = [_chunk(doc, index=0)]
        second = [_chunk(doc, index=1)]
        extractor = _PairExtractor()

        first_batch = await extract_chunks(
            first,
            start_index=0,
            extractor=extractor,
            schema=_KNOWS_SCHEMA,
            error_policy=ErrorPolicy.RAISE,
            settings=_SETTINGS,
            llm_extractor=None,
        )
        second_batch = await extract_chunks(
            second,
            start_index=len(first_batch.entities),
            extractor=extractor,
            schema=_KNOWS_SCHEMA,
            error_policy=ErrorPolicy.RAISE,
            settings=_SETTINGS,
            llm_extractor=None,
        )

        assert [rel.source_index for rel in first_batch.relations] == [0]
        assert [rel.target_index for rel in first_batch.relations] == [1]
        assert [rel.source_index for rel in second_batch.relations] == [2]
        assert [rel.target_index for rel in second_batch.relations] == [3]
        assert len(first_batch.entities) + len(second_batch.entities) == 4

    async def test_label_outside_the_schema_is_dropped_not_raised(self) -> None:
        """An undeclared label is dropped and the batch still succeeds."""

        class _RogueExtractor(Extractor):
            async def extract(
                self, chunk: Chunk, schema: GraphSchema
            ) -> ExtractionResult:
                chunk_id = chunk.id or uuid4()
                person = ExtractedEntity(
                    chunk_id=chunk_id,
                    label="Person",
                    text="Ada",
                    char_start=0,
                    char_end=3,
                )
                ghost = ExtractedEntity(
                    chunk_id=chunk_id,
                    label="Bad Label",
                    text="Acme",
                    char_start=4,
                    char_end=8,
                )
                return ExtractionResult(
                    entities=[person, ghost],
                    relations=[
                        ExtractedRelation(
                            chunk_id=chunk_id,
                            label="RELATED_TO",
                            source_index=0,
                            target_index=1,
                        )
                    ],
                    extractor_name="rogue",
                )

        doc = _doc(key="rogue")
        batch = await extract_chunks(
            [_chunk(doc)],
            start_index=0,
            extractor=_RogueExtractor(),
            schema=_RELATED_TO_SCHEMA,
            error_policy=ErrorPolicy.RAISE,
            settings=_SETTINGS,
            llm_extractor=None,
        )

        assert [entity.label for entity in batch.entities] == ["Person"]
        assert batch.relations == []
        assert batch.failures == []


class _ScoredExtractor(Extractor):
    """Fake first extractor that scores each chunk by its text.

    The text of a chunk is its score, for example ``"0.6"``. Any text that does
    not start with ``"0."`` gives no entities.
    """

    def __init__(self, *, limit: int = 8) -> None:
        """Create the extractor with a concurrency limit and call counters."""
        self.max_concurrency = limit
        self.active = 0
        self.peak = 0
        self.calls: list[str] = []

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Record the call and return one entity scored by the chunk text."""
        self.active += 1
        self.peak = max(self.peak, self.active)
        self.calls.append(chunk.text)
        await asyncio.sleep(0.01)
        self.active -= 1
        entities = (
            [
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label="Person",
                    text="Ada",
                    char_start=0,
                    char_end=3,
                    confidence=float(chunk.text),
                )
            ]
            if chunk.text.startswith("0.")
            else []
        )
        return ExtractionResult(entities=entities, relations=[], extractor_name="first")


class _UnparsableAnswerError(ValueError):
    """Raised by a fake LLM extractor whose answer did not parse."""


class _LlmExtractor(LLMExtractor):
    """Fake escalation extractor with a scripted answer for each chunk text.

    A chunk whose text is in ``raises`` raises that error. A chunk whose text is
    in ``empty`` gets a parsed answer with no entities. With ``echo`` the answer
    holds the candidates it received, relabelled with ``label``; otherwise it
    holds one entity named Grace.
    """

    def __init__(
        self,
        *,
        limit: int = 8,
        raises: dict[str, Exception] | None = None,
        empty: set[str] | None = None,
        label: str = "Person",
        echo: bool = False,
    ) -> None:
        """Create the extractor with a concurrency limit and call counters."""
        self.max_concurrency = limit
        self.active = 0
        self.peak = 0
        self.calls: list[str] = []
        self.seen: list[list[str]] = []
        self._raises = raises or {}
        self._empty = empty or set()
        self._label = label
        self._echo = echo

    async def extract(
        self,
        chunk: Chunk,
        schema: GraphSchema,
        candidates: Sequence[ExtractedEntity] | None = None,
    ) -> ExtractionResult:
        """Record the call, then raise, return no entities, or answer."""
        self.active += 1
        self.peak = max(self.peak, self.active)
        self.calls.append(chunk.text)
        self.seen.append([entity.text for entity in candidates or []])
        await asyncio.sleep(0.01)
        self.active -= 1
        if chunk.text in self._raises:
            raise self._raises[chunk.text]
        if chunk.text in self._empty:
            return ExtractionResult(entities=[], relations=[], extractor_name="llm")
        names = self.seen[-1] if self._echo else ["Grace"]
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label=self._label,
                    text=name,
                    char_start=50 + 10 * position,
                    char_end=50 + 10 * position + len(name),
                    confidence=None,
                )
                for position, name in enumerate(names)
            ],
            relations=[],
            extractor_name="llm",
        )


async def _run_two_phase(
    texts: list[str],
    *,
    first: Extractor,
    llm: LLMExtractor | None,
    settings: ExtractionSettings,
    error_policy: ErrorPolicy = ErrorPolicy.RAISE,
) -> tuple[list[ExtractedEntity], list[StageFailure], EscalationReport]:
    """Run extract_chunks over chunks with the given texts."""
    doc = _doc(key="two-phase")
    chunks = [_chunk(doc, index=i, text=t) for i, t in enumerate(texts)]
    batch = await extract_chunks(
        chunks,
        start_index=0,
        extractor=first,
        schema=DEFAULT_SCHEMA,
        error_policy=error_policy,
        settings=settings,
        llm_extractor=llm,
    )
    return batch.entities, batch.failures, batch.report


class TestExtractChunksEscalation:
    """extract_chunks() runs the first extractor on all chunks, then the LLM on some."""

    async def test_llm_runs_only_on_the_weakest_chunks_within_the_budget(self) -> None:
        """Two of ten chunks escalate, and they are the two weakest."""
        texts = ["0.9", "0.5", "0.9", "0.55", "0.9", "0.6", "0.9", "0.65", "0.9", "0.9"]
        first, llm = _ScoredExtractor(), _LlmExtractor()

        _, _, report = await _run_two_phase(
            texts,
            first=first,
            llm=llm,
            settings=ExtractionSettings(escalation_budget=0.2),
        )

        assert sorted(first.calls) == sorted(texts)
        assert sorted(llm.calls) == ["0.5", "0.55"]
        assert (report.total, report.eligible, report.escalated) == (10, 4, 2)
        assert report.left_for_gliner == 2
        assert report.lowest_score_left == 0.6

    async def test_escalated_chunk_keeps_its_gliner_span_next_to_the_llm_entity(
        self,
    ) -> None:
        """The LLM entity comes first, and a GLiNER span the LLM missed is kept."""
        entities, _, _ = await _run_two_phase(
            ["0.6"],
            first=_ScoredExtractor(),
            llm=_LlmExtractor(),
            settings=ExtractionSettings(escalation_budget="all"),
        )

        assert [e.text for e in entities] == ["Grace", "Ada"]

    async def test_chunk_order_of_entities_is_kept(self) -> None:
        """Entities stay in chunk order, whatever order the LLM finishes in."""
        entities, _, _ = await _run_two_phase(
            ["0.6", "0.9", "0.65"],
            first=_ScoredExtractor(),
            llm=_LlmExtractor(),
            settings=ExtractionSettings(escalation_budget="all"),
        )

        assert [e.text for e in entities] == ["Grace", "Ada", "Ada", "Grace", "Ada"]

    async def test_budget_zero_never_calls_the_llm(self) -> None:
        """Budget 0 is GLiNER only, and the report still counts eligible chunks."""
        llm = _LlmExtractor()

        _, _, report = await _run_two_phase(
            ["0.6", "0.65"],
            first=_ScoredExtractor(),
            llm=llm,
            settings=ExtractionSettings(escalation_budget=0.0),
        )

        assert llm.calls == []
        assert (report.eligible, report.escalated, report.left_for_gliner) == (2, 0, 2)

    async def test_no_llm_extractor_means_no_selection(self) -> None:
        """Without an LLM extractor, hybrid degrades to gliner and counts chunks."""
        _, _, report = await _run_two_phase(
            ["0.6", "0.65"],
            first=_ScoredExtractor(),
            llm=None,
            settings=ExtractionSettings(escalation_budget="all"),
        )

        assert (report.mode, report.total, report.eligible, report.escalated) == (
            "gliner",
            2,
            0,
            0,
        )

    async def test_phases_use_their_own_concurrency_limits(self) -> None:
        """Each phase stays within its own extractor's max_concurrency."""
        first, llm = _ScoredExtractor(limit=1), _LlmExtractor(limit=3)

        await _run_two_phase(
            ["0.6"] * 9,
            first=first,
            llm=llm,
            settings=ExtractionSettings(escalation_budget="all"),
        )

        assert first.peak == 1
        assert llm.peak == 3

    async def test_failed_first_extraction_is_not_eligible(self) -> None:
        """A chunk that failed in phase 1 is recorded and never escalated."""

        class _FailsOnce(_ScoredExtractor):
            async def extract(
                self, chunk: Chunk, schema: GraphSchema
            ) -> ExtractionResult:
                if chunk.text == "bad":
                    raise ValueError("boom")
                return await super().extract(chunk, schema)

        llm = _LlmExtractor()

        _, failures, report = await _run_two_phase(
            ["bad", "0.6"],
            first=_FailsOnce(),
            llm=llm,
            settings=ExtractionSettings(escalation_budget="all"),
            error_policy=ErrorPolicy.SKIP,
        )

        assert [f.error_type for f in failures] == ["ValueError"]
        assert llm.calls == ["0.6"]
        assert report.total == 2

    async def test_first_extractor_error_under_raise_stops_before_phase_two(
        self,
    ) -> None:
        """A phase-1 error under RAISE propagates before the LLM runs."""

        class _Boom(_ScoredExtractor):
            async def extract(
                self, chunk: Chunk, schema: GraphSchema
            ) -> ExtractionResult:
                if chunk.text == "bad":
                    raise RuntimeError("first down")
                return await super().extract(chunk, schema)

        llm = _LlmExtractor()

        with pytest.raises(RuntimeError, match="first down"):
            await _run_two_phase(
                ["0.6", "bad"],
                first=_Boom(),
                llm=llm,
                settings=ExtractionSettings(escalation_budget="all"),
            )

        assert llm.calls == []

    async def test_llm_error_keeps_the_first_result_even_under_raise(self) -> None:
        """In hybrid mode an LLM error never aborts, and GLiNER's result stays.

        This is the paid-work case: one exhausted chunk must not discard the
        results of the other chunks, whatever the error policy. Llm mode has no
        first result, so it follows the policy (see the llm tests below).
        """
        entities, failures, report = await _run_two_phase(
            ["0.6", "0.65"],
            first=_ScoredExtractor(),
            llm=_LlmExtractor(raises={"0.6": RuntimeError("llm down")}),
            settings=ExtractionSettings(escalation_budget="all"),
            error_policy=ErrorPolicy.RAISE,
        )

        assert [e.text for e in entities] == ["Ada", "Grace", "Ada"]
        assert [f.error_type for f in failures] == ["RuntimeError"]
        assert (report.escalated, report.failed) == (2, 1)

    async def test_unparsable_answer_keeps_the_first_result(self) -> None:
        """An answer that did not parse raises in the LLM extractor and is kept out."""
        entities, failures, report = await _run_two_phase(
            ["0.6"],
            first=_ScoredExtractor(),
            llm=_LlmExtractor(raises={"0.6": _UnparsableAnswerError("not json")}),
            settings=ExtractionSettings(escalation_budget="all"),
        )

        assert [e.text for e in entities] == ["Ada"]
        assert [f.error_type for f in failures] == ["_UnparsableAnswerError"]
        assert report.failed == 1

    async def test_parsed_empty_answer_keeps_a_first_result_with_entities(
        self,
    ) -> None:
        """An empty parsed answer does not wipe out entities GLiNER found."""
        entities, failures, report = await _run_two_phase(
            ["0.6"],
            first=_ScoredExtractor(),
            llm=_LlmExtractor(empty={"0.6"}),
            settings=ExtractionSettings(escalation_budget="all"),
        )

        assert [e.text for e in entities] == ["Ada"]
        assert failures == []
        assert (report.escalated, report.failed) == (1, 1)

    async def test_parsed_empty_answer_replaces_an_empty_first_result(self) -> None:
        """When GLiNER found nothing, an empty answer is accepted and not a failure."""
        text = "none one two three four five six seven eight nine"

        entities, failures, report = await _run_two_phase(
            [text],
            first=_ScoredExtractor(),
            llm=_LlmExtractor(empty={text}),
            settings=ExtractionSettings(escalation_budget="all"),
        )

        assert entities == []
        assert failures == []
        assert (report.eligible, report.escalated, report.failed) == (1, 1, 0)

    async def test_report_carries_wall_time_for_each_phase(self) -> None:
        """Both phases report wall time, and calls equal total and escalated."""
        _, _, report = await _run_two_phase(
            ["0.6", "0.9"],
            first=_ScoredExtractor(),
            llm=_LlmExtractor(),
            settings=ExtractionSettings(escalation_budget="all"),
        )

        assert report.primary_seconds > 0
        assert report.escalation_seconds > 0
        assert (report.total, report.escalated) == (2, 1)

    async def test_llm_receives_the_kept_entities_as_candidates(self) -> None:
        """Phase 2 passes the chunk's kept GLiNER entities to the LLM extractor."""
        llm = _LlmExtractor()

        await _run_two_phase(
            ["0.6"],
            first=_ScoredExtractor(),
            llm=llm,
            settings=ExtractionSettings(escalation_budget="all"),
        )

        assert llm.seen == [["Ada"]]

    async def test_zero_yield_chunk_is_sent_without_candidates(self) -> None:
        """A chunk with no GLiNER entities reaches the LLM with an empty list."""
        text = "none one two three four five six seven eight nine"
        llm = _LlmExtractor()

        await _run_two_phase(
            [text],
            first=_ScoredExtractor(),
            llm=llm,
            settings=ExtractionSettings(escalation_budget="all"),
        )

        assert llm.seen == [[]]

    async def test_confirmed_candidate_keeps_gliner_span_and_confidence(self) -> None:
        """An LLM entity with a candidate's name takes its confidence and span."""
        entities, _, report = await _run_two_phase(
            ["0.6"],
            first=_ScoredExtractor(),
            llm=_LlmExtractor(echo=True, label="Organization"),
            settings=ExtractionSettings(escalation_budget="all"),
        )

        (entity,) = entities
        assert (entity.label, entity.confidence) == ("Organization", 0.6)
        assert (entity.char_start, entity.char_end) == (0, 3)
        assert report.failed == 0

    async def test_llm_label_outside_the_schema_is_validated_away(self) -> None:
        """A bad LLM label is dropped, so the answer is empty and GLiNER stays."""
        entities, failures, report = await _run_two_phase(
            ["0.6"],
            first=_ScoredExtractor(),
            llm=_LlmExtractor(label="Spaceship"),
            settings=ExtractionSettings(escalation_budget="all"),
        )

        assert [e.text for e in entities] == ["Ada"]
        assert failures == []
        assert report.failed == 1

    async def test_spans_name_the_phase(self) -> None:
        """Each extract_chunk span names its phase; one escalate span wraps phase 2."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        doc = _doc(key="spans")
        chunks = [_chunk(doc, index=0, text="0.6"), _chunk(doc, index=1, text="0.9")]

        await extract_chunks(
            chunks,
            start_index=0,
            extractor=_ScoredExtractor(),
            schema=DEFAULT_SCHEMA,
            error_policy=ErrorPolicy.RAISE,
            settings=ExtractionSettings(escalation_budget="all"),
            llm_extractor=_LlmExtractor(),
            tracer=provider.get_tracer("test"),
        )

        spans = exporter.get_finished_spans()
        phases = sorted(
            (s.attributes or {})["agrag.extraction.phase"]
            for s in spans
            if s.name == "agrag.extraction.extract_chunk"
        )
        (escalate,) = [s for s in spans if s.name == "agrag.extraction.escalate"]
        assert phases == ["escalation", "primary", "primary"]
        assert (escalate.attributes or {})["agrag.chunks_total"] == 2
        assert (escalate.attributes or {})["agrag.chunks_eligible"] == 1
        assert (escalate.attributes or {})["agrag.chunks_escalated"] == 1


class TestExtractChunksModes:
    """extract_chunks() runs only the phases that the effective mode names."""

    async def test_gliner_mode_never_calls_the_llm(self) -> None:
        """Gliner mode reads every chunk with GLiNER and never calls the LLM."""
        first, llm = _ScoredExtractor(), _LlmExtractor()
        texts = ["0.6", "0.9"]

        _, _, report = await _run_two_phase(
            texts,
            first=first,
            llm=llm,
            settings=ExtractionSettings(mode="gliner", escalation_budget="all"),
        )

        assert sorted(first.calls) == sorted(texts)
        assert llm.calls == []
        assert (report.mode, report.escalated, report.skipped_short) == ("gliner", 0, 0)

    async def test_llm_mode_never_calls_the_first_extractor(self) -> None:
        """Llm mode skips GLiNER and sends each long chunk with no candidates."""
        first, llm = _ScoredExtractor(), _LlmExtractor()

        entities, failures, report = await _run_two_phase(
            ["one two three", "short"],
            first=first,
            llm=llm,
            settings=ExtractionSettings(mode="llm", min_escalation_words=3),
        )

        assert first.calls == []
        assert llm.calls == ["one two three"]
        assert llm.seen == [[]]
        assert [e.text for e in entities] == ["Grace"]
        assert failures == []
        assert (report.mode, report.total, report.skipped_short) == ("llm", 2, 1)
        assert (report.eligible, report.escalated) == (0, 1)

    async def test_llm_mode_ignores_the_budget(self) -> None:
        """Llm mode sends every long chunk even when the budget is zero."""
        llm = _LlmExtractor()

        _, _, report = await _run_two_phase(
            ["one two three"],
            first=_ScoredExtractor(),
            llm=llm,
            settings=ExtractionSettings(
                mode="llm", min_escalation_words=3, escalation_budget=0.0
            ),
        )

        assert llm.calls == ["one two three"]
        assert report.escalated == 1

    async def test_llm_mode_without_an_llm_extractor_raises(self) -> None:
        """Llm mode cannot run without an LLM extractor and says so."""
        with pytest.raises(ValueError, match="llm_extractor"):
            await _run_two_phase(
                ["one two three"],
                first=_ScoredExtractor(),
                llm=None,
                settings=ExtractionSettings(mode="llm", min_escalation_words=3),
            )

    async def test_llm_empty_answer_is_a_valid_empty_result(self) -> None:
        """Llm mode counts a parsed empty answer as no failure."""
        entities, failures, report = await _run_two_phase(
            ["one two three"],
            first=_ScoredExtractor(),
            llm=_LlmExtractor(empty={"one two three"}),
            settings=ExtractionSettings(mode="llm", min_escalation_words=3),
        )

        assert entities == []
        assert failures == []
        assert report.failed == 0

    async def test_llm_error_under_raise_stops_the_batch(self) -> None:
        """Llm mode under RAISE propagates the LLM error."""
        with pytest.raises(RuntimeError, match="llm down"):
            await _run_two_phase(
                ["one two three"],
                first=_ScoredExtractor(),
                llm=_LlmExtractor(raises={"one two three": RuntimeError("llm down")}),
                settings=ExtractionSettings(mode="llm", min_escalation_words=3),
                error_policy=ErrorPolicy.RAISE,
            )

    @pytest.mark.parametrize("policy", [ErrorPolicy.SKIP, ErrorPolicy.QUARANTINE])
    async def test_llm_error_is_recorded_and_counted_failed(
        self, policy: ErrorPolicy
    ) -> None:
        """Llm mode under SKIP or QUARANTINE records the error and counts it failed."""
        entities, failures, report = await _run_two_phase(
            ["one two three", "four five six"],
            first=_ScoredExtractor(),
            llm=_LlmExtractor(raises={"one two three": RuntimeError("llm down")}),
            settings=ExtractionSettings(mode="llm", min_escalation_words=3),
            error_policy=policy,
        )

        assert [f.error_type for f in failures] == ["RuntimeError"]
        assert [e.text for e in entities] == ["Grace"]
        assert (report.failed, report.escalated) == (1, 2)


class _RecordingEmbedder(Embedder):
    """Fake embedder that records the texts it was asked to embed."""

    model = "fake"

    def __init__(self) -> None:
        self.texts: list[str] = []

    async def dimensions(self) -> int:
        """Return a small fixed dimension."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Record the texts and return a zero vector per text."""
        self.texts.extend(texts)
        return [[0.0] * 4 for _ in texts]


class TestEmbedChunksStage:
    """Chunk embedding covers the chunks the graph holds after the node write."""

    @staticmethod
    async def _embed(
        chunks: list[Chunk], store: AsyncMock, writes: WriteOutcome
    ) -> tuple[list[str], list[StageFailure]]:
        embedder = _RecordingEmbedder()
        result = await embed_chunks_stage(
            chunks,
            {chunk.id for chunk in chunks if chunk.id is not None},
            writes,
            StageContext(
                graph_store=store,
                embedder=embedder,
                error_policy=ErrorPolicy.SKIP,
                tracer=get_tracer(None),
                job_id=None,
                deferred=None,
            ),
            embed_heading_path=False,
        )
        return embedder.texts, result.failures

    async def test_skips_chunks_whose_node_write_failed(self) -> None:
        """A chunk the node write reported as failed is not embedded."""
        document = _doc(key="a")
        failed, landed = (
            _chunk(document, text="failed"),
            _chunk(document, text="landed"),
        )
        writes = WriteOutcome(failed_ids={failed.id}, wrote_any=True)

        texts, failures = await self._embed([failed, landed], _store()[0], writes)

        assert texts == ["landed"]
        assert failures == []

    async def test_embeds_only_chunks_the_graph_holds_when_nothing_was_written(
        self,
    ) -> None:
        """With no node write sent, the graph read decides which chunks landed."""
        document = _doc(key="a")
        landed = _chunk(document, text="landed")
        missing = _chunk(document, text="missing")
        store, _ = _store()
        store.execute_read.return_value = [{"n": {"id": str(landed.id)}}]

        texts, _ = await self._embed(
            [landed, missing], store, WriteOutcome(wrote_any=False)
        )

        assert texts == ["landed"]

    @staticmethod
    def _context(store: AsyncMock, error_policy: ErrorPolicy) -> StageContext:
        return StageContext(
            graph_store=store,
            embedder=_RecordingEmbedder(),
            error_policy=error_policy,
            tracer=get_tracer(None),
            job_id=None,
            deferred=None,
        )

    async def test_failed_chunk_lookup_skips_embedding_under_skip(self) -> None:
        """A failed read records a failure and embeds nothing under SKIP."""
        chunk = _chunk(_doc(key="a"), text="unread")
        store = AsyncMock()
        store.execute_read.side_effect = RuntimeError("read unavailable")

        result = await embed_chunks_stage(
            [chunk],
            {chunk.id},
            WriteOutcome(wrote_any=False),
            self._context(store, ErrorPolicy.SKIP),
            embed_heading_path=False,
        )

        assert [failure.item_id for failure in result.failures] == ["chunk_lookup"]
        store.execute_write.assert_not_called()

    async def test_failed_chunk_lookup_raises_under_raise(self) -> None:
        """A failed read propagates under RAISE instead of skipping the embed."""
        chunk = _chunk(_doc(key="a"), text="unread")
        store = AsyncMock()
        store.execute_read.side_effect = RuntimeError("read unavailable")

        with pytest.raises(RuntimeError, match="read unavailable"):
            await embed_chunks_stage(
                [chunk],
                {chunk.id},
                WriteOutcome(wrote_any=False),
                self._context(store, ErrorPolicy.RAISE),
                embed_heading_path=False,
            )
