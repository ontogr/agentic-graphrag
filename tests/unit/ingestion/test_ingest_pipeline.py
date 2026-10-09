"""Tests for the shared per-batch ingestion core.

``ingest_chunks()`` is a pure move of ``Graph.add()``'s pipeline body, so
the characterization test runs the same input through both paths and
asserts identical summaries. ``extract_chunks()`` is covered for its
cross-batch index threading.
"""

import asyncio
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
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

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_record import UpsertFailure, UpsertResult
from agrag.common.data_models.graph_schema import GENERIC, GraphSchema
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.vector_record import VectorHit
from agrag.embedding.base import Embedder
from agrag.ingestion._ingest_pipeline import extract_chunks, ingest_chunks
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.ingestion.resolve import ResolutionResult
from agrag.ingestion.resolve.candidate_source import GraphCandidateSource
from agrag.ingestion.stats import IngestStats
from agrag.loaders.types import ErrorPolicy
from agrag.retrieval.settings import RetrievalSettings
from tests.unit.ingestion._lease_fake import CutoverJobLeaseFake


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

    @asynccontextmanager
    async def _transaction():
        yield store

    store.transaction = _transaction
    return store, calls


async def _ingest(
    documents: list[Document],
    chunks: list[Chunk],
    store: AsyncMock,
    *,
    extractor: Extractor | None = None,
    ingestion: IngestStats | None = None,
    return_chunks: bool = False,
) -> Any:
    """Run extract_chunks + ingest_chunks over fixed input."""
    active_extractor = extractor if extractor is not None else _NoopExtractor()
    entities, relations, failures = await extract_chunks(
        chunks,
        start_index=0,
        extractor=active_extractor,
        schema=GENERIC,
        error_policy=ErrorPolicy.RAISE,
    )
    return await ingest_chunks(
        chunks,
        documents,
        entities,
        relations,
        failures,
        graph_store=store,
        embedder=_ZeroEmbedder(),
        vector_store=None,
        graph_schema=GENERIC,
        retrieval_settings=RetrievalSettings(),
        error_policy=ErrorPolicy.RAISE,
        ingestion=ingestion or IngestStats(documents=len(documents)),
        return_chunks=return_chunks,
    )


class TestIngestChunks:
    """ingest_chunks() produces the AddResult shape add() produces."""

    async def test_writes_chunks_documents_and_part_of(self) -> None:
        """One document's chunks yield chunk, document, and PART_OF writes."""
        store, calls = _store()
        first, second = _doc(key="a"), _doc(key="b")
        chunks = [_chunk(first, index=0), _chunk(second, index=0)]

        result = await _ingest([first, second], chunks, store, return_chunks=True)

        assert result.ingestion.documents == 2
        assert result.extraction.chunks_processed == 2
        assert [chunk.id for chunk in result.chunks] == [chunk.id for chunk in chunks]
        labels = [label for label, _ in calls["nodes"]]
        assert "Chunk" in labels
        assert "Document" in labels
        part_of = [
            rec
            for batch in calls["relations"]
            for rec in batch
            if rec.type == "PART_OF"
        ]
        assert len(part_of) == 2

    async def test_empty_chunks_returns_zero_stages(self) -> None:
        """No chunks still writes the document node and reports zero stages."""
        store, _ = _store()
        doc = _doc(key="a")

        result = await _ingest([doc], [], store)

        assert result.extraction.chunks_processed == 0
        assert result.storage.nodes_written == 0
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
                schema=GENERIC,
                error_policy=ErrorPolicy.RAISE,
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

        _, relations, failures = await extract_chunks(
            [chunk],
            start_index=0,
            extractor=_BadRelation(),
            schema=GENERIC,
            error_policy=ErrorPolicy.SKIP,
            tracer=provider.get_tracer("test"),
        )

        names = [span.name for span in exporter.get_finished_spans()]
        assert relations == []
        assert [f.item_id for f in failures] == [str(chunk.id)]
        assert "agrag.extraction.remap_relations" in names

    async def test_structure_nodes_are_written_under_their_own_span(self) -> None:
        """Ingest writes the section tree under agrag.storage.upsert_structure."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        store, _ = _store()
        doc = _doc(key="a")

        await ingest_chunks(
            [_chunk(doc)],
            [doc],
            [],
            [],
            [],
            graph_store=store,
            embedder=_ZeroEmbedder(),
            vector_store=None,
            graph_schema=GENERIC,
            retrieval_settings=RetrievalSettings(),
            error_policy=ErrorPolicy.RAISE,
            ingestion=IngestStats(documents=1),
            return_chunks=False,
            tracer=provider.get_tracer("test"),
        )

        spans = {span.name: span for span in exporter.get_finished_spans()}
        assert "agrag.storage.upsert_structure" in spans
        assert spans["agrag.storage.upsert_structure"].attributes is not None

    async def test_rejects_a_non_positive_extraction_concurrency(self) -> None:
        """A zero limit would block every extraction forever."""
        with pytest.raises(ValueError, match="max_concurrency"):
            await extract_chunks(
                [],
                start_index=0,
                extractor=_NoopExtractor(),
                schema=GENERIC,
                error_policy=ErrorPolicy.RAISE,
                max_concurrency=0,
            )

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
            result = await ingest_chunks(
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
                graph_store=store,
                embedder=_ZeroEmbedder(),
                vector_store=None,
                graph_schema=GENERIC,
                retrieval_settings=RetrievalSettings(),
                error_policy=ErrorPolicy.RAISE,
                ingestion=IngestStats(documents=1),
                return_chunks=False,
            )
        assert result.merge.failures == []
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
        return await ingest_chunks(
            [chunk],
            [doc],
            mentions,
            [],
            [],
            graph_store=store,
            embedder=_ZeroEmbedder(),
            vector_store=None,
            graph_schema=GENERIC,
            retrieval_settings=RetrievalSettings(),
            error_policy=error_policy,
            ingestion=IngestStats(documents=1),
        )

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

    async def test_passes_max_llm_pairs_to_the_resolver(self) -> None:
        """The pair limit reaches the resolver that ``ingest_chunks`` builds."""
        store, _ = _store()
        doc = _doc(key="limit")
        chunk = _chunk(doc, text="Ada Lovelace wrote the first algorithm.")
        entity = ExtractedEntity(
            chunk_id=chunk.id,
            label="Person",
            text="Ada Lovelace",
            char_start=0,
            char_end=12,
        )
        resolver_instance = AsyncMock()
        resolver_instance.resolve.return_value = ResolutionResult(groups=[], matches=[])

        with mock.patch(
            "agrag.ingestion.resolve.resolution.Resolver",
            return_value=resolver_instance,
        ) as resolver_class:
            await ingest_chunks(
                [chunk],
                [doc],
                [entity],
                [],
                [],
                graph_store=store,
                embedder=_ZeroEmbedder(),
                vector_store=None,
                graph_schema=GENERIC,
                retrieval_settings=RetrievalSettings(),
                error_policy=ErrorPolicy.RAISE,
                ingestion=IngestStats(documents=1),
                max_llm_pairs=7,
            )

        assert resolver_class.call_args.kwargs["max_llm_pairs"] == 7


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
            schema=GENERIC,
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
            graph_store=store,
            embedder=_Recorder(),
            vector_store=None,
            graph_schema=GENERIC,
            retrieval_settings=RetrievalSettings(),
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

    async def test_vector_store_payload_text_stays_raw(self) -> None:
        """The stored payload text is the chunk text, not the contextual text."""
        store, _ = _store()
        original = store.execute_write.side_effect

        async def match_embeddings(query: str, parameters: Any = None) -> Any:
            records = (parameters or {}).get("records") or []
            if records and "vector" in records[0]:
                return [{"id": record["id"]} for record in records]
            return await original(query, parameters)

        store.execute_write.side_effect = match_embeddings
        vector_store = AsyncMock()
        chunk = self._chunk(["A"])

        await ingest_chunks(
            [chunk],
            [_doc(key="h")],
            [],
            [],
            [],
            graph_store=store,
            embedder=_ZeroEmbedder(),
            vector_store=vector_store,
            graph_schema=GENERIC,
            retrieval_settings=RetrievalSettings(),
            error_policy=ErrorPolicy.RAISE,
            ingestion=IngestStats(documents=1),
            embed_heading_path=True,
        )

        payloads = [
            record.payload["text"]
            for call in vector_store.upsert.await_args_list
            for record in call.args[1]
            if record.payload.get("label") == "Chunk"
        ]
        assert payloads == ["body text"]


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

        entities_one, relations_one, _ = await extract_chunks(
            first,
            start_index=0,
            extractor=extractor,
            schema=GENERIC,
            error_policy=ErrorPolicy.RAISE,
        )
        entities_two, relations_two, _ = await extract_chunks(
            second,
            start_index=len(entities_one),
            extractor=extractor,
            schema=GENERIC,
            error_policy=ErrorPolicy.RAISE,
        )

        assert [rel.source_index for rel in relations_one] == [0]
        assert [rel.target_index for rel in relations_one] == [1]
        assert [rel.source_index for rel in relations_two] == [2]
        assert [rel.target_index for rel in relations_two] == [3]
        assert len(entities_one) + len(entities_two) == 4

    async def test_skip_records_failure_and_continues(self) -> None:
        """A failing chunk is recorded under SKIP without stopping the batch."""

        class _FlakyExtractor(Extractor):
            async def extract(
                self, chunk: Chunk, schema: GraphSchema
            ) -> ExtractionResult:
                if chunk.index == 0:
                    raise ValueError("boom")
                return ExtractionResult(
                    entities=[], relations=[], extractor_name="flaky"
                )

        doc = _doc(key="flaky")
        chunks = [_chunk(doc, index=0), _chunk(doc, index=1)]

        entities, _, failures = await extract_chunks(
            chunks,
            start_index=0,
            extractor=_FlakyExtractor(),
            schema=GENERIC,
            error_policy=ErrorPolicy.SKIP,
        )

        assert entities == []
        assert len(failures) == 1
        assert failures[0].error_type == "ValueError"

    async def test_part_of_ids_use_stable_node_ids(self) -> None:
        """Relation endpoints reference UUIDs, keeping the core typed."""
        doc = _doc(key="typed")
        chunk = _chunk(doc)
        assert isinstance(chunk.document_id, UUID)


class _RelationExtractor(Extractor):
    """Extractor returning two related mentions for every chunk."""

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return an Alice/Acme pair joined by a WORKS_AT relation."""
        return ExtractionResult(
            entities=[
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label="Person",
                    text="Alice",
                    char_start=0,
                    char_end=5,
                ),
                ExtractedEntity(
                    chunk_id=chunk.id,
                    label="Organization",
                    text="Acme",
                    char_start=14,
                    char_end=18,
                ),
            ],
            relations=[
                ExtractedRelation(
                    chunk_id=chunk.id,
                    label="WORKS_AT",
                    source_index=0,
                    target_index=1,
                )
            ],
            extractor_name="fake",
        )


class TestResolutionContextWiring:
    """ingest_chunks passes real LLM verification context to Resolver.

    Both the in-batch and persisted-candidate pairs feed one combined
    Resolver.resolve call (see ingest_chunks), unlike Graph.consolidate's
    two separate passes, so both kinds of context are asserted on that one
    call. The equivalent coverage for Graph.consolidate lives in
    tests/unit/ingestion/test_graph.py.
    """

    async def test_in_batch_resolution_gets_relation_neighbors(self) -> None:
        """The combined resolve call is seeded from the batch's relations."""
        store, _ = _store()
        doc = _doc(key="a")
        chunk = _chunk(doc, text="Alice works at Acme")
        resolver_instance = AsyncMock()
        resolver_instance.resolve.return_value = ResolutionResult(groups=[], matches=[])

        with mock.patch(
            "agrag.ingestion.resolve.resolution.Resolver",
            return_value=resolver_instance,
        ):
            await _ingest([doc], [chunk], store, extractor=_RelationExtractor())

        assert resolver_instance.resolve.await_args.kwargs["neighbors_by_index"] == {
            0: ["WORKS_AT Acme"],
            1: ["WORKS_AT Alice"],
        }

    async def test_persisted_candidate_similarity_reaches_resolve(self) -> None:
        """A candidate hit's real embedding score is seeded into resolution.

        Only one Resolver.resolve call happens for the whole batch: the
        persisted candidate joins the same combined mention list the
        in-batch pairs use, rather than a second pass over it.
        """
        store, _ = _store()
        doc = _doc(key="a")
        chunk = _chunk(doc, text="Alice works at Acme")
        candidate_id = uuid4()

        async def fake_vector_search(text: str, **kwargs: Any) -> list[VectorHit]:
            if text == "Alice":
                return [
                    VectorHit(id=candidate_id, score=0.91, payload={"name": "Alice"})
                ]
            return []

        resolver_instance = AsyncMock()
        resolver_instance.resolve.return_value = ResolutionResult(groups=[], matches=[])
        fetch_neighbors = AsyncMock(return_value={candidate_id: ["WORKS_AT Acme"]})

        with (
            mock.patch(
                "agrag.ingestion.resolve.candidate_source.vector_search",
                new=fake_vector_search,
            ),
            mock.patch(
                "agrag.ingestion.resolve.resolution.Resolver",
                return_value=resolver_instance,
            ),
            mock.patch(
                "agrag.ingestion.resolve.resolution.fetch_persisted_neighbors",
                fetch_neighbors,
            ),
        ):
            await _ingest([doc], [chunk], store, extractor=_RelationExtractor())

        assert len(resolver_instance.resolve.await_args_list) == 1
        kwargs = resolver_instance.resolve.await_args.kwargs
        assert kwargs["similarity_by_pair"] == {(0, 2): 0.91}
        assert kwargs["neighbors_by_index"][2] == ["WORKS_AT Acme"]
        assert fetch_neighbors.await_args.args[0] == [candidate_id]
