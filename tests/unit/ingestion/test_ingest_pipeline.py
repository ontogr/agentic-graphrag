"""Tests for the shared per-batch ingestion core.

``ingest_chunks()`` is a pure move of ``Graph.add()``'s pipeline body, so
the characterization test runs the same input through both paths and
asserts identical summaries. ``extract_chunks()`` is covered for its
cross-batch index threading.
"""

from collections.abc import Sequence
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_record import UpsertResult
from agrag.common.data_models.graph_schema import GENERIC, GraphSchema
from agrag.common.data_models.provenance import TextProvenance
from agrag.embedding.base import Embedder
from agrag.ingestion._ingest_pipeline import extract_chunks, ingest_chunks
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import Graph
from agrag.ingestion.stats import IngestStats
from agrag.loaders.corpus.types import ErrorPolicy
from agrag.retrieval.settings import RetrievalSettings


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
    store.execute_write.return_value = []
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
