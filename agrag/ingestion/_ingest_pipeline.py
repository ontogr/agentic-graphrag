"""Shared per-batch ingestion core for ``Graph.add()`` and ``Graph.update()``.

This module is internal. It owns the extract-resolve-merge-write pipeline
that runs over already-chunked input, with every dependency passed
explicitly rather than read from ``Graph``. ``Graph.add()`` calls
:func:`ingest_chunks` once per call after its own walk/chunk loop;
``Graph.update()`` calls it directly for the fresh-content case. This
module has no ``Graph`` import and cannot reach into ``Graph``'s private
state.
"""

import contextlib
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.document import DOCUMENT_LABEL, Document
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
from agrag.common.data_models.graph_record import RelationRecord, UpsertResult
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.relation import Relation
from agrag.common.data_models.vector_record import VectorRecord
from agrag.common.text import normalize_text
from agrag.cypher.entities import (
    NODE_IDENTITY_LABEL,
    clear_chunk_embedding_query,
    clear_property_query,
    fetch_by_merge_keys_query,
    fetch_relations_between_query,
    hydrate_chunks_by_id_query,
    set_chunk_embedding_query,
    set_embedding_query,
)
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.graphdb.errors import (
    GraphStoreAliasConflictError,
    GraphStoreConstraintViolationError,
    GraphStoreDataIntegrityError,
)
from agrag.ingestion._lexical_backbone import (
    build_document_record,
    build_next_chunk_records,
    build_part_of_records,
    distinct_documents,
)
from agrag.ingestion.extract import Extractor
from agrag.ingestion.materialize import (
    decisions_by_component,
    write_matches_and_materialize,
)
from agrag.ingestion.merge import (
    MergePlan,
    apply_merge,
    compute_merge,
    mentioned_in_id,
    relation_id,
)
from agrag.ingestion.reports import AddResult
from agrag.ingestion.resolve import (
    ExactMatch,
    FuzzyMatch,
    GraphCandidateSource,
    InBatchCandidateSource,
    LLMVerify,
    PersistedCandidateSource,
    Resolver,
    exact_resolution_groups,
)
from agrag.ingestion.resolved_embeddings import _synchronize_resolved_entity_vectors
from agrag.ingestion.stats import (
    ExtractionStats,
    IngestStats,
    MergeStats,
    ResolutionStats,
    StageFailure,
    StorageStats,
    cap_failures,
)
from agrag.loaders.corpus.types import ErrorPolicy
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


async def extract_chunks(
    chunks: list[Chunk],
    *,
    start_index: int,
    extractor: Extractor,
    schema: GraphSchema,
    error_policy: ErrorPolicy,
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

    Returns:
        The extracted entities and globally-remapped relations, plus one
        StageFailure per chunk or relation that failed under a
        non-RAISE policy.
    """
    entities: list[ExtractedEntity] = []
    relations: list[ExtractedRelation] = []
    failures: list[StageFailure] = []
    for chunk in chunks:
        # Use global entities/relations with index remapping
        offset = start_index + len(entities)
        try:
            result = await extractor.extract(chunk, schema)
        except Exception as exc:  # noqa: BLE001
            if error_policy is ErrorPolicy.RAISE:
                raise
            failures.append(
                StageFailure(
                    item_id=str(chunk.id),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )
            continue
        # Append entities
        entities.extend(result.entities)
        # Remap relations indices to global offsets
        for rel in result.relations:
            # Validate local indices are within this chunk's result
            # They should be, but guard
            try:
                # Need to ensure we use global indices
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
                failures.append(
                    StageFailure(
                        item_id=str(chunk.id),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
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
) -> AddResult:
    """Run resolution, merge, and storage for already-chunked input.

    Takes the chunks, their source documents, and the already-extracted
    mentions (see :func:`extract_chunks`), then runs global exact-match
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
        error_policy: RAISE propagates a stage failure; any other policy
            records it and continues with the remaining items.
        ingestion: The ingestion-stage summary the caller already computed
            from its own walk.
        return_chunks: Whether to include the ingested chunks in the
            returned result.

    Returns:
        The per-stage summary for this ingestion.

    Note:
        Shared by ``Graph.add()`` and ``Graph.update()``: both callers
        must observe side-effect-equivalent behavior for the same input,
        since ``update()``'s fresh-content path is defined as this core
        over newly chunked content.
    """
    # If no chunks/entities, we can early return with empty stages
    if not chunks:
        if documents:
            await graph_store.upsert_nodes(
                DOCUMENT_LABEL,
                [
                    build_document_record(document)
                    for document in distinct_documents(documents)
                ],
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

    # Global exact-match + in-batch resolution (buffered over whole call)
    exact_matches = await _global_exact_match(entities, graph_store=graph_store)

    # Build chunks_by_id for LLMVerify
    chunks_by_id: dict[UUID, Chunk] = {}
    for ch in chunks:
        if ch.id is not None:
            chunks_by_id[ch.id] = ch

    # Resolver: ExactMatch, FuzzyMatch, LLMVerify
    resolver = Resolver(
        comparators=[
            ExactMatch(),
            FuzzyMatch(),
            LLMVerify(chunks_by_id=chunks_by_id),
        ],
        candidate_source=InBatchCandidateSource(),
    )
    resolution_result = await resolver.resolve(entities) if entities else None
    semantic_groups = resolution_result.groups if resolution_result is not None else []
    groups = exact_resolution_groups(entities, exact_matches)

    # Compute resolution stats
    exact_match_hits = len(exact_matches)
    # Groups include singletons; in_batch_groups is resolver group count.
    # ambiguous_count: no direct metric yet, use 0.
    resolution = ResolutionStats(
        exact_match_hits=exact_match_hits,
        in_batch_groups=len(semantic_groups),
        ambiguous_count=0,
    )

    # Merge and write
    merge_stats = MergeStats()
    storage_stats = StorageStats()
    merge_failures: list[StageFailure] = []

    # Track survivors and mention->entity map
    mention_to_entity: dict[int, UUID] = {}
    survivors: dict[UUID, Entity] = {}
    resolved_vector_failures: list[StageFailure] = []
    # For storage stats counting
    nodes_created = 0
    nodes_updated = 0
    nodes_merged = 0
    conflicts_resolved = 0

    for group in groups:
        group_indices = list(group.entity_indices)
        group_mentions = [entities[i] for i in group_indices]

        # Collect distinct existing entities for this group
        existing_for_group: list[Entity] = []
        seen_ids: set[UUID] = set()
        for idx in group_indices:
            ent = exact_matches.get(idx)
            if ent is not None and ent.id not in seen_ids:
                seen_ids.add(ent.id)
                existing_for_group.append(ent)

        # Compute merge
        try:
            plan, desc_failures = await compute_merge(
                existing_entities=existing_for_group,
                mentions=group_mentions,
                schema=graph_schema,
            )
        except Exception as exc:  # noqa: BLE001
            if error_policy is ErrorPolicy.RAISE:
                raise
            merge_failures.append(
                StageFailure(
                    item_id=",".join(str(entities[i].text) for i in group_indices),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )
            continue

        if desc_failures:
            merge_failures.extend(desc_failures)  # type: ignore[arg-type]

        conflicts_resolved += len(plan.conflicts)

        # Track merge stats
        if not existing_for_group:
            nodes_created += 1
        elif len(existing_for_group) == 1:
            nodes_updated += 1
        else:
            # Tombstone case: survivor + absorbed
            nodes_merged += len(plan.tombstone_ids)
            # nodes_merged counts tombstoned; survivor is already existing
            # so no nodes_created/updated increment for multi-merge.
            pass

        # Apply merge (writes survivor and handles tombstone)
        try:
            plan, retry_desc_failures = await _apply_merge_with_conflict_retry(
                plan,
                graph_store=graph_store,
                schema=graph_schema,
                existing_entities=existing_for_group,
                mentions=group_mentions,
                is_new_entity=not existing_for_group,
            )
            if retry_desc_failures:
                merge_failures.extend(retry_desc_failures)
            if plan.tombstone_ids:
                try:
                    await _delete_vectors(
                        vector_store,
                        retrieval_settings.entity_collection,
                        list(plan.tombstone_ids),
                    )
                except Exception as exc:  # noqa: BLE001
                    if error_policy is ErrorPolicy.RAISE:
                        raise
                    merge_failures.append(
                        StageFailure(
                            item_id="tombstone_vector_store",
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            if error_policy is ErrorPolicy.RAISE:
                raise
            merge_failures.append(
                StageFailure(
                    item_id=str(plan.survivor.id),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )
            continue

        survivors[plan.survivor.id] = plan.survivor
        for idx in group_indices:
            mention_to_entity[idx] = plan.survivor.id

    if resolution_result is not None:
        persisted_mentions: list[ExtractedEntity] = list(entities)
        persisted_candidates: dict[int, list[int]] = {}
        persisted_ids: dict[int, UUID] = {}
        candidate_entities: dict[UUID, Entity] = {}
        candidate_source = GraphCandidateSource(
            graph_store=graph_store,
            embedder=embedder,
            vector_store=vector_store,
            vector_collection=retrieval_settings.entity_collection,
            entity_labels=[entity.label for entity in graph_schema.entities],
        )
        for mention_index, mention in enumerate(entities):
            try:
                candidates = await candidate_source.global_candidates_for(mention)
            except Exception:  # noqa: BLE001
                candidates = []
            for candidate in candidates:
                if candidate.id == mention_to_entity.get(mention_index):
                    continue
                candidate_index = len(persisted_mentions)
                candidate_mention, candidate_chunk = _synthetic_entity_mention(
                    candidate
                )
                persisted_mentions.append(candidate_mention)
                chunks_by_id[candidate_mention.chunk_id] = candidate_chunk
                persisted_candidates.setdefault(mention_index, []).append(
                    candidate_index
                )
                persisted_ids[candidate_index] = candidate.id
                candidate_entities[candidate.id] = candidate
        if persisted_candidates:
            persisted_result = await Resolver(
                comparators=[
                    ExactMatch(),
                    FuzzyMatch(),
                    LLMVerify(chunks_by_id=chunks_by_id),
                ],
                candidate_source=PersistedCandidateSource(persisted_candidates),
            ).resolve(persisted_mentions)
            resolution_result.matches.extend(persisted_result.matches)
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
            try:
                materialization = await write_matches_and_materialize(
                    decisions,
                    graph_store=graph_store,
                    schema=graph_schema,
                    members=members,
                )
            except Exception as exc:  # noqa: BLE001
                if error_policy is ErrorPolicy.RAISE:
                    raise
                merge_failures.append(
                    StageFailure(
                        item_id=",".join(str(member_id) for member_id in member_ids),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
                continue
            # Synchronized per component, not batched after the loop: a
            # later component's failure under ErrorPolicy.RAISE must not
            # skip vector cleanup for components already committed above.
            resolved_vector_failures.extend(
                await _synchronize_resolved_entity_vectors(
                    [materialization.resolved_entity],
                    materialization.removed_entity_ids,
                    embedder=embedder,
                    graph_store=graph_store,
                    vector_store=vector_store,
                    vector_collection=retrieval_settings.resolved_entity_collection,
                    error_policy=error_policy,
                )
            )

    # If there were no entities (empty corpus) we have no survivors
    # but we still need to write chunks

    merge_failures_capped = cap_failures(merge_failures)
    merge_stats = MergeStats(
        nodes_created=nodes_created,
        nodes_updated=nodes_updated,
        nodes_merged=nodes_merged,
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
        triples_list, graph_store=graph_store
    )

    # Materialize Relation objects
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

    # MENTIONED_IN edges: one per (chunk, entity) pair
    mentioned_pairs: set[tuple[UUID, UUID]] = set()
    for idx, entity_id in mention_to_entity.items():
        # mention's chunk_id
        chunk_id = entities[idx].chunk_id
        mentioned_pairs.add((chunk_id, entity_id))

    # Look up by endpoint rather than trusting mentioned_in_id() alone:
    # an entity merge transfers a MENTIONED_IN edge onto a new endpoint
    # but keeps its old, tombstone-derived id (transfer_relationships_
    # query copies the edge's existing properties, including id, as-is).
    # Recomputing the id from the current (chunk, entity) pair would
    # then miss that edge and create a parallel one on re-ingest.
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
            relation_storage_failures.append(
                StageFailure(
                    item_id=str(ch.id),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )
            continue

    # Document nodes and PART_OF edges: one Document per distinct document
    # in this call, PART_OF linking it to the chunks written above.
    distinct = distinct_documents(documents)
    documents_by_key = {doc.resolved_document_key: doc for doc in distinct}
    selected_document_ids = {
        Document.node_id_for(document_key=document_key)
        for document_key in documents_by_key
    }
    chunks_by_document_id: dict[UUID, list[Chunk]] = defaultdict(list)
    for ch in chunks:
        if ch.document_id in selected_document_ids:
            chunks_by_document_id[ch.document_id].append(ch)
    documents_by_id = {
        Document.node_id_for(document_key=document_key): document
        for document_key, document in documents_by_key.items()
    }
    document_records = [build_document_record(doc) for doc in documents_by_id.values()]
    for document_id, document in documents_by_id.items():
        document_node_id = Document.node_id_for(
            document_key=document.resolved_document_key
        )
        # The version matches chunk versioning's own version_id, so an
        # identical re-ingest rebuilds the same edge ids and converges.
        version_id = str(Document.id_for(content_hash=document.content_hash))
        relation_records.extend(
            build_part_of_records(
                document_node_id,
                chunks_by_document_id.get(document_id, []),
                version_id=version_id,
            )
        )
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
    try:
        if chunk_records:
            # Grouping handled inside upsert_nodes
            write_result = await graph_store.upsert_nodes(CHUNK_LABEL, chunk_records)
            nodes_written += write_result.written
            storage_failures.extend(_upsert_stage_failures(write_result))
            chunk_failure_ids = set()
            for failure in write_result.failures:
                try:
                    chunk_failure_ids.add(UUID(failure.id))
                except ValueError:
                    continue
            chunks_written = True
    except Exception as exc:  # noqa: BLE001
        if error_policy is ErrorPolicy.RAISE:
            raise
        storage_failures.append(
            StageFailure(
                item_id="chunks",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        )

    # Write Document nodes
    try:
        if document_records:
            await graph_store.upsert_nodes(DOCUMENT_LABEL, document_records)
            nodes_written += len(document_records)
    except Exception as exc:  # noqa: BLE001
        if error_policy is ErrorPolicy.RAISE:
            raise
        storage_failures.append(
            StageFailure(
                item_id="documents",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        )

    # Chunk embedding stage: embed chunks and write vectors. When the node
    # write failed, upsert_nodes may still have committed its earlier
    # batches, so embed whichever of this call's chunks the graph holds
    # instead of leaving them unsearchable until the source is re-ingested.
    embeddable_ids = chunk_ids - chunk_failure_ids
    if not chunks_written:
        embeddable_ids = await _persisted_chunk_ids(graph_store, chunk_ids)
    if embeddable_ids:
        storage_failures.extend(
            await _embed_and_upsert_chunks(
                [chunk for chunk in chunks if chunk.id in embeddable_ids],
                embedder=embedder,
                graph_store=graph_store,
                error_policy=error_policy,
                vector_store=vector_store,
                vector_collection=retrieval_settings.chunk_collection,
            )
        )

    # Survivors already written via apply_merge; count them.
    nodes_written += len(survivors)

    # Write domain relations
    try:
        if relation_records:
            write_result = await graph_store.upsert_relations(relation_records)
            relationships_written_count += write_result.written
            storage_failures.extend(_upsert_stage_failures(write_result))
    except Exception as exc:  # noqa: BLE001
        if error_policy is ErrorPolicy.RAISE:
            raise
        storage_failures.append(
            StageFailure(
                item_id="relations",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        )

    try:
        if mentioned_in_records:
            write_result = await graph_store.upsert_relations(mentioned_in_records)
            relationships_written_count += write_result.written
            storage_failures.extend(_upsert_stage_failures(write_result))
    except Exception as exc:  # noqa: BLE001
        if error_policy is ErrorPolicy.RAISE:
            raise
        storage_failures.append(
            StageFailure(
                item_id="MENTIONED_IN",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        )

    # Embedding stage: embed survivors and update them.
    if survivors:
        storage_failures.extend(
            await _embed_and_upsert_survivors(
                survivors,
                embedder=embedder,
                graph_store=graph_store,
                error_policy=error_policy,
                vector_store=vector_store,
                vector_collection=retrieval_settings.entity_collection,
                labels_by_id={ent.id: ent.label for ent in survivors.values()},
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
    return [
        StageFailure(
            item_id=failure.id,
            error_type=failure.error_type,
            error_message=failure.error_message,
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
) -> None:
    """Upsert records to the VectorStore when one is configured.

    Records whose vector is empty are skipped: an embed failure leaves
    None on the domain object, and an empty vector cannot be searched, so
    writing it would only corrupt the collection.

    Args:
        vector_store: The store to write to, or None to do nothing.
        collection: The collection name to write into.
        records: The records to upsert.
    """
    if vector_store is None:
        return
    writable = [record for record in records if record.vector]
    if not writable:
        return
    await vector_store.upsert(collection, writable)


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
    graph_store: GraphStore, chunk_ids: set[UUID]
) -> set[UUID]:
    """Return the subset of chunk_ids that exist as Chunk nodes.

    ``upsert_nodes`` writes its batches in sequence, so a failure partway
    through leaves the earlier batches committed. Embedding only the ids the
    graph really holds keeps those chunks searchable and keeps a chunk that
    never landed out of the VectorStore.

    Args:
        graph_store: Where the chunk nodes are read.
        chunk_ids: The ids this call tried to write.

    Returns:
        The ids found, or an empty set when the graph cannot be read. The
        caller then skips the embedding stage, which is what it did for every
        chunk before the partial write was accounted for.
    """
    if not chunk_ids:
        return set()
    try:
        rows = await graph_store.execute_read(
            hydrate_chunks_by_id_query(), {"ids": [str(cid) for cid in chunk_ids]}
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


def _parse_entity_node(node: object) -> Entity | None:  # noqa: PLR0912,PLR0915
    """Parse a GraphStore node row into an Entity.

    Handles both neo4j Node objects and plain dict mocks used in unit tests.
    """
    try:
        props: dict = {}
        labels: list[str] = []
        node_id: object = None

        if isinstance(node, dict) and "labels" in node and "properties" in node:
            # Mock form: {"id": "...", "labels": [...], "properties": {...}}
            labels = list(node.get("labels") or [])
            props = dict(node.get("properties") or {})
            node_id = node.get("id") or props.get("id")
        elif isinstance(node, dict) and "id" in node:
            # Flat mock where properties are top-level alongside id/labels
            # e.g. {"n": {"id": "...", "name": "...", "merge_key": "..."}}
            # But here node is that inner dict.
            props = dict(node)
            # id may be in props
            node_id = props.get("id")
            # labels might be in props or separate
            maybe_labels = props.pop("labels", None)
            if isinstance(maybe_labels, list):
                labels = maybe_labels
            # Try to get labels from node dict if present alongside
            if not labels and "labels" in props:
                labels = props.pop("labels")  # type: ignore[assignment]
        else:
            # Attempt neo4j Node: dict(node) gives properties, node.labels gives labels
            try:
                props = dict(node)  # ty: ignore[no-matching-overload]  # type: ignore[arg-type]
            except Exception:
                props = {}
            try:
                maybe_labels = getattr(node, "labels", None)
                if maybe_labels is not None:
                    labels = list(maybe_labels)  # type: ignore[arg-type]
            except Exception:
                labels = []
            # Try id from props or node["id"]
            try:
                node_id = props.get("id")  # type: ignore[union-attr]
            except Exception:
                node_id = None
            if node_id is None:
                with contextlib.suppress(Exception):
                    node_id = node["id"]  # type: ignore[index]  # ty: ignore[not-subscriptable]
            # Node may also be wrapped as {"n": Node}
            if isinstance(node, dict) and "n" in node:
                return _parse_entity_node(node["n"])

        if node_id is None:
            # Fallback: id inside props
            node_id = props.get("id")

        # Determine label
        label: str | None = None
        if labels:
            for lbl in labels:
                if lbl not in (NODE_IDENTITY_LABEL, CHUNK_LABEL):
                    label = str(lbl)
                    break
            if label is None:
                # All labels were system labels, take first
                label = str(labels[0]) if labels else None
        if label is None:
            # Fallback from merge_key
            mk = props.get("merge_key") or ""
            if isinstance(mk, str) and ":" in mk:
                label = mk.split(":", 1)[0]

        if label is None or node_id is None:
            return None

        # System keys not part of domain properties
        system_keys = {
            "name",
            "merge_key",
            "merged_from",
            "merge_count",
            "source_chunk_ids",
            "created_at",
            "embedding",
            "id",
        }
        entity_props = {k: v for k, v in props.items() if k not in system_keys}

        merged_from_raw = props.get("merged_from") or []
        merged_from = [UUID(str(x)) for x in merged_from_raw if x]

        try:
            merge_count = int(props.get("merge_count", 1))
        except Exception:
            merge_count = 1

        scids_raw = props.get("source_chunk_ids") or []
        scids = [UUID(str(x)) for x in scids_raw if x]

        embedding = props.get("embedding")

        created_at_raw = props.get("created_at")
        created_at = None
        if isinstance(created_at_raw, str):
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except Exception:
                created_at = None

        name_val = props.get("name")
        if name_val is None:
            mk = props.get("merge_key", "")
            if isinstance(mk, str) and ":" in mk:
                name_val = mk.split(":", 1)[1]
            else:
                name_val = mk or ""

        kwargs: dict = {
            "id": UUID(str(node_id)),
            "label": label,
            "name": str(name_val),
            "properties": entity_props,
            "merged_from": merged_from,
            "merge_count": merge_count,
            "source_chunk_ids": scids,
        }
        if embedding is not None:
            kwargs["embedding"] = list(embedding)  # type: ignore[arg-type]
        if created_at is not None:
            kwargs["created_at"] = created_at
        return Entity(**kwargs)
    except Exception:
        return None


def _extract_merged_into(node: object, row: object) -> str | None:
    """Return a tombstone's ``merged_into`` id if present, else ``None``.

    Callers read ``None`` as "this node is live" -- so, unlike the two
    inner probes below, nothing here is allowed to turn a genuine failure
    into ``None``. Each probe tries one node representation (plain dict
    properties, a dict-convertible driver object, an attribute-bearing
    driver object) and is individually suppressed only because failing to
    apply does not mean the node lacks ``merged_into``, just that this
    particular representation does not match; there is always another probe
    or the final "no candidates found" fallthrough to answer that. Nothing
    past those probes suppresses errors, so a genuine bug -- for example an
    id that cannot be stringified -- propagates instead of being silently
    read as "live".
    """
    candidates: list[object] = []
    if isinstance(node, dict):
        props = node.get("properties") if "properties" in node else None
        if isinstance(props, dict) and props.get("merged_into"):
            candidates.append(props["merged_into"])
        if node.get("merged_into"):
            candidates.append(node["merged_into"])
    else:
        with contextlib.suppress(Exception):
            props = dict(node)  # ty: ignore[no-matching-overload]  # type: ignore[arg-type]
            if isinstance(props, dict) and props.get("merged_into"):
                candidates.append(props["merged_into"])
        with contextlib.suppress(Exception):
            val = getattr(node, "merged_into", None)
            if val:
                candidates.append(val)
    if isinstance(row, dict) and row.get("merged_into"):
        candidates.append(row["merged_into"])
    if candidates:
        return str(candidates[0])
    return None


_MAX_TOMBSTONE_CHAIN_HOPS = 32


async def _resolve_tombstone_chain(
    *,
    start_merged_into: str,
    graph_store: GraphStore,
) -> Entity:
    """Follow ``merged_into`` pointers until the live survivor is reached.

    Args:
        start_merged_into: The id the first tombstone points at.
        graph_store: Where the chain is read from.

    Returns:
        The live entity at the end of the chain -- never a tombstone.

    Raises:
        GraphStoreDataIntegrityError: The chain cycles, points at a missing
            node, the live node at its end cannot be parsed as an Entity, or
            the chain exceeds ``_MAX_TOMBSTONE_CHAIN_HOPS`` hops without
            reaching a live node. A store read failure propagates as-is,
            unwrapped.
    """
    visited: set[str] = set()
    current_id = start_merged_into
    for _ in range(_MAX_TOMBSTONE_CHAIN_HOPS):
        if current_id in visited:
            raise GraphStoreDataIntegrityError(
                f"merged_into cycle detected resolving tombstone chain from "
                f"{start_merged_into!r} (revisited {current_id!r})"
            )
        visited.add(current_id)
        rows = await graph_store.execute_read(
            f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: $id}}) RETURN n",
            {"id": current_id},
        )
        if not rows:
            raise GraphStoreDataIntegrityError(
                f"tombstone chain from {start_merged_into!r} points at "
                f"missing node {current_id!r}"
            )
        row = rows[0]
        node = (
            row.get("n") if isinstance(row, dict) and "n" in row else row  # type: ignore[union-attr]
        )
        # An intermediate tombstone's own node is never parsed: a real
        # driver row carries no "labels" key for a plain RETURN n, and
        # clear_tombstone_merge_keys_query already stripped merge_key --
        # _parse_entity_node's label fallbacks both come up empty, even
        # though this hop is not what the caller ultimately needs.
        next_id = _extract_merged_into(node, row)
        if next_id is not None:
            current_id = next_id
            continue
        entity = _parse_entity_node(node) or _parse_entity_node(row)  # type: ignore[arg-type]
        if entity is None:
            raise GraphStoreDataIntegrityError(
                f"tombstone chain from {start_merged_into!r} reached "
                f"unparsable node {current_id!r}"
            )
        return entity
    raise GraphStoreDataIntegrityError(
        f"tombstone chain from {start_merged_into!r} exceeded "
        f"{_MAX_TOMBSTONE_CHAIN_HOPS} hops without reaching a live node"
    )


async def _global_exact_match(
    mentions: list[ExtractedEntity], *, graph_store: GraphStore
) -> dict[int, Entity]:
    """Return each mention index's matching persisted Entity, if it has one.

    One batched read per distinct label present in mentions. A row is
    mapped back to its mention(s) by the merge_key the row's alias was
    matched on -- returned alongside the node by fetch_by_merge_keys_query
    -- rather than by re-deriving a key from the resolved entity's current
    name: an accepted alias can name an entity by something other than its
    current canonical name (see upsert_merge_alias_query), so re-deriving
    would silently fail to map those mentions back. A row that turns out to
    be a tombstone has its merged_into chain followed to the live survivor
    first; older rows without a returned merge_key (plain mocks) fall back
    to the resolved entity's own merge_key.

    Args:
        mentions: The entity mentions to look up.
        graph_store: Where the lookup runs.

    Returns:
        A map from mention index to its matching Entity.

    Raises:
        GraphStoreDataIntegrityError: A matched row's merged_into chain
            could not be resolved to a live entity.
    """
    if not mentions:
        return {}
    grouped: dict[str, list[str]] = defaultdict(list)
    mk_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, mention in enumerate(mentions):
        mk = f"{mention.label}:{normalize_text(mention.text)}"
        grouped[mention.label].append(mk)
        mk_to_indices[mk].append(idx)

    result: dict[int, Entity] = {}
    for _label, mks in grouped.items():
        unique_mks = list(dict.fromkeys(mks))
        if not unique_mks:
            continue
        rows = await graph_store.execute_read(
            fetch_by_merge_keys_query(), {"merge_keys": unique_mks}
        )
        for row in rows:
            node = row.get("n") if isinstance(row, dict) and "n" in row else row
            # A tombstone's own node is never parsed: a real driver row
            # carries no "labels" key for a plain RETURN n, and
            # clear_tombstone_merge_keys_query already stripped merge_key --
            # _parse_entity_node's label fallbacks both come up empty, even
            # though the alias lookup only needs the live entity at the end
            # of merged_into, not this row's own node.
            merged_into = _extract_merged_into(node, row)
            if merged_into is not None:
                entity = await _resolve_tombstone_chain(
                    start_merged_into=merged_into, graph_store=graph_store
                )
            else:
                entity = _parse_entity_node(node) or _parse_entity_node(row)
                if entity is None:
                    continue
            queried_mk = row.get("merge_key") if isinstance(row, dict) else None
            mk = queried_mk if isinstance(queried_mk, str) else entity.merge_key
            for idx in mk_to_indices.get(mk, []):
                if mentions[idx].label == entity.label:
                    result[idx] = entity
    return result


async def _global_relation_lookup(
    triples: list[tuple[UUID, UUID, str]], *, graph_store: GraphStore
) -> dict[tuple[UUID, UUID, str], tuple[UUID, list[UUID]]]:
    """Return each triple's already-persisted relation id and source_chunk_ids.

    One batched read per distinct relation type present in triples.

    Args:
        triples: The (source_id, target_id, type) triples to look up.
        graph_store: Where the lookup runs.

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
        query = fetch_relations_between_query(rel_type)
        rows = await graph_store.execute_read(query, {"pairs": params})
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


def _synthetic_entity_mention(entity: Entity) -> tuple[ExtractedEntity, Chunk]:
    """Build a mention and distinct name context for a persisted raw entity."""
    chunk_id = uuid4()
    chunk = Chunk(
        id=chunk_id,
        document_id=chunk_id,
        index=0,
        text=entity.name,
        provenance=TextProvenance(char_start=0, char_end=len(entity.name)),
    )
    return (
        ExtractedEntity(
            chunk_id=chunk_id,
            label=entity.label,
            text=entity.name,
            char_start=0,
            char_end=len(entity.name),
        ),
        chunk,
    )


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
) -> list[StageFailure]:
    """Embed every chunk's text and write the vectors back onto their nodes.

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
    hydrates every hit from the graph, so only that record's score is
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

    Returns:
        One StageFailure per chunk whose embed or write step raised.

    Raises:
        Exception: Whatever embed() or the write raised, when
            error_policy is RAISE.
    """
    try:
        texts = [ch.text for ch in chunks]
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
        await graph_store.execute_write(
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
        return [
            StageFailure(
                item_id="chunk_embeddings",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        ]
    if vector_store is not None:
        vector_records = []
        for ch in chunks:
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
            await _upsert_vectors(vector_store, vector_collection, vector_records)
        except Exception as exc:  # noqa: BLE001
            if error_policy is ErrorPolicy.RAISE:
                raise
            return [
                StageFailure(
                    item_id="chunk_vector_store",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
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
    name/description still match what this call started with. add() and
    consolidate(apply=True) can run concurrently against the same entity
    (see _apply_merge_with_conflict_retry), so without this guard an older,
    slower call's write or clear can land after a newer call's and leave a
    vector computed for stale text, or wipe a vector the newer call just
    wrote.

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
        await graph_store.execute_write(
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
        return [
            StageFailure(
                item_id="embeddings",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        ]
    if vector_store is not None:
        label_map = labels_by_id or {}
        vector_records = [
            _vector_record(
                ent.id,
                ent.embedding or [],
                label=label_map.get(ent.id, ""),
                text=ent.embedding_text,
                properties=dict(ent.properties),
            )
            for ent in survivors.values()
        ]
        try:
            await _upsert_vectors(vector_store, vector_collection, vector_records)
        except Exception as exc:  # noqa: BLE001
            if error_policy is ErrorPolicy.RAISE:
                raise
            return [
                StageFailure(
                    item_id="entity_vector_store",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            ]
    return []


async def _apply_merge_with_conflict_retry(
    plan: MergePlan,
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    existing_entities: list[Entity],
    mentions: list[ExtractedEntity],
    is_new_entity: bool,
) -> tuple[MergePlan, list[Any]]:
    """Apply a merge plan, recovering once from a concurrent race.

    Two distinct races can surface here, both as a
    GraphStoreConstraintViolationError:

    - A brand-new entity's write can lose a create race: two concurrent
      add() calls resolving the same normalized name each run their
      exact-match lookup before either has written anything, so neither
      sees the other, and both then try to create a live node for the same
      merge_key. merge_key_constraint_query rejects whichever write lands
      second; this recovers by re-resolving the name to whichever entity
      won the race and merging into it instead, the way a normal update
      would have if the exact-match lookup had seen it in time. Only
      possible when is_new_entity, since updating an already-known
      canonical entity writes that entity's own already-established
      merge_key, which cannot newly collide.
    - An accepted merge_key -- one of the group's mention- or
      absorbed-entity-derived names, not necessarily the survivor's own --
      can be claimed, mid-transaction, by a live entity outside this
      merge's own survivor/tombstone set: for example, one writer creates a
      canonical entity named "Bob" while this call separately resolves
      "Bob" as an accepted alias of a different canonical entity named
      "Robert". Neither writer's own node merge_key collides in that case,
      so apply_merge raises GraphStoreAliasConflictError itself instead of
      relying on the backend's constraint. This recovers by re-resolving
      every conflicting merge_key to its real owner and recomputing the
      merge with those owners folded into existing_entities. Possible
      whether or not is_new_entity, since it is unrelated to whether the
      survivor's own node is new.

    Args:
        plan: The merge to apply.
        graph_store: Where the merge is written.
        schema: The schema the survivor's label belongs to.
        existing_entities: The persisted entities plan was originally
            computed from, needed to recompute the merge with a
            newly-discovered conflicting entity folded in.
        mentions: The mentions compute_merge originally folded into plan,
            needed to recompute the merge against the real canonical entity.
        is_new_entity: Whether plan was building a brand-new entity (no
            existing_entities) -- gates recovery from a bare create-race
            constraint violation, the only case that can mean.

    Returns:
        The plan that was actually applied (plan itself, or the recomputed
        one after recovering from a conflict) and any description-LLM
        failures the recovery's own compute_merge call raised.

    Raises:
        GraphStoreConstraintViolationError: The violation was not a race
            this can recover from (a create-race violation on a non-new
            entity, or an owner that still cannot be found after retry).
    """
    try:
        await apply_merge(plan, graph_store=graph_store, schema=schema)
        return plan, []
    except GraphStoreAliasConflictError as exc:
        label = plan.survivor.label
        synthetics = []
        for merge_key in exc.conflicts:
            name = merge_key.removeprefix(f"{label}:")
            synthetics.append(
                ExtractedEntity(
                    chunk_id=uuid4(),
                    label=label,
                    text=name,
                    char_start=0,
                    char_end=len(name),
                )
            )
        resolved = await _global_exact_match(synthetics, graph_store=graph_store)
        if len(resolved) != len(synthetics):
            raise
        owners = {entity.id: entity for entity in resolved.values()}
        merged_existing = list(
            {
                entity.id: entity for entity in [*existing_entities, *owners.values()]
            }.values()
        )
        retried_plan, desc_failures = await compute_merge(
            existing_entities=merged_existing, mentions=mentions, schema=schema
        )
        await apply_merge(retried_plan, graph_store=graph_store, schema=schema)
        return retried_plan, desc_failures
    except GraphStoreConstraintViolationError:
        if not is_new_entity:
            raise
        synthetic = ExtractedEntity(
            chunk_id=uuid4(),
            label=plan.survivor.label,
            text=plan.survivor.name,
            char_start=0,
            char_end=len(plan.survivor.name),
        )
        resolved = await _global_exact_match([synthetic], graph_store=graph_store)
        canonical = resolved.get(0)
        if canonical is None:
            raise
        retried_plan, desc_failures = await compute_merge(
            existing_entities=[canonical], mentions=mentions, schema=schema
        )
        await apply_merge(retried_plan, graph_store=graph_store, schema=schema)
        return retried_plan, desc_failures
