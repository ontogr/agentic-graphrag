"""Graph writes of one ingestion batch, with each failure named by its write.

Node writes run in parallel. Each write returns its own outcome, so a failure
is reported under the name of the write that raised it. Relation writes run
after the nodes they link exist.
"""

import asyncio
from dataclasses import dataclass, field
from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.document import DOCUMENT_LABEL
from agrag.common.data_models.graph_record import (
    NodeRecord,
    RelationRecord,
    UpsertResult,
)
from agrag.common.data_models.stage_failure import StageFailure
from agrag.common.data_models.structure import (
    FIGURE_LABEL,
    SECTION_LABEL,
    SOURCE_LABEL,
    TABLE_LABEL,
)
from agrag.graphdb.base import GraphStore
from agrag.ingestion._structure import StructureRecords
from agrag.loaders.types import ErrorPolicy
from agrag.observability import record_stage_failure, stage_failure_context


@dataclass
class WriteOutcome:
    """The result of one graph write.

    Attributes:
        written: The number of records the store reports as written.
        failures: The per-record failures and the failures of the whole write.
        failed_ids: The ids of the chunk nodes the store rejected.
        wrote_any: Whether the write sent any record to the store.
    """

    written: int = 0
    failures: list[StageFailure] = field(default_factory=list)
    failed_ids: set[UUID] = field(default_factory=set)
    wrote_any: bool = False


@dataclass
class NodeWrites:
    """The outcome of each node write in one batch, by the records it wrote.

    Attributes:
        chunks: The Chunk nodes.
        structure: The Section, Table, Figure and Source nodes.
        documents: The Document nodes.
    """

    chunks: WriteOutcome = field(default_factory=WriteOutcome)
    structure: WriteOutcome = field(default_factory=WriteOutcome)
    documents: WriteOutcome = field(default_factory=WriteOutcome)

    @property
    def written(self) -> int:
        """Return the number of nodes written by all three writes."""
        return self.chunks.written + self.structure.written + self.documents.written

    @property
    def failures(self) -> list[StageFailure]:
        """Return the failures of all three writes, chunks first."""
        return [
            *self.chunks.failures,
            *self.structure.failures,
            *self.documents.failures,
        ]


def upsert_stage_failures(result: UpsertResult) -> list[StageFailure]:
    """Convert isolated graph-store failures into ingestion stage failures."""
    trace_id, span_id = stage_failure_context()
    return [
        StageFailure(
            item_id=failure.id,
            error_type=failure.error_type,
            error_message=failure.error_message,
            trace_id=trace_id,
            span_id=span_id,
        )
        for failure in result.failures
    ]


async def write_nodes(
    graph_store: GraphStore,
    *,
    chunk_records: list[NodeRecord],
    structure: StructureRecords,
    document_records: list[NodeRecord],
    error_policy: ErrorPolicy,
    pending_job_id: UUID | None,
    tracer: Tracer,
) -> NodeWrites:
    """Write the chunk, structure and document nodes of one batch.

    Every write finishes before this returns, even when one of them fails. The
    error policy then decides: ``RAISE`` re-raises the first failure in the order
    chunks, structure, documents, and any other policy records it as a failure
    named after the write.

    Args:
        graph_store: The store to write to.
        chunk_records: The Chunk node records. Empty when the batch has no chunks.
        structure: The structure records of the batch's documents.
        document_records: The Document node records.
        error_policy: How a failed write is reported.
        pending_job_id: The cutover job the writes belong to, if any.
        tracer: Opens one span for each write.

    Returns:
        The outcome of each write.

    Raises:
        Exception: The first failed write, when ``error_policy`` is ``RAISE``.
    """
    chunks, structure_outcome, documents = await asyncio.gather(
        _write_chunk_nodes(graph_store, chunk_records, pending_job_id, tracer),
        _write_structure_nodes(graph_store, structure, pending_job_id, tracer),
        _write_document_nodes(graph_store, document_records, pending_job_id, tracer),
        return_exceptions=True,
    )
    return NodeWrites(
        chunks=_settle("chunks", chunks, error_policy),
        structure=_settle("structure", structure_outcome, error_policy),
        documents=_settle("documents", documents, error_policy),
    )


async def write_relations(
    graph_store: GraphStore,
    records: list[RelationRecord],
    *,
    item_id: str,
    span_name: str,
    error_policy: ErrorPolicy,
    pending_job_id: UUID | None,
    tracer: Tracer,
) -> WriteOutcome:
    """Write one batch of relation records under the error policy.

    Args:
        graph_store: The store to write to.
        records: The relation records. An empty list writes nothing.
        item_id: The name a failure of this write is recorded under.
        span_name: The name of the span that covers this write.
        error_policy: How a failed write is reported.
        pending_job_id: The cutover job the write belongs to, if any.
        tracer: Opens the span.

    Returns:
        The number of relations written and any failure.

    Raises:
        Exception: The write failed and ``error_policy`` is ``RAISE``.
    """
    with tracer.start_as_current_span(
        span_name, attributes={"agrag.record_count": len(records)}
    ) as span:
        try:
            if not records:
                return WriteOutcome()
            write_result = await graph_store.upsert_relations(
                records, pending_job_id=pending_job_id
            )
            span.set_attribute("agrag.relationships_written", write_result.written)
            return WriteOutcome(
                written=write_result.written,
                failures=upsert_stage_failures(write_result),
            )
        except Exception as exc:  # noqa: BLE001
            if error_policy is ErrorPolicy.RAISE:
                raise
            return WriteOutcome(failures=[_failure(item_id, exc)])


def _settle(
    item_id: str,
    outcome: WriteOutcome | BaseException,
    error_policy: ErrorPolicy,
) -> WriteOutcome:
    if not isinstance(outcome, BaseException):
        return outcome
    if error_policy is ErrorPolicy.RAISE or not isinstance(outcome, Exception):
        raise outcome
    return WriteOutcome(failures=[_failure(item_id, outcome)])


def _failure(item_id: str, exc: Exception) -> StageFailure:
    trace_id, span_id = record_stage_failure(exc)
    return StageFailure(
        item_id=item_id,
        error_type=type(exc).__name__,
        error_message=str(exc),
        trace_id=trace_id,
        span_id=span_id,
    )


async def _write_chunk_nodes(
    graph_store: GraphStore,
    chunk_records: list[NodeRecord],
    pending_job_id: UUID | None,
    tracer: Tracer,
) -> WriteOutcome:
    with tracer.start_as_current_span(
        "agrag.storage.upsert_chunks",
        attributes={"agrag.record_count": len(chunk_records)},
    ) as span:
        if not chunk_records:
            return WriteOutcome()
        write_result = await graph_store.upsert_nodes(
            CHUNK_LABEL, chunk_records, pending_job_id=pending_job_id
        )
        failed_ids: set[UUID] = set()
        for failure in write_result.failures:
            try:
                failed_ids.add(UUID(failure.id))
            except ValueError:
                continue
        span.set_attribute("agrag.nodes_written", write_result.written)
        return WriteOutcome(
            written=write_result.written,
            failures=upsert_stage_failures(write_result),
            failed_ids=failed_ids,
            wrote_any=True,
        )


async def _write_structure_nodes(
    graph_store: GraphStore,
    structure: StructureRecords,
    pending_job_id: UUID | None,
    tracer: Tracer,
) -> WriteOutcome:
    with tracer.start_as_current_span(
        "agrag.storage.upsert_structure",
        attributes={"agrag.record_count": structure.node_count},
    ) as span:
        written = 0
        failures: list[StageFailure] = []
        for result in await _write_structure_labels(
            graph_store, structure, pending_job_id
        ):
            written += result.written
            failures.extend(upsert_stage_failures(result))
        span.set_attribute("agrag.nodes_written", written)
        return WriteOutcome(written=written, failures=failures)


async def _write_document_nodes(
    graph_store: GraphStore,
    document_records: list[NodeRecord],
    pending_job_id: UUID | None,
    tracer: Tracer,
) -> WriteOutcome:
    with tracer.start_as_current_span(
        "agrag.storage.upsert_documents",
        attributes={"agrag.record_count": len(document_records)},
    ) as span:
        if not document_records:
            return WriteOutcome()
        result = await graph_store.upsert_nodes(
            DOCUMENT_LABEL, document_records, pending_job_id=pending_job_id
        )
        span.set_attribute("agrag.nodes_written", result.written)
        return WriteOutcome(
            written=result.written, failures=upsert_stage_failures(result)
        )


async def _write_structure_labels(
    graph_store: GraphStore,
    structure: StructureRecords,
    pending_job_id: UUID | None,
) -> list[UpsertResult]:
    # Each label is its own write. gather waits for all of them before the first
    # failure is raised, so no sibling write is cut off partway.
    pending: list[tuple[str, list[NodeRecord]]] = [
        (label, records)
        for label, records in (
            (SECTION_LABEL, structure.sections),
            (TABLE_LABEL, structure.tables),
            (FIGURE_LABEL, structure.figures),
            (SOURCE_LABEL, structure.sources),
        )
        if records
    ]
    outcomes = await asyncio.gather(
        *(
            graph_store.upsert_nodes(label, records, pending_job_id=pending_job_id)
            for label, records in pending
        ),
        return_exceptions=True,
    )
    for outcome in outcomes:
        if isinstance(outcome, BaseException):
            raise outcome
    return [outcome for outcome in outcomes if not isinstance(outcome, BaseException)]
