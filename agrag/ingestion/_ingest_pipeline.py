"""Shared per-batch ingestion core for ``Graph.add()`` and ``Graph.update()``.

This module is internal. It owns the extract-resolve-merge-write pipeline
that runs over already-chunked input, with every dependency passed
explicitly rather than read from ``Graph``. ``Graph.add()`` calls
``ingest_chunks`` once per call after its own walk/chunk loop;
``Graph.update()`` calls it directly for the fresh-content case. This
module has no ``Graph`` import and cannot reach into ``Graph``'s private
state.
"""

import asyncio
import contextlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.chunking.chunker import ChunkPlacement
from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.document import Document
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.stage_failure import StageFailure, cap_failures
from agrag.common.data_models.vector_record import VectorRecord
from agrag.cypher.entities import (
    clear_chunk_embedding_query,
    clear_property_query,
    load_chunks_by_id_query,
    set_chunk_embedding_query,
    set_embedding_query,
)
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion._lexical_backbone import (
    build_document_record,
    distinct_documents,
)
from agrag.ingestion._merge_stage import merge_stage
from agrag.ingestion._resolve_stage import resolve_stage
from agrag.ingestion._storage import (
    WriteOutcome,
    write_nodes,
    write_nodes_stage,
    write_relations,
    write_relations_stage,
)
from agrag.ingestion._structure import build_document_structure
from agrag.ingestion.extract import Extractor
from agrag.ingestion.reports import AddResult
from agrag.ingestion.resolve.zone_classifier import MAX_LLM_PAIRS
from agrag.ingestion.resolved_entities import MatchComponent
from agrag.ingestion.stats import (
    ExtractionStats,
    IngestStats,
    MergeStats,
    ResolutionStats,
    StorageStats,
)
from agrag.loaders.types import ErrorPolicy
from agrag.observability import (
    get_tracer,
    record_stage_failure,
)
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


async def extract_chunks(
    chunks: list[Chunk],
    *,
    start_index: int,
    extractor: Extractor,
    schema: GraphSchema,
    error_policy: ErrorPolicy,
    tracer: Tracer | None = None,
) -> tuple[list[ExtractedEntity], list[ExtractedRelation], list[StageFailure]]:
    resolved_tracer = get_tracer(tracer)
    semaphore = asyncio.Semaphore(extractor.max_concurrency)

    async def _extract_one(
        chunk: Chunk,
    ) -> ExtractionResult | StageFailure:
        async with semaphore:
            with resolved_tracer.start_as_current_span(
                "agrag.extraction.extract_chunk",
                attributes={"agrag.chunk_id": str(chunk.id)},
            ) as span:
                try:
                    result = await extractor.extract(chunk, schema)
                except Exception as exc:
                    if error_policy is ErrorPolicy.RAISE:
                        raise
                    trace_id, span_id = record_stage_failure(exc)
                    return StageFailure(
                        item_id=str(chunk.id),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        trace_id=trace_id,
                        span_id=span_id,
                    )
                span.set_attribute("agrag.entities_extracted", len(result.entities))
                span.set_attribute("agrag.relations_extracted", len(result.relations))
                return result

    tasks = [asyncio.ensure_future(_extract_one(chunk)) for chunk in chunks]
    try:
        outcomes = await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    entities: list[ExtractedEntity] = []
    relations: list[ExtractedRelation] = []
    failures: list[StageFailure] = []
    for chunk, outcome in zip(chunks, outcomes, strict=True):
        if isinstance(outcome, StageFailure):
            failures.append(outcome)
            continue
        offset = start_index + len(entities)
        entities.extend(outcome.entities)
        for rel in outcome.relations:
            try:
                new_rel = ExtractedRelation(
                    chunk_id=rel.chunk_id,
                    label=rel.label,
                    source_index=rel.source_index + offset,
                    target_index=rel.target_index + offset,
                    confidence=rel.confidence,
                )
            except Exception as exc:  # noqa: BLE001
                if error_policy is ErrorPolicy.RAISE:
                    raise
                with resolved_tracer.start_as_current_span(
                    "agrag.extraction.remap_relations",
                    attributes={"agrag.chunk_id": str(chunk.id)},
                ):
                    trace_id, span_id = record_stage_failure(exc)
                failures.append(
                    StageFailure(
                        item_id=str(chunk.id),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        trace_id=trace_id,
                        span_id=span_id,
                    )
                )
                continue
            relations.append(new_rel)
    return entities, relations, failures


@dataclass(frozen=True)
class EmbedStageResult:
    """The failures of one embedding stage.

    Attributes:
        failures: One StageFailure per embed or vector write that raised under
            an error policy other than RAISE.
    """

    failures: list[StageFailure]


async def embed_chunks_stage(
    chunks: list[Chunk],
    chunk_ids: set[UUID],
    chunk_writes: WriteOutcome,
    *,
    embedder: Embedder,
    graph_store: GraphStore,
    error_policy: ErrorPolicy,
    vector_store: VectorStore | None,
    vector_collection: str,
    job_id: UUID | str | None,
    embed_heading_path: bool,
    tracer: Tracer,
) -> EmbedStageResult:
    """Embed the chunks of this batch that the graph holds, and write vectors.

    When the Chunk node write failed, upsert_nodes may still have committed its
    earlier batches. The stage then embeds whichever of this call's chunks the
    graph holds, so they do not stay unsearchable until the source is
    re-ingested.

    Args:
        chunks: The chunks of this batch.
        chunk_ids: The ids of the chunks this batch tried to write.
        chunk_writes: The outcome of the Chunk node write.
        embedder: Produces one vector per chunk.
        graph_store: Where the vectors are written and the landed chunks read.
        error_policy: How a failed embed or vector write is reported.
        vector_store: Optional second write target for the vectors.
        vector_collection: The VectorStore collection to write into.
        job_id: The in-flight cutover job, if any.
        embed_heading_path: Whether the embedder gets each heading path above
            the chunk text.
        tracer: Opens the embedding span.

    Returns:
        The failures of the embed and vector writes.

    Raises:
        Exception: The embed or a write failed and ``error_policy`` is
            ``RAISE``.
    """
    embeddable_ids = chunk_ids - chunk_writes.failed_ids
    if not chunk_writes.wrote_any:
        embeddable_ids = await _persisted_chunk_ids(
            graph_store, chunk_ids, job_id=job_id
        )
    if not embeddable_ids:
        return EmbedStageResult(failures=[])
    with tracer.start_as_current_span(
        "agrag.storage.embed_chunks",
        attributes={"agrag.embedding.heading_context": embed_heading_path},
    ):
        failures = await _embed_and_upsert_chunks(
            [chunk for chunk in chunks if chunk.id in embeddable_ids],
            embedder=embedder,
            graph_store=graph_store,
            error_policy=error_policy,
            vector_store=vector_store,
            vector_collection=vector_collection,
            pending_job_id=job_id,
            embed_heading_path=embed_heading_path,
        )
    return EmbedStageResult(failures=failures)


async def embed_survivors_stage(
    survivors: dict[UUID, Entity],
    *,
    embedder: Embedder,
    graph_store: GraphStore,
    error_policy: ErrorPolicy,
    vector_store: VectorStore | None,
    vector_collection: str,
    job_id: UUID | str | None,
    tracer: Tracer,
) -> EmbedStageResult:
    """Refresh the embedding of each survivor that this batch merged.

    Args:
        survivors: The merged entities written by this call, keyed by id.
        embedder: Computes one vector per entity's embedding text.
        graph_store: Where the vectors are written.
        error_policy: How a failed embed or vector write is reported.
        vector_store: Optional second write target for the vectors.
        vector_collection: The VectorStore collection to write into.
        job_id: The in-flight cutover job, if any.
        tracer: Opens the embedding span. No span opens without survivors.

    Returns:
        The failures of the embed and vector writes.

    Raises:
        Exception: The embed or a write failed and ``error_policy`` is
            ``RAISE``.
    """
    if not survivors:
        return EmbedStageResult(failures=[])
    with tracer.start_as_current_span("agrag.storage.embed_survivors"):
        failures = await _embed_and_upsert_survivors(
            survivors,
            embedder=embedder,
            graph_store=graph_store,
            error_policy=error_policy,
            vector_store=vector_store,
            vector_collection=vector_collection,
            labels_by_id={ent.id: ent.label for ent in survivors.values()},
            pending_job_id=job_id,
        )
    return EmbedStageResult(failures=failures)


async def ingest_chunks(
    chunks: list[Chunk],
    documents: list[Document],
    entities: list[ExtractedEntity],
    relations: list[ExtractedRelation],
    extraction_failures: list[StageFailure],
    *,
    graph_store: GraphStore,
    embedder: Embedder,
    vector_store: VectorStore | None,
    graph_schema: GraphSchema,
    retrieval_settings: RetrievalSettings,
    error_policy: ErrorPolicy,
    ingestion: IngestStats,
    placements: Mapping[UUID, ChunkPlacement],
    return_chunks: bool = False,
    job_id: UUID | str | None = None,
    rebuilt_components: list[MatchComponent] | None = None,
    tracer: Tracer | None = None,
    embed_heading_path: bool = True,
    max_llm_pairs: int = MAX_LLM_PAIRS,
) -> AddResult:
    """Resolve, merge, write and embed one batch of extracted chunks.

    Args:
        chunks: The chunks of this batch.
        documents: The documents the chunks belong to.
        entities: The mentions extracted from the chunks.
        relations: The relations extracted from the chunks.
        extraction_failures: Failures recorded before this stage.
        graph_store: The store every stage reads and writes.
        embedder: Embeds chunks, mentions and survivors.
        vector_store: Optional vector index mirrored by the embedding stages.
        graph_schema: The schema the resolver and merge work against.
        retrieval_settings: Names the collections the stages write to.
        error_policy: How a failed record, write or embed is reported.
        ingestion: The ingestion stats carried into the result.
        placements: Where each chunk sits in its document's structure.
        return_chunks: Whether the result carries the chunks.
        job_id: The in-flight cutover job, if any.
        rebuilt_components: When set, each rebuilt resolver component is
            appended with its decisions and members.
        tracer: Opens the spans. None disables them.
        embed_heading_path: Whether the chunk embedder gets each heading path.
        max_llm_pairs: The cap on LLM verifications for this batch.

    Returns:
        The stats of every stage, and the chunks when ``return_chunks`` is set.

    Raises:
        Exception: The first failure of any stage when ``error_policy`` is
            ``RAISE``.
    """
    job_uuid = UUID(str(job_id)) if job_id is not None else None
    resolved_tracer = get_tracer(tracer)
    with resolved_tracer.start_as_current_span("agrag.ingestion.ingest_chunks"):
        # With no chunks, only the documents and their structure are written.
        if not chunks:
            distinct = distinct_documents(documents)
            document_records = [build_document_record(doc) for doc in distinct]
            structure = build_document_structure(distinct, [], {})
            node_writes = await write_nodes(
                graph_store,
                chunk_records=[],
                structure=structure,
                document_records=document_records,
                error_policy=error_policy,
                pending_job_id=job_uuid,
                tracer=resolved_tracer,
            )
            empty_storage_failures = list(node_writes.failures)
            relation_outcome = await write_relations(
                graph_store,
                structure.relations,
                item_id="relations",
                span_name="agrag.storage.upsert_relations",
                error_policy=error_policy,
                pending_job_id=job_uuid,
                tracer=resolved_tracer,
            )
            empty_storage_failures.extend(relation_outcome.failures)
            empty_storage_capped = cap_failures(empty_storage_failures)
            extraction_failures_capped = cap_failures(list(extraction_failures))
            extraction = ExtractionStats(
                chunks_processed=0,
                entities_extracted=0,
                relations_extracted=0,
                failures=extraction_failures_capped.items,
                failures_total=extraction_failures_capped.total,
                failures_truncated=extraction_failures_capped.truncated,
            )
            return AddResult(
                ingestion=ingestion,
                extraction=extraction,
                resolution=ResolutionStats(),
                merge=MergeStats(),
                storage=StorageStats(
                    failures=empty_storage_capped.items,
                    failures_total=empty_storage_capped.total,
                    failures_truncated=empty_storage_capped.truncated,
                ),
                chunks=list(chunks) if return_chunks else [],
            )

        resolution = await resolve_stage(
            entities,
            relations,
            chunks,
            graph_store=graph_store,
            embedder=embedder,
            vector_store=vector_store,
            graph_schema=graph_schema,
            retrieval_settings=retrieval_settings,
            error_policy=error_policy,
            job_id=job_id,
            tracer=tracer,
            max_llm_pairs=max_llm_pairs,
        )
        merge = await merge_stage(
            entities,
            relations,
            resolution.batch,
            graph_store=graph_store,
            embedder=embedder,
            vector_store=vector_store,
            graph_schema=graph_schema,
            resolved_entity_collection=retrieval_settings.resolved_entity_collection,
            error_policy=error_policy,
            job_id=job_id,
            rebuilt_components=rebuilt_components,
            tracer=tracer,
        )
        nodes = await write_nodes_stage(
            chunks,
            documents,
            placements,
            graph_store=graph_store,
            error_policy=error_policy,
            pending_job_id=job_uuid,
            tracer=resolved_tracer,
        )
        chunk_embeds = await embed_chunks_stage(
            chunks,
            nodes.chunk_ids,
            nodes.chunk_writes,
            embedder=embedder,
            graph_store=graph_store,
            error_policy=error_policy,
            vector_store=vector_store,
            vector_collection=retrieval_settings.chunk_collection,
            job_id=job_id,
            embed_heading_path=embed_heading_path,
            tracer=resolved_tracer,
        )
        relation_writes = await write_relations_stage(
            [*merge.relation_records, *nodes.structure_relation_records],
            merge.mentioned_in_records,
            graph_store=graph_store,
            error_policy=error_policy,
            pending_job_id=job_uuid,
            tracer=resolved_tracer,
        )
        survivor_embeds = await embed_survivors_stage(
            merge.survivors,
            embedder=embedder,
            graph_store=graph_store,
            error_policy=error_policy,
            vector_store=vector_store,
            vector_collection=retrieval_settings.entity_collection,
            job_id=job_id,
            tracer=resolved_tracer,
        )
        storage_capped = cap_failures(
            [
                *nodes.record_failures,
                *merge.resolved_vector_failures,
                *nodes.node_failures,
                *chunk_embeds.failures,
                *relation_writes.failures,
                *survivor_embeds.failures,
            ]
        )
        storage = StorageStats(
            nodes_written=nodes.nodes_written + len(merge.survivors),
            relationships_written=relation_writes.written,
            failures=storage_capped.items,
            failures_total=storage_capped.total,
            failures_truncated=storage_capped.truncated,
        )

    extraction_failures_capped = cap_failures(list(extraction_failures))
    extraction = ExtractionStats(
        chunks_processed=len(chunks),
        entities_extracted=len(entities),
        relations_extracted=len(relations),
        failures=extraction_failures_capped.items,
        failures_total=extraction_failures_capped.total,
        failures_truncated=extraction_failures_capped.truncated,
    )
    return AddResult(
        ingestion=ingestion,
        extraction=extraction,
        resolution=resolution.stats,
        merge=merge.stats,
        storage=storage,
        chunks=list(chunks) if return_chunks else [],
    )


def _vector_record(
    record_id: UUID,
    vector: list[float],
    *,
    label: str,
    text: str,
    properties: dict[str, object] | None = None,
) -> VectorRecord:
    """Build a VectorRecord whose payload matches the retrievers' reads.

    ``label`` lets SearchFilters.to_payload_filter scope a search;
    ``text`` is the field the VectorStore backends sparse-embed for
    hybrid_search's keyword arm.

    Args:
        record_id: The domain object's id.
        vector: The dense embedding.
        label: The graph label the domain object carries.
        text: The embedding_text the vector was computed from.
        properties: Additional payload fields for metadata filtering.

    Returns:
        The record ready for VectorStore.upsert.
    """
    payload = {"label": label, "text": text}
    if properties:
        payload.update(properties)
    return VectorRecord(id=record_id, vector=vector, payload=payload)


async def _upsert_vectors(
    vector_store: VectorStore | None,
    collection: str,
    records: list[VectorRecord],
    *,
    pending_job_id: UUID | str | None = None,
) -> None:
    """Upsert records to the VectorStore when one is configured.

    Records whose vector is empty are skipped: an embed failure leaves
    None on the domain object, and an empty vector cannot be searched, so
    writing it would only corrupt the collection.

    Args:
        vector_store: The store to write to, or None to do nothing.
        collection: The collection name to write into.
        records: The records to upsert.
        pending_job_id: The in-flight Cutover Job staging these records. None
            writes committed records, for callers outside a job.
    """
    if vector_store is None:
        return
    writable = [record for record in records if record.vector]
    if not writable:
        return
    await vector_store.upsert(
        collection,
        writable,
        pending_job_id=UUID(str(pending_job_id)) if pending_job_id else None,
    )


async def _delete_vectors(
    vector_store: VectorStore | None, collection: str, ids: Sequence[UUID]
) -> None:
    """Delete records from the VectorStore when one is configured.

    Args:
        vector_store: The store to delete from, or None to do nothing.
        collection: The collection name to delete from.
        ids: The record ids to delete.
    """
    if vector_store is None or not ids:
        return
    await vector_store.delete(collection, list(ids))


def _node_properties(node: object) -> dict[str, Any]:
    """Return a node's properties from a GraphStore read row.

    The driver's ``Result.data()`` returns a node as a dict of its
    properties, which is also the shape the unit-test fakes use. A mapping
    that wraps them under ``properties`` is unwrapped.

    Args:
        node: The ``n`` value of a read row, or the row itself.

    Returns:
        The node's properties, or an empty mapping when none can be read.
    """
    if isinstance(node, dict):
        properties = node.get("properties")
        return dict(properties) if isinstance(properties, dict) else dict(node)
    with contextlib.suppress(Exception):
        return dict(node)  # ty: ignore[no-matching-overload]  # type: ignore[arg-type]
    return {}


async def _persisted_chunk_ids(
    graph_store: GraphStore, chunk_ids: set[UUID], *, job_id: UUID | str | None = None
) -> set[UUID]:
    """Return the subset of chunk_ids that exist as Chunk nodes.

    ``upsert_nodes`` writes its batches in sequence, so a failure partway
    through leaves the earlier batches committed. Embedding only the ids the
    graph really holds keeps those chunks searchable and keeps a chunk that
    never landed out of the VectorStore.

    Args:
        graph_store: Where the chunk nodes are read.
        chunk_ids: The ids this call tried to write.
        job_id: The in-flight job's id, so chunks this same job just wrote
            (still carrying its pending tag) count as landed. None reads
            committed chunks only.

    Returns:
        The ids found, or an empty set when the graph cannot be read. The
        caller then skips the embedding stage, which is what it did for every
        chunk before the partial write was accounted for.
    """
    if not chunk_ids:
        return set()
    try:
        rows = await graph_store.execute_read(
            load_chunks_by_id_query(),
            {
                "ids": [str(cid) for cid in chunk_ids],
                "job_id": str(job_id) if job_id is not None else None,
            },
        )
    except Exception:  # noqa: BLE001
        return set()
    found: set[UUID] = set()
    for row in rows:
        node = row.get("n", row) if isinstance(row, dict) else row
        node_id = _node_properties(node).get("id")
        if node_id is not None:
            with contextlib.suppress(ValueError):
                found.add(UUID(str(node_id)))
    return found


def _embedding_guard_fields(entity: Entity) -> dict[str, str]:
    """Return the id/name/description fields the embedding writes guard on.

    set_embedding_query and clear_property_query only apply a record when a
    node's current name/description still match these values, so a slower
    call cannot overwrite or clear a newer call's vector for different text.
    Mirrors ``coalesce(n.description, '')`` on the Cypher side.
    """
    description = entity.properties.get("description")
    return {
        "id": str(entity.id),
        "expected_name": entity.name,
        "expected_description": str(description) if description else "",
    }


async def _embed_and_upsert_chunks(
    chunks: list[Chunk],
    *,
    embedder: Embedder,
    graph_store: GraphStore,
    error_policy: ErrorPolicy,
    vector_store: VectorStore | None = None,
    vector_collection: str = "",
    pending_job_id: UUID | str | None = None,
    embed_heading_path: bool = False,
) -> list[StageFailure]:
    """Embed every chunk's text and write the vectors back onto their nodes.

    With ``embed_heading_path``, the embedder gets each chunk's heading path above
    its text. The stored text, the ``expected_text`` guard and the vector payload
    text stay the raw chunk text.

    On failure, clears any embedding already written to the chunk nodes
    rather than leaving one computed for stale text in place: vector
    search must not keep ranking a chunk by outdated content just because
    this re-embed failed. The clear is guarded by ``expected_text`` the
    same way the write is, so a concurrent update that changed a chunk's
    text between this call's embed and its clear does not accidentally
    wipe a newer vector.

    When vector_store is set, every successfully written vector is also
    upserted there so SearchEngine's VectorStore path matches the
    GraphStore-native path. Each record carries its chunk's
    ``document_id``, which is what a document-scoped SearchFilters
    compiles to, so filtering by document works on both paths. A
    VectorStore failure honors error_policy: RAISE propagates, otherwise
    it is recorded as a StageFailure and the native search path keeps
    working without it. The failure leaves the collection untouched: the
    mirror has no conditional write, so deleting the records this call
    failed to replace would race a concurrent re-ingest and could remove
    the newer vector it just wrote. The stored record keeps its previous
    text until the next successful ingest rewrites it, and retrieval
    loads every hit from the graph, so only that record's score is
    stale.

    Args:
        chunks: The chunks this call wrote to graph_store already.
        embedder: Produces one vector per chunk text.
        graph_store: Where the embedding, and on failure the cleared
            embedding property, are written.
        error_policy: RAISE propagates the failure after clearing; any
            other policy returns it instead.
        vector_store: Optional second write target; None does nothing.
        vector_collection: The VectorStore collection to write into.
            Ignored when vector_store is None.
        error_policy: RAISE propagates the failure after clearing; any
            other policy returns it instead.
        pending_job_id: The in-flight job's id, mirrored into vector
            payloads until that job commits. None writes untagged
            payloads, for callers outside a job.
        embed_heading_path: Whether the embedder gets each chunk's heading path
            above its text.

    Returns:
        One StageFailure per chunk whose embed or write step raised.

    Raises:
        Exception: Whatever embed() or the write raised, when
            error_policy is RAISE.
    """
    try:
        texts = [ch.contextual_text if embed_heading_path else ch.text for ch in chunks]
        vectors = await embedder.embed(texts)
        records = []
        for ch, vec in zip(chunks, vectors, strict=True):
            ch.embedding = vec
            records.append(
                {
                    "id": str(ch.id),
                    "vector": vec,
                    "expected_text": ch.text,
                }
            )
        matched_rows = await graph_store.execute_write(
            set_chunk_embedding_query("embedding"), {"records": records}
        )
    except Exception as exc:  # noqa: BLE001
        with contextlib.suppress(Exception):
            await graph_store.execute_write(
                clear_chunk_embedding_query("embedding"),
                {
                    "records": [
                        {"id": str(ch.id), "expected_text": ch.text} for ch in chunks
                    ]
                },
            )
        if error_policy is ErrorPolicy.RAISE:
            raise
        trace_id, span_id = record_stage_failure(exc)
        return [
            StageFailure(
                item_id="chunk_embeddings",
                error_type=type(exc).__name__,
                error_message=str(exc),
                trace_id=trace_id,
                span_id=span_id,
            )
        ]
    if vector_store is not None:
        vector_records = []
        matched_ids = {
            UUID(str(row["id"]))
            for row in matched_rows
            if isinstance(row, dict) and row.get("id")
        }
        for ch in chunks:
            if ch.id not in matched_ids:
                ch.embedding = None
                continue
            if ch.id is None or not ch.embedding:
                continue
            vector_records.append(
                _vector_record(
                    ch.id,
                    ch.embedding,
                    label=CHUNK_LABEL,
                    text=ch.text,
                    properties={"document_id": str(ch.document_id)},
                )
            )
        try:
            await _upsert_vectors(
                vector_store,
                vector_collection,
                vector_records,
                pending_job_id=pending_job_id,
            )
        except Exception as exc:  # noqa: BLE001
            if error_policy is ErrorPolicy.RAISE:
                raise
            trace_id, span_id = record_stage_failure(exc)
            return [
                StageFailure(
                    item_id="chunk_vector_store",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    trace_id=trace_id,
                    span_id=span_id,
                )
            ]
    return []


async def _embed_and_upsert_survivors(
    survivors: dict[UUID, Entity],
    *,
    embedder: Embedder,
    graph_store: GraphStore,
    error_policy: ErrorPolicy,
    vector_store: VectorStore | None = None,
    vector_collection: str = "",
    labels_by_id: dict[UUID, str] | None = None,
    pending_job_id: UUID | str | None = None,
) -> list[StageFailure]:
    """Embed every survivor's current text and write only the vector.

    Shared by add() and consolidate(apply=True): both write a survivor's
    node before this call, so its embedding must be refreshed for whatever
    text that write left it with. Writing only the embedding property
    (set_embedding_query), rather than a full node upsert from the in-memory
    Entity, matters here specifically: a concurrent writer could update this
    same entity's provenance or properties while this call's embed() is in
    flight, and a full overwrite from a snapshot taken before that update
    would discard it, not just deliver the new vector.

    Both the write and the failure-path clear below are guarded by
    _embedding_guard_fields: a record only applies when the node's current
    name/description still match what this call started with. Concurrent
    add() calls can interleave against the same entity, so without this
    guard an older, slower call's write or clear can land after a newer
    call's and leave a vector computed for stale text, or wipe a vector
    the newer call just wrote.

    On failure, clears any embedding already on the survivor nodes rather
    than leaving one computed for their prior text in place: vector search
    must not keep ranking an entity by outdated content just because this
    re-embed failed. ``zip(..., strict=True)`` turns an embedder returning
    too few vectors into the same failure path, rather than silently
    leaving the trailing entities' embeddings stale.

    When vector_store is set, each mirrored record also carries the
    survivor's own properties, since a SearchFilters property filter is
    compiled into the payload there but into a node-property match on the
    GraphStore-native path. A failed mirror upsert leaves the collection
    untouched, for the reason _embed_and_upsert_chunks gives: removing the
    records this call failed to replace would race a concurrent call that
    owns them.

    Args:
        survivors: The entities to embed, keyed by id.
        embedder: Computes one vector per entity's embedding_text.
        graph_store: Where the embedding, and on failure the cleared
            embedding property, are written.
        error_policy: RAISE propagates the failure after clearing; any
            other policy returns it instead.
        vector_store: Optional second write target; None does nothing.
        vector_collection: The VectorStore collection to write into.
            Ignored when vector_store is None.
        labels_by_id: Maps each survivor id to its label for the
            VectorStore payload. Survivors missing from the map are
            written with an empty label. Ignored when vector_store is
            None.
        pending_job_id: The in-flight job's id, mirrored into vector
            payloads until that job commits. None writes untagged
            payloads, for callers outside a job.

    Returns:
        A single-item list with the failure, or empty on success.

    Raises:
        Exception: Whatever embed() or the write raised, when error_policy
            is RAISE.
    """
    try:
        texts = [ent.embedding_text for ent in survivors.values()]
        vectors = await embedder.embed(texts)
        records = []
        for ent, vec in zip(survivors.values(), vectors, strict=True):
            ent.embedding = vec
            records.append({**_embedding_guard_fields(ent), "vector": vec})
        matched_rows = await graph_store.execute_write(
            set_embedding_query("embedding"), {"records": records}
        )
    except Exception as exc:  # noqa: BLE001
        # Best-effort: a failure here must not mask error_policy.
        with contextlib.suppress(Exception):
            await graph_store.execute_write(
                clear_property_query("embedding"),
                {
                    "records": [
                        _embedding_guard_fields(ent) for ent in survivors.values()
                    ]
                },
            )
        if error_policy is ErrorPolicy.RAISE:
            raise
        trace_id, span_id = record_stage_failure(exc)
        return [
            StageFailure(
                item_id="embeddings",
                error_type=type(exc).__name__,
                error_message=str(exc),
                trace_id=trace_id,
                span_id=span_id,
            )
        ]
    if vector_store is not None:
        label_map = labels_by_id or {}
        matched_ids = {
            UUID(str(row["id"]))
            for row in matched_rows
            if isinstance(row, dict) and row.get("id")
        }
        vector_records = [
            _vector_record(
                ent.id,
                ent.embedding or [],
                label=label_map.get(ent.id, ""),
                text=ent.embedding_text,
                properties=dict(ent.properties),
            )
            for ent in survivors.values()
            if ent.id in matched_ids
        ]
        try:
            await _upsert_vectors(
                vector_store,
                vector_collection,
                vector_records,
                pending_job_id=pending_job_id,
            )
        except Exception as exc:  # noqa: BLE001
            if error_policy is ErrorPolicy.RAISE:
                raise
            trace_id, span_id = record_stage_failure(exc)
            return [
                StageFailure(
                    item_id="entity_vector_store",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    trace_id=trace_id,
                    span_id=span_id,
                )
            ]
    return []
