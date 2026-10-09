"""Tests for the graph writes of one batch and how their failures are named.

A failed write is reported under the name of the write that raised it, and the
error policy decides whether it raises or is recorded. The empty-chunk path uses
the same writes, so it follows the same policy.
"""

from collections.abc import Sequence
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agrag.common.data_models.document import (
    DOCUMENT_LABEL,
    Document,
    DocumentFamily,
    SourceFormat,
)
from agrag.common.data_models.graph_record import (
    NodeRecord,
    RelationRecord,
    UpsertFailure,
    UpsertResult,
)
from agrag.common.data_models.graph_schema import GENERIC
from agrag.common.data_models.structure import (
    FIGURE_LABEL,
    SECTION_LABEL,
    TABLE_LABEL,
)
from agrag.ingestion._ingest_pipeline import ingest_chunks
from agrag.ingestion._storage import write_nodes, write_relations
from agrag.ingestion._structure import StructureRecords
from agrag.ingestion.stats import IngestStats
from agrag.loaders.types import ErrorPolicy
from agrag.observability import get_tracer
from agrag.retrieval.settings import RetrievalSettings


def _node(label: str) -> NodeRecord:
    return NodeRecord(id=uuid4(), labels=[label], properties={})


def _relation() -> RelationRecord:
    return RelationRecord(
        id=uuid4(), type="PART_OF", start_id=uuid4(), end_id=uuid4(), properties={}
    )


def _store_failing_on(*labels: str) -> AsyncMock:
    """Build a store whose node writes for the given labels raise."""
    store = AsyncMock()

    async def _upsert_nodes(
        node_label: str, records: Sequence[Any], **kwargs: Any
    ) -> UpsertResult:
        if node_label in labels:
            raise RuntimeError(f"{node_label} write failed")
        return UpsertResult(written=len(records))

    store.upsert_nodes.side_effect = _upsert_nodes
    store.upsert_relations.return_value = UpsertResult()
    store.execute_read.return_value = []
    return store


async def _write(store: AsyncMock, error_policy: ErrorPolicy) -> Any:
    return await write_nodes(
        store,
        chunk_records=[_node("Chunk")],
        structure=StructureRecords(),
        document_records=[_node(DOCUMENT_LABEL)],
        error_policy=error_policy,
        pending_job_id=None,
        tracer=get_tracer(None),
    )


class TestWriteNodes:
    """Each node write reports its own failure under its own name."""

    async def test_a_failed_chunk_write_is_named_chunks(self) -> None:
        """Only the chunk write fails, and the document write still lands."""
        store = _store_failing_on("Chunk")

        writes = await _write(store, ErrorPolicy.SKIP)

        assert [failure.item_id for failure in writes.failures] == ["chunks"]
        assert writes.documents.written == 1

    async def test_a_failed_document_write_is_named_documents(self) -> None:
        """A failed document write is recorded under documents."""
        store = _store_failing_on(DOCUMENT_LABEL)

        writes = await _write(store, ErrorPolicy.SKIP)

        assert [failure.item_id for failure in writes.failures] == ["documents"]
        assert writes.chunks.written == 1

    async def test_a_failed_write_raises_under_raise_policy(self) -> None:
        """RAISE re-raises the failure instead of recording it."""
        store = _store_failing_on(DOCUMENT_LABEL)

        with pytest.raises(RuntimeError, match="Document write failed"):
            await _write(store, ErrorPolicy.RAISE)

    async def test_every_write_finishes_before_the_first_failure_raises(
        self,
    ) -> None:
        """A failed chunk write does not cancel the document write."""
        store = _store_failing_on("Chunk")

        with pytest.raises(RuntimeError, match="Chunk write failed"):
            await _write(store, ErrorPolicy.RAISE)

        labels = [call.args[0] for call in store.upsert_nodes.await_args_list]
        assert DOCUMENT_LABEL in labels


class TestWriteStructureLabels:
    """Each structure label reports its own failure under its own name."""

    @staticmethod
    async def _write_structure(store: AsyncMock, error_policy: ErrorPolicy) -> Any:
        structure = StructureRecords(
            sections=[_node(SECTION_LABEL)],
            tables=[_node(TABLE_LABEL)],
            figures=[_node(FIGURE_LABEL)],
        )
        return await write_nodes(
            store,
            chunk_records=[],
            structure=structure,
            document_records=[],
            error_policy=error_policy,
            pending_job_id=None,
            tracer=get_tracer(None),
        )

    async def test_a_failed_label_is_named_by_its_label_and_others_still_count(
        self,
    ) -> None:
        """Under SKIP the failed label is named, and the other labels' counts stay."""
        store = _store_failing_on(TABLE_LABEL)

        writes = await self._write_structure(store, ErrorPolicy.SKIP)

        assert [failure.item_id for failure in writes.structure.failures] == [
            TABLE_LABEL
        ]
        assert writes.structure.written == 2

    async def test_raise_reraises_the_first_failed_label_after_all_writes(
        self,
    ) -> None:
        """RAISE waits for every label, then re-raises the first failure in order."""
        store = _store_failing_on(SECTION_LABEL, FIGURE_LABEL)

        with pytest.raises(RuntimeError, match="Section write failed"):
            await self._write_structure(store, ErrorPolicy.RAISE)

        labels = [call.args[0] for call in store.upsert_nodes.await_args_list]
        assert TABLE_LABEL in labels
        assert FIGURE_LABEL in labels


class TestWriteRelations:
    """A relation write reports one failure under the name it is given."""

    async def test_a_failed_relation_write_is_named_by_the_caller(self) -> None:
        """The failure carries the item id the caller passed."""
        store = AsyncMock()
        store.upsert_relations.side_effect = RuntimeError("edge write failed")

        outcome = await write_relations(
            store,
            [_relation()],
            item_id="MENTIONED_IN",
            span_name="agrag.storage.upsert_mentioned_in",
            error_policy=ErrorPolicy.SKIP,
            pending_job_id=None,
            tracer=get_tracer(None),
        )

        assert [failure.item_id for failure in outcome.failures] == ["MENTIONED_IN"]

    async def test_a_failed_relation_write_raises_under_raise_policy(self) -> None:
        """RAISE propagates the relation failure."""
        store = AsyncMock()
        store.upsert_relations.side_effect = RuntimeError("edge write failed")

        with pytest.raises(RuntimeError, match="edge write failed"):
            await write_relations(
                store,
                [_relation()],
                item_id="relations",
                span_name="agrag.storage.upsert_relations",
                error_policy=ErrorPolicy.RAISE,
                pending_job_id=None,
                tracer=get_tracer(None),
            )


class TestEmptyChunkWrites:
    """A batch with no chunks writes its documents under the error policy."""

    @staticmethod
    def _document() -> Document:
        text = "hello"
        return Document(
            text=text,
            title="t",
            uri="empty.txt",
            document_key="empty.txt",
            source_format=SourceFormat.TXT,
            family=DocumentFamily.PROSE,
            content_hash="hash-empty",
            loader_name="text",
            char_count=len(text),
            line_count=1,
        )

    async def _ingest_empty(self, store: AsyncMock, error_policy: ErrorPolicy) -> Any:
        batch = await ingest_chunks(
            [],
            [self._document()],
            [],
            [],
            [],
            graph_store=store,
            embedder=AsyncMock(),
            vector_store=None,
            graph_schema=GENERIC,
            retrieval_settings=RetrievalSettings(),
            error_policy=error_policy,
            ingestion=IngestStats(documents=1),
            placements={},
        )
        return batch.add_result

    async def test_a_failed_document_write_is_recorded_under_skip(self) -> None:
        """Under SKIP the document failure becomes a storage failure."""
        store = _store_failing_on(DOCUMENT_LABEL)

        result = await self._ingest_empty(store, ErrorPolicy.SKIP)

        assert [failure.item_id for failure in result.storage.failures] == ["documents"]

    async def test_a_failed_document_write_raises_under_raise(self) -> None:
        """Under RAISE the document failure propagates."""
        store = _store_failing_on(DOCUMENT_LABEL)

        with pytest.raises(RuntimeError, match="Document write failed"):
            await self._ingest_empty(store, ErrorPolicy.RAISE)

    async def test_a_reported_document_failure_is_kept_as_a_failure(self) -> None:
        """A failure the store reports for one document shows as a storage failure."""
        store = AsyncMock()
        store.upsert_nodes.return_value = UpsertResult(
            failures=[UpsertFailure(id="d", error_type="WriteError", error_message="x")]
        )

        result = await self._ingest_empty(store, ErrorPolicy.SKIP)

        assert [failure.item_id for failure in result.storage.failures] == ["d"]
