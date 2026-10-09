"""Shared per-batch ingestion core for ``Graph.add()`` and ``Graph.update()``.

This module is internal. It owns the extract-resolve-merge-write pipeline
that runs over already-chunked input, with every dependency passed
explicitly rather than read from ``Graph``. ``Graph.add()`` calls
``ingest_chunks`` once per call after its own walk/chunk loop;
``Graph.update()`` calls it directly for the fresh-content case. This
module has no ``Graph`` import and cannot reach into ``Graph``'s private
state.
"""

import contextlib
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.document import DOCUMENT_LABEL, Document
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
from agrag.common.data_models.graph_record import (
    RelationRecord,
    UpsertResult,
)
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.relation import Relation
from agrag.common.data_models.stage_failure import StageFailure, cap_failures
from agrag.common.data_models.vector_record import VectorRecord
from agrag.cypher.entities import (
    clear_chunk_embedding_query,
    clear_property_query,
    fetch_relations_between_query,
    load_chunks_by_id_query,
    set_chunk_embedding_query,
    set_embedding_query,
)
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion._lexical_backbone import (
    build_document_record,
    build_next_chunk_records,
    distinct_documents,
)
from agrag.ingestion._structure import build_document_structure
from agrag.ingestion._structure_wiring import write_structure_nodes
from agrag.ingestion.extract import Extractor
from agrag.ingestion.merge import (
    apply_merge,
    compute_merge,
    mentioned_in_id,
    relation_id,
)
from agrag.ingestion.reports import AddResult
from agrag.ingestion.resolve import resolve_batch
from agrag.ingestion.resolve.zone_classifier import MAX_LLM_PAIRS
from agrag.ingestion.resolved_embeddings import _synchronize_resolved_entity_vectors
from agrag.ingestion.resolved_entities import (
    MatchComponent,
    decisions_by_component,
    write_matches_and_rebuild,
)
from agrag.ingestion.stats import (
    ExtractionStats,
    IngestStats,
    MergeStats,
    ResolutionStats,
    StorageStats,
)
from agrag.loaders.corpus.types import ErrorPolicy
from agrag.observability import (
    get_tracer,
    record_stage_failure,
    stage_failure_context,
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
    """Run the extractor over already-chunked input, remapping relation indices.

    Relation indices an extractor reports are local to one chunk's own
    result; they are shifted by the running entity count so they address
    the combined entity list. ``start_index`` is the number of entities
    already collected before ``chunks`` (for example by earlier walk
    batches), so a per-batch call remaps exactly as one continuous call
    would.

    Args:
        chunks: The chunks to extract from, in order.
        start_index: The running entity count before ``chunks``.
        extractor: Runs against each chunk.
        schema: The entity/relation types extraction is validated against.
        error_policy: RAISE propagates an extraction failure; any other
            policy records it and continues with the remaining chunks.
        tracer: Opens one span per chunk.

    Returns:
        The extracted entities and globally-remapped relations, plus one
        StageFailure per chunk or relation that failed under a
        non-RAISE policy.
    """
    entities: list[ExtractedEntity] = []
    relations: list[ExtractedRelation] = []
    failures: list[StageFailure] = []
    resolved_tracer = get_tracer(tracer)
    for chunk in chunks:
        offset = start_index + len(entities)
        # The relation-remapping loop below stays inside this same `with`
        # block, not just the extract() call -- a relation-index failure
        # must mark *this chunk's* span, not whatever span is ambiently
        # current once this span closes (the caller's, coarser and shared
        # across every chunk), matching the per-item failure granularity
        # every other site in this plan uses.
        with resolved_tracer.start_as_current_span(
            "agrag.extraction.extract_chunk",
            attributes={"agrag.chunk_id": str(chunk.id)},
        ) as span:
            try:
                result = await extractor.extract(chunk, schema)
            except Exception as exc:  # noqa: BLE001
                if error_policy is ErrorPolicy.RAISE:
                    raise
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
            span.set_attribute("agrag.entities_extracted", len(result.entities))
            span.set_attribute("agrag.relations_extracted", len(result.relations))
            entities.extend(result.entities)
            for rel in result.relations:
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


async def ingest_chunks(  # noqa: PLR0912,PLR0915
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
    return_chunks: bool = False,
    job_id: UUID | str | None = None,
    rebuilt_components: list[MatchComponent] | None = None,
    tracer: Tracer | None = None,
    embed_heading_path: bool = True,
    max_llm_pairs: int = MAX_LLM_PAIRS,
) -> AddResult:
    """Run resolution, merge, and storage for already-chunked input.

    Takes the chunks, their source documents, and the already-extracted
    mentions (see ``extract_chunks``), then runs global exact-match
    plus in-batch resolution, merge planning and application, and every
    storage write chunks already use: chunk nodes, document nodes,
    ``PART_OF``/``NEXT_CHUNK`` edges, domain relations, ``MENTIONED_IN``
    edges, and embeddings.

    Args:
        chunks: The chunks to ingest, in document then chunk order.
        documents: The documents the chunks came from, possibly repeating
            the same document across batches. Document nodes are deduped
            by stable key before writing.
        entities: The extracted entity mentions, with globally-remapped
            relation indices matching this list.
        relations: The extracted relations addressing ``entities``.
        extraction_failures: Failures extraction already recorded under a
            non-RAISE policy, carried into the returned summary.
        graph_store: Where nodes, relations, and embeddings are written.
        embedder: Populates chunk and entity embeddings.
        vector_store: Optional second write target for embeddings.
        graph_schema: The entity/relation types merges are computed against.
        retrieval_settings: Collection names for the VectorStore writes.
        error_policy: RAISE propagates a stage failure, including a failed
            read of a mention's persisted candidates; any other policy
            records it and continues with the remaining items. A mention
            whose candidate read failed is not resolved or stored in this
            call, and its failure appears in ``merge.failures``.
        ingestion: The ingestion-stage summary the caller already computed
            from its own walk.
        return_chunks: Whether to include the ingested chunks in the
            returned result.
        job_id: The in-flight Cutover Job's id. Every node, edge, and
            vector this call writes is tagged with it until that job
            commits; brand-new entities derive deterministic ids from it.
            None writes untagged with random new-entity ids, for callers
            outside a job.
        rebuilt_components: Receives each component this call
            rebuilt. A pending job never deletes the resolved entity
            it supersedes, so the caller rebuilds these again after
            the job commits to replace it.
        tracer: Opens this call's span and every phase span below it.
        embed_heading_path: Whether chunk embeddings include the chunk's heading
            path. The stored chunk text and vector payload text stay raw.
        max_llm_pairs: The most ambiguous entity pairs that resolution sends to
            the LLM for each label.

    Returns:
        The per-stage summary for this ingestion.

    Note:
        Shared by ``Graph.add()`` and ``Graph.update()``: both callers
        must observe side-effect-equivalent behavior for the same input,
        since ``update()``'s fresh-content path is defined as this core
        over newly chunked content.
    """
    pending_job_id = str(job_id) if job_id is not None else None
    job_uuid = UUID(pending_job_id) if pending_job_id is not None else None
    resolved_tracer = get_tracer(tracer)
    with resolved_tracer.start_as_current_span("agrag.ingestion.ingest_chunks"):
        # If no chunks/entities, we can early return with empty stages
        if not chunks:
            if documents:
                await graph_store.upsert_nodes(
                    DOCUMENT_LABEL,
                    [
                        build_document_record(document)
                        for document in distinct_documents(documents)
                    ],
                    pending_job_id=job_uuid,
                )
            # Build final result with zero stages
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
                storage=StorageStats(),
                chunks=list(chunks) if return_chunks else [],
            )

        chunks_by_id: dict[UUID, Chunk] = {}
        for ch in chunks:
            if ch.id is not None:
                chunks_by_id[ch.id] = ch

        resolution_batch = await resolve_batch(
            entities,
            relations,
            chunks_by_id,
            graph_store=graph_store,
            embedder=embedder,
            vector_store=vector_store,
            vector_collection=retrieval_settings.entity_collection,
            entity_labels=[entity.label for entity in graph_schema.entities],
            tracer=tracer,
            max_llm_pairs=max_llm_pairs,
            error_policy=error_policy,
            job_id=job_id,
        )
        exact_matches = resolution_batch.exact_matches
        unresolved_indices = resolution_batch.unresolved_indices
        resolution_result = resolution_batch.result
        persisted_ids = resolution_batch.persisted_ids
        candidate_entities = resolution_batch.candidate_entities
        semantic_groups = (
            resolution_result.groups if resolution_result is not None else []
        )
        groups = resolution_batch.groups

        # Compute resolution stats. Groups over the combined list include
        # synthetic singletons, so only groups holding a real mention count.
        exact_match_hits = len(exact_matches)
        # Groups include singletons; in_batch_groups is resolver group count.
        resolution = ResolutionStats(
            exact_match_hits=exact_match_hits,
            in_batch_groups=sum(
                1
                for group in semantic_groups
                if any(index < len(entities) for index in group.entity_indices)
            ),
            ambiguous_count=(
                resolution_result.ambiguous_count
                if resolution_result is not None
                else 0
            ),
        )

        # Merge and write
        merge_stats = MergeStats()
        storage_stats = StorageStats()
        merge_failures: list[StageFailure] = list(resolution_batch.failures)

        # Track survivors and mention->entity map
        mention_to_entity: dict[int, UUID] = {}
        survivors: dict[UUID, Entity] = {}
        resolved_vector_failures: list[StageFailure] = []
        # For storage stats counting
        nodes_created = 0
        nodes_updated = 0
        conflicts_resolved = 0

        for group in groups:
            group_indices = [
                index
                for index in group.entity_indices
                if index not in unresolved_indices
            ]
            if not group_indices:
                continue
            group_mentions = [entities[i] for i in group_indices]
            with resolved_tracer.start_as_current_span(
                "agrag.merge.merge_group",
                attributes={"agrag.mention_count": len(group_mentions)},
            ) as span:
                existing_for_group: list[Entity] = []
                seen_ids: set[UUID] = set()
                for idx in group_indices:
                    ent = exact_matches.get(idx)
                    if ent is not None and ent.id not in seen_ids:
                        seen_ids.add(ent.id)
                        existing_for_group.append(ent)

                try:
                    plan, desc_failures = await compute_merge(
                        existing_entities=existing_for_group,
                        mentions=group_mentions,
                        schema=graph_schema,
                        job_id=job_id,
                        tracer=tracer,
                    )
                except Exception as exc:  # noqa: BLE001
                    if error_policy is ErrorPolicy.RAISE:
                        raise
                    trace_id, span_id = record_stage_failure(exc)
                    merge_failures.append(
                        StageFailure(
                            item_id=",".join(
                                str(entities[i].text) for i in group_indices
                            ),
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                            trace_id=trace_id,
                            span_id=span_id,
                        )
                    )
                    continue

                if desc_failures:
                    merge_failures.extend(desc_failures)  # type: ignore[arg-type]
                conflicts_resolved += len(plan.conflicts)
                if not existing_for_group:
                    nodes_created += 1
                else:
                    nodes_updated += 1

                try:
                    await apply_merge(
                        plan,
                        graph_store=graph_store,
                        schema=graph_schema,
                        pending_job_id=pending_job_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    if error_policy is ErrorPolicy.RAISE:
                        raise
                    trace_id, span_id = record_stage_failure(exc)
                    merge_failures.append(
                        StageFailure(
                            item_id=str(plan.survivor.id),
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                            trace_id=trace_id,
                            span_id=span_id,
                        )
                    )
                    continue

                span.set_attribute("agrag.conflicts_resolved", len(plan.conflicts))
                survivors[plan.survivor.id] = plan.survivor
                for idx in group_indices:
                    mention_to_entity[idx] = plan.survivor.id

        if resolution_result is not None:
            mention_to_entity.update(persisted_ids)
            for decisions in decisions_by_component(
                resolution_result.matches, mention_to_entity
            ):
                member_ids = {decision.entity_a_id for decision in decisions} | {
                    decision.entity_b_id for decision in decisions
                }
                members = [
                    survivors.get(member_id) or candidate_entities[member_id]
                    for member_id in member_ids
                ]
                with resolved_tracer.start_as_current_span(
                    "agrag.merge.rebuild_component",
                    attributes={"agrag.member_count": len(members)},
                ):
                    try:
                        rebuild = await write_matches_and_rebuild(
                            decisions,
                            graph_store=graph_store,
                            schema=graph_schema,
                            members=members,
                            pending_job_id=pending_job_id,
                            tracer=tracer,
                        )
                    except Exception as exc:  # noqa: BLE001
                        if error_policy is ErrorPolicy.RAISE:
                            raise
                        trace_id, span_id = record_stage_failure(exc)
                        merge_failures.append(
                            StageFailure(
                                item_id=",".join(
                                    str(member_id) for member_id in member_ids
                                ),
                                error_type=type(exc).__name__,
                                error_message=str(exc),
                                trace_id=trace_id,
                                span_id=span_id,
                            )
                        )
                        continue
                    if rebuilt_components is not None:
                        rebuilt_components.append((decisions, members))
                    # Synchronized per component, not batched after the loop: a
                    # later component's failure under ErrorPolicy.RAISE must not
                    # skip vector cleanup for components already committed above.
                    resolved_vector_failures.extend(
                        await _synchronize_resolved_entity_vectors(
                            [rebuild.resolved_entity],
                            rebuild.removed_entity_ids,
                            embedder=embedder,
                            graph_store=graph_store,
                            vector_store=vector_store,
                            vector_collection=retrieval_settings.resolved_entity_collection,
                            error_policy=error_policy,
                            pending_job_id=job_id,
                        )
                    )

        # If there were no entities (empty corpus) we have no survivors
        # but we still need to write chunks

        merge_failures_capped = cap_failures(merge_failures)
        merge_stats = MergeStats(
            nodes_created=nodes_created,
            nodes_updated=nodes_updated,
            conflicts_resolved=conflicts_resolved,
            failures=merge_failures_capped.items,
            failures_total=merge_failures_capped.total,
            failures_truncated=merge_failures_capped.truncated,
        )

        # Domain relation dedup + MENTIONED_IN
        # Build domain relation triples after mention->entity mapping
        # triples: list of (src_id, tgt_id, label)
        triple_to_chunk_ids: dict[tuple[UUID, UUID, str], list[UUID]] = {}
        # Keep track of which relations contributed which chunk ids
        for rel in relations:
            src_id = mention_to_entity.get(rel.source_index)
            tgt_id = mention_to_entity.get(rel.target_index)
            if src_id is None or tgt_id is None or src_id == tgt_id:
                continue
            key = (src_id, tgt_id, rel.label)
            # Collect chunk ids for this triple (within-call dedup union)
            lst = triple_to_chunk_ids.setdefault(key, [])
            # Avoid duplicates preserving order
            if rel.chunk_id not in lst:
                lst.append(rel.chunk_id)

        # Global relation lookup
        triples_list = list(triple_to_chunk_ids.keys())
        existing_rel_map = await _global_relation_lookup(
            triples_list, graph_store=graph_store, job_id=pending_job_id
        )

        # Build Relation objects
        relation_records: list[RelationRecord] = []
        relation_storage_failures: list[StageFailure] = []

        for (src_id, tgt_id, rel_type), chunk_ids in triple_to_chunk_ids.items():
            key = (src_id, tgt_id, rel_type)
            existing = existing_rel_map.get(key)
            if existing is not None:
                existing_id, existing_scids = existing
                # Union source_chunk_ids
                union_ids = list(dict.fromkeys([*existing_scids, *chunk_ids]))
                rel_id = existing_id
            else:
                # Deterministic, not uuid4(): two concurrent add() calls that
                # both miss the existing-relation lookup for this triple must
                # compute the same id, so their upserts converge onto one
                # edge instead of creating parallel ones.
                rel_id = relation_id(src_id, tgt_id, rel_type)
                union_ids = list(dict.fromkeys(chunk_ids))

            # Build Relation domain object then to record
            # Use created_at default
            relation_obj = Relation(
                id=rel_id,
                type=rel_type,
                source_id=src_id,
                target_id=tgt_id,
                source_chunk_ids=union_ids,
            )
            relation_records.append(relation_obj.to_relation_record())

        # MENTIONED_IN edges: one per (chunk, entity) pair, for real mentions
        # only. Synthetic persisted-candidate indices (>= len(entities)) carry
        # no chunk evidence from this call: their chunks were never written.
        mentioned_pairs: set[tuple[UUID, UUID]] = set()
        for idx, entity_id in mention_to_entity.items():
            if idx >= len(entities):
                continue
            # mention's chunk_id
            chunk_id = entities[idx].chunk_id
            mentioned_pairs.add((chunk_id, entity_id))

        # Look up by endpoint rather than trusting mentioned_in_id() alone,
        # so an edge whose stored id differs from the recomputed one is
        # found instead of duplicated on re-ingest.
        existing_mentioned_map = await _global_relation_lookup(
            [
                (chunk_id, entity_id, "MENTIONED_IN")
                for chunk_id, entity_id in mentioned_pairs
            ],
            graph_store=graph_store,
        )

        mentioned_in_records: list[RelationRecord] = []
        for chunk_id, entity_id in mentioned_pairs:
            existing = existing_mentioned_map.get((chunk_id, entity_id, "MENTIONED_IN"))
            edge_id = (
                existing[0]
                if existing is not None
                else mentioned_in_id(chunk_id, entity_id)
            )
            # Build record directly
            rec = RelationRecord(
                id=edge_id,
                type="MENTIONED_IN",
                start_id=chunk_id,
                end_id=entity_id,
                properties={"created_at": datetime.now().isoformat()},
            )
            mentioned_in_records.append(rec)

        # Final storage writes: Chunks, Relations (domain + mentioned)
        # Chunks
        chunk_records = []
        chunk_ids: set[UUID] = set()
        for ch in chunks:
            try:
                chunk_records.append(ch.to_node_record())
                if ch.id is not None:
                    chunk_ids.add(ch.id)
            except Exception as exc:  # noqa: BLE001
                if error_policy is ErrorPolicy.RAISE:
                    raise
                trace_id, span_id = record_stage_failure(exc)
                relation_storage_failures.append(
                    StageFailure(
                        item_id=str(ch.id),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        trace_id=trace_id,
                        span_id=span_id,
                    )
                )
                continue

        # Document nodes and PART_OF edges: one Document per distinct document
        # in this call, PART_OF linking it to the chunks written above.
        distinct = distinct_documents(documents)
        document_records = [build_document_record(doc) for doc in distinct]
        structure = build_document_structure(distinct, chunks)
        relation_records.extend(structure.relations)
        relation_records.extend(build_next_chunk_records(chunks))

        # Write chunk nodes
        storage_failures: list[StageFailure] = [
            *relation_storage_failures,
            *resolved_vector_failures,
        ]
        nodes_written = 0
        relationships_written_count = 0
        chunk_failure_ids: set[UUID] = set()
        chunks_written = False
        with resolved_tracer.start_as_current_span(
            "agrag.storage.upsert_chunks",
            attributes={"agrag.record_count": len(chunk_records)},
        ) as span:
            try:
                if chunk_records:
                    write_result = await graph_store.upsert_nodes(
                        CHUNK_LABEL, chunk_records, pending_job_id=job_uuid
                    )
                    nodes_written += write_result.written
                    storage_failures.extend(_upsert_stage_failures(write_result))
                    chunk_failure_ids = set()
                    for failure in write_result.failures:
                        try:
                            chunk_failure_ids.add(UUID(failure.id))
                        except ValueError:
                            continue
                    chunks_written = True
                    span.set_attribute("agrag.nodes_written", write_result.written)
            except Exception as exc:  # noqa: BLE001
                if error_policy is ErrorPolicy.RAISE:
                    raise
                trace_id, span_id = record_stage_failure(exc)
                storage_failures.append(
                    StageFailure(
                        item_id="chunks",
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        trace_id=trace_id,
                        span_id=span_id,
                    )
                )

        # Write structure nodes: sections, tables, figures and record sources
        with resolved_tracer.start_as_current_span(
            "agrag.storage.upsert_structure",
            attributes={"agrag.record_count": structure.node_count},
        ) as span:
            try:
                for result in await write_structure_nodes(
                    graph_store, structure, pending_job_id=job_uuid
                ):
                    nodes_written += result.written
                    storage_failures.extend(_upsert_stage_failures(result))
                span.set_attribute("agrag.nodes_written", nodes_written)
            except Exception as exc:  # noqa: BLE001
                if error_policy is ErrorPolicy.RAISE:
                    raise
                trace_id, span_id = record_stage_failure(exc)
                storage_failures.append(
                    StageFailure(
                        item_id="structure",
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        trace_id=trace_id,
                        span_id=span_id,
                    )
                )

        # Write Document nodes
        with resolved_tracer.start_as_current_span(
            "agrag.storage.upsert_documents",
            attributes={"agrag.record_count": len(document_records)},
        ) as span:
            try:
                if document_records:
                    result = await graph_store.upsert_nodes(
                        DOCUMENT_LABEL, document_records, pending_job_id=job_uuid
                    )
                    nodes_written += result.written
                    storage_failures.extend(_upsert_stage_failures(result))
                    span.set_attribute("agrag.nodes_written", result.written)
            except Exception as exc:  # noqa: BLE001
                if error_policy is ErrorPolicy.RAISE:
                    raise
                trace_id, span_id = record_stage_failure(exc)
                storage_failures.append(
                    StageFailure(
                        item_id="documents",
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        trace_id=trace_id,
                        span_id=span_id,
                    )
                )

        # Chunk embedding stage: embed chunks and write vectors. When the node
        # write failed, upsert_nodes may still have committed its earlier
        # batches, so embed whichever of this call's chunks the graph holds
        # instead of leaving them unsearchable until the source is re-ingested.
        embeddable_ids = chunk_ids - chunk_failure_ids
        if not chunks_written:
            embeddable_ids = await _persisted_chunk_ids(
                graph_store, chunk_ids, job_id=job_id
            )
        if embeddable_ids:
            with resolved_tracer.start_as_current_span(
                "agrag.storage.embed_chunks",
                attributes={"agrag.embedding.heading_context": embed_heading_path},
            ):
                storage_failures.extend(
                    await _embed_and_upsert_chunks(
                        [chunk for chunk in chunks if chunk.id in embeddable_ids],
                        embedder=embedder,
                        graph_store=graph_store,
                        error_policy=error_policy,
                        vector_store=vector_store,
                        vector_collection=retrieval_settings.chunk_collection,
                        pending_job_id=job_id,
                        embed_heading_path=embed_heading_path,
                    )
                )

        # Survivors already written via apply_merge; count them.
        nodes_written += len(survivors)

        # Write domain relations
        with resolved_tracer.start_as_current_span(
            "agrag.storage.upsert_relations",
            attributes={"agrag.record_count": len(relation_records)},
        ) as span:
            try:
                if relation_records:
                    write_result = await graph_store.upsert_relations(
                        relation_records, pending_job_id=job_uuid
                    )
                    relationships_written_count += write_result.written
                    storage_failures.extend(_upsert_stage_failures(write_result))
                    span.set_attribute(
                        "agrag.relationships_written", write_result.written
                    )
            except Exception as exc:  # noqa: BLE001
                if error_policy is ErrorPolicy.RAISE:
                    raise
                trace_id, span_id = record_stage_failure(exc)
                storage_failures.append(
                    StageFailure(
                        item_id="relations",
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        trace_id=trace_id,
                        span_id=span_id,
                    )
                )

        with resolved_tracer.start_as_current_span(
            "agrag.storage.upsert_mentioned_in",
            attributes={"agrag.record_count": len(mentioned_in_records)},
        ) as span:
            try:
                if mentioned_in_records:
                    write_result = await graph_store.upsert_relations(
                        mentioned_in_records, pending_job_id=job_uuid
                    )
                    relationships_written_count += write_result.written
                    storage_failures.extend(_upsert_stage_failures(write_result))
                    span.set_attribute(
                        "agrag.relationships_written", write_result.written
                    )
            except Exception as exc:  # noqa: BLE001
                if error_policy is ErrorPolicy.RAISE:
                    raise
                trace_id, span_id = record_stage_failure(exc)
                storage_failures.append(
                    StageFailure(
                        item_id="MENTIONED_IN",
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        trace_id=trace_id,
                        span_id=span_id,
                    )
                )

        # Embedding stage: embed survivors and update them.
        if survivors:
            with resolved_tracer.start_as_current_span("agrag.storage.embed_survivors"):
                storage_failures.extend(
                    await _embed_and_upsert_survivors(
                        survivors,
                        embedder=embedder,
                        graph_store=graph_store,
                        error_policy=error_policy,
                        vector_store=vector_store,
                        vector_collection=retrieval_settings.entity_collection,
                        labels_by_id={ent.id: ent.label for ent in survivors.values()},
                        pending_job_id=job_id,
                    )
                )
        storage_failures_capped = cap_failures(storage_failures)
        storage_stats = StorageStats(
            nodes_written=nodes_written,
            relationships_written=relationships_written_count,
            failures=storage_failures_capped.items,
            failures_total=storage_failures_capped.total,
            failures_truncated=storage_failures_capped.truncated,
        )

    # Assemble final AddResult
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
        resolution=resolution,
        merge=merge_stats,
        storage=storage_stats,
        chunks=list(chunks) if return_chunks else [],
    )


def _upsert_stage_failures(result: UpsertResult) -> list[StageFailure]:
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


async def _global_relation_lookup(
    triples: list[tuple[UUID, UUID, str]],
    *,
    graph_store: GraphStore,
    job_id: UUID | str | None = None,
) -> dict[tuple[UUID, UUID, str], tuple[UUID, list[UUID]]]:
    """Return each triple's already-persisted relation id and source_chunk_ids.

    One batched read per distinct relation type present in triples.

    Args:
        triples: The (source_id, target_id, type) triples to look up.
        graph_store: Where the lookup runs.
        job_id: The active job whose pending relations are visible.

    Returns:
        A map from triple to its existing relation's (id, source_chunk_ids).
    """
    if not triples:
        return {}
    by_type: dict[str, list[tuple[UUID, UUID]]] = defaultdict(list)
    for src, tgt, typ in triples:
        by_type[typ].append((src, tgt))

    result: dict[tuple[UUID, UUID, str], tuple[UUID, list[UUID]]] = {}
    for rel_type, pairs in by_type.items():
        unique_pairs = list(dict.fromkeys(pairs))
        # Build params as list of {source_id, target_id}
        params = [{"source_id": str(s), "target_id": str(t)} for s, t in unique_pairs]
        query = fetch_relations_between_query(
            rel_type, job_id="job_id" if job_id is not None else None
        )
        read_params: dict[str, object] = {"pairs": params}
        if job_id is not None:
            read_params["job_id"] = str(job_id)
        rows = await graph_store.execute_read(query, read_params)
        for row in rows:
            try:
                src = UUID(str(row["source_id"]))
                tgt = UUID(str(row["target_id"]))
                rel_id = UUID(str(row["id"]))
                raw_scids = row.get("source_chunk_ids") or []
                scids = [UUID(str(x)) for x in raw_scids]
                key = (src, tgt, rel_type)
                # Also handle reverse? Not needed, query is directed.
                result[key] = (rel_id, scids)
            except Exception:
                continue
    return result


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
