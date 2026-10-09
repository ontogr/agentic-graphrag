"""Graph writes of one ingestion batch, with each failure named by its write.

Node writes run in parallel. Each write returns its own outcome, so a failure
is reported under the name of the write that raised it. Relation writes run
after the nodes they link exist.
"""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.chunking.chunker import ChunkPlacement
from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.document import DOCUMENT_LABEL, Document
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
from agrag.ingestion._lexical_backbone import (
    build_document_record,
    build_next_chunk_records,
    distinct_documents,
)
from agrag.ingestion._stage_context import StageContext
from agrag.ingestion._structure import StructureRecords, build_document_structure
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
        _write_structure_nodes(
            graph_store, structure, pending_job_id, error_policy, tracer
        ),
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
        except Exception as exc:
            if error_policy is ErrorPolicy.RAISE:
                raise
            return WriteOutcome(failures=[_failure(item_id, exc)])


@dataclass(frozen=True)
class NodeStageResult:
    """The node writes of one batch and the records they were built from.

    Attributes:
        chunk_ids: The ids of the chunks this batch tried to write.
        chunk_writes: The outcome of the Chunk node write.
        nodes_written: The nodes the store reports as written by all writes.
        record_failures: Chunks whose node record could not be built.
        node_failures: The failures of the Chunk, structure and Document writes.
        structure_relation_records: The PART_OF and NEXT_CHUNK edges of this
            batch. They are written with the domain relations.
        structure_node_ids: The Section, Table and Figure ids of this batch.
    """

    chunk_ids: set[UUID]
    chunk_writes: WriteOutcome
    nodes_written: int
    record_failures: list[StageFailure]
    node_failures: list[StageFailure]
    structure_relation_records: list[RelationRecord]
    structure_node_ids: list[UUID]


async def write_nodes_stage(
    chunks: list[Chunk],
    documents: list[Document],
    placements: Mapping[UUID, ChunkPlacement],
    ctx: StageContext,
) -> NodeStageResult:
    """Build and write the Chunk, structure and Document nodes of one batch.

    A chunk whose node record cannot be built is left out of the write and
    reported as a failure, unless the error policy is ``RAISE``.

    Args:
        chunks: The chunks of this batch. Empty when the batch has none.
        documents: The documents the chunks belong to.
        placements: Where each chunk sits in its document's structure.
        ctx: The store to write to, the error policy, the job and the tracer.

    Returns:
        The node writes, the records that could not be built, and the
        structure relations to write later.

    Raises:
        Exception: A record build or write failed and ``error_policy`` is
            ``RAISE``.
    """
    chunk_records: list[NodeRecord] = []
    chunk_ids: set[UUID] = set()
    record_failures: list[StageFailure] = []
    for chunk in chunks:
        try:
            chunk_records.append(chunk.to_node_record())
            if chunk.id is not None:
                chunk_ids.add(chunk.id)
        except Exception as exc:
            if ctx.error_policy is ErrorPolicy.RAISE:
                raise
            record_failures.append(_failure(str(chunk.id), exc))

    distinct = distinct_documents(documents)
    document_records = [build_document_record(doc) for doc in distinct]
    structure = build_document_structure(distinct, chunks, placements)
    structure_relation_records = [
        *structure.relations,
        *build_next_chunk_records(chunks),
    ]
    node_writes = await write_nodes(
        ctx.graph_store,
        chunk_records=chunk_records,
        structure=structure,
        document_records=document_records,
        error_policy=ctx.error_policy,
        pending_job_id=ctx.job_id,
        tracer=ctx.tracer,
    )
    return NodeStageResult(
        chunk_ids=chunk_ids,
        chunk_writes=node_writes.chunks,
        nodes_written=node_writes.written,
        record_failures=record_failures,
        node_failures=node_writes.failures,
        structure_relation_records=structure_relation_records,
        structure_node_ids=structure.structure_node_ids,
    )


async def write_relations_stage(
    domain_records: list[RelationRecord],
    mentioned_in_records: list[RelationRecord],
    ctx: StageContext,
) -> WriteOutcome:
    """Write the domain relations, then the MENTIONED_IN edges, of one batch.

    Args:
        domain_records: The domain relations and structure edges.
        mentioned_in_records: The MENTIONED_IN edges.
        ctx: The store to write to, the error policy, the job and the tracer.

    Returns:
        The number of relations written and the failures of both writes.

    Raises:
        Exception: A write failed and ``error_policy`` is ``RAISE``.
    """
    domain_outcome = await write_relations(
        ctx.graph_store,
        domain_records,
        item_id="relations",
        span_name="agrag.storage.upsert_relations",
        error_policy=ctx.error_policy,
        pending_job_id=ctx.job_id,
        tracer=ctx.tracer,
    )
    mentioned_outcome = await write_relations(
        ctx.graph_store,
        mentioned_in_records,
        item_id="MENTIONED_IN",
        span_name="agrag.storage.upsert_mentioned_in",
        error_policy=ctx.error_policy,
        pending_job_id=ctx.job_id,
        tracer=ctx.tracer,
    )
    return WriteOutcome(
        written=domain_outcome.written + mentioned_outcome.written,
        failures=[*domain_outcome.failures, *mentioned_outcome.failures],
    )


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
    error_policy: ErrorPolicy,
    tracer: Tracer,
) -> WriteOutcome:
    with tracer.start_as_current_span(
        "agrag.storage.upsert_structure",
        attributes={"agrag.record_count": structure.node_count},
    ) as span:
        label_outcomes = [
            _settle(label, outcome, error_policy)
            for label, outcome in await _write_structure_labels(
                graph_store, structure, pending_job_id
            )
        ]
        written = sum(outcome.written for outcome in label_outcomes)
        failures = [
            failure for outcome in label_outcomes for failure in outcome.failures
        ]
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
) -> list[tuple[str, WriteOutcome | BaseException]]:
    """Write the structure nodes of each label, one write per label.

    Every write finishes before this returns. A label whose write raised
    carries that exception, so the caller settles each label on its own.
    """
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
            _write_label(graph_store, label, records, pending_job_id)
            for label, records in pending
        ),
        return_exceptions=True,
    )
    return [
        (label, outcome) for (label, _), outcome in zip(pending, outcomes, strict=True)
    ]


async def _write_label(
    graph_store: GraphStore,
    label: str,
    records: list[NodeRecord],
    pending_job_id: UUID | None,
) -> WriteOutcome:
    result = await graph_store.upsert_nodes(
        label, records, pending_job_id=pending_job_id
    )
    return WriteOutcome(written=result.written, failures=upsert_stage_failures(result))
