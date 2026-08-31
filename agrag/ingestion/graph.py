"""The public Graph API for ingestion."""

import asyncio
import contextlib
import glob
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Union
from uuid import UUID, uuid4

from opentelemetry.trace import Tracer

import agrag.loaders.docling  # noqa: F401  (registers the docling loaders)
from agrag.chunking import default_chunker
from agrag.chunking.text import chunk_document
from agrag.common.data_models.chunk import CHUNK_LABEL, Chunk
from agrag.common.data_models.document import Document
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity, ExtractedRelation
from agrag.common.data_models.graph_record import RelationRecord
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.relation import Relation
from agrag.common.text import normalize_text
from agrag.cypher.entities import (
    NODE_IDENTITY_LABEL,
    clear_property_query,
    fetch_all_by_label_query,
    fetch_by_merge_keys_query,
    fetch_relations_between_query,
)
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.ingestion.extract import Extractor
from agrag.ingestion.merge import (
    apply_merge,
    compute_merge,
    mentioned_in_id,
    relation_id,
)
from agrag.ingestion.resolve import (
    ExactMatch,
    FuzzyMatch,
    InBatchCandidateSource,
    LLMVerify,
    Resolver,
)
from agrag.ingestion.types import (
    AddResult,
    ConsolidationReport,
    ExtractionStats,
    IngestStats,
    MergeStats,
    ResolutionStats,
    StageFailure,
    StorageStats,
    _capped,
)
from agrag.loaders.corpus import registry as _corpus_registry
from agrag.loaders.corpus._walk import _CorpusWalk, _InMemoryWalk
from agrag.loaders.corpus.base import Loader
from agrag.loaders.corpus.types import ErrorPolicy, LoadStats, ReadOptions
from agrag.loaders.docling.chunking import chunk_docling_document
from agrag.observability import get_tracer, traced


SourceType = Union[str, Path]
SourcesType = Union[SourceType, Sequence[SourceType]]

# Relationship types Graph.open() always registers
SYSTEM_RELATION_TYPES = ["MENTIONED_IN"]


def _resolve_paths(source: SourcesType) -> tuple[list[Path], bool]:
    """Expand a source argument into concrete file paths.

    Args:
        source: A file path, a directory, a glob, or a list of these.

    Returns:
        The resolved file paths in sorted order and whether the input was a single plain
        file (not a directory or glob).
    """
    items = source if isinstance(source, (list, tuple)) else [source]
    paths: list[Path] = []
    single_file = len(items) == 1
    for item in items:
        text = str(item)
        path = Path(text)
        if path.is_dir():
            single_file = False
            paths.extend(sorted(p for p in path.rglob("*") if p.is_file()))
        elif any(ch in text for ch in "*?["):
            single_file = False
            paths.extend(
                sorted(
                    Path(m)
                    for m in glob.glob(text, recursive=True)
                    if Path(m).is_file()
                )
            )
        else:
            paths.append(path)
    return paths, single_file


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
    """Return a tombstone's ``merged_into`` id if present, else ``None``."""
    try:
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
    except Exception:
        return None
    return None


def _extract_raw_merge_key(node: object) -> str | None:
    """Return the raw ``merge_key`` from a node dict without parsing."""
    try:
        if isinstance(node, dict):
            if "properties" in node and isinstance(node["properties"], dict):
                val = node["properties"].get("merge_key")
                if isinstance(val, str):
                    return val
            val = node.get("merge_key")
            if isinstance(val, str):
                return val
        else:
            with contextlib.suppress(Exception):
                props = dict(node)  # ty: ignore[no-matching-overload]  # type: ignore[arg-type]
                if isinstance(props, dict):
                    val = props.get("merge_key")
                    if isinstance(val, str):
                        return val
    except Exception:
        return None
    return None


async def _resolve_tombstone_chain(
    *,
    start_merged_into: str,
    graph_store: GraphStore,
) -> Entity | None:
    """Follow ``merged_into`` pointers until the live survivor is reached."""
    visited: set[str] = set()
    current_id: str | None = start_merged_into
    survivor: Entity | None = None
    for _ in range(32):
        if current_id is None or current_id in visited:
            break
        visited.add(current_id)
        try:
            rows = await graph_store.execute_read(
                f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: $id}}) RETURN n",
                {"id": current_id},
            )
        except Exception:
            break
        if not rows:
            break
        row = rows[0]
        node = (
            row.get("n") if isinstance(row, dict) and "n" in row else row  # type: ignore[union-attr]
        )
        entity = _parse_entity_node(node) or _parse_entity_node(row)  # type: ignore[arg-type]
        if entity is None:
            break
        survivor = entity
        next_id = _extract_merged_into(node, row)
        if next_id is None or next_id in visited:
            break
        current_id = next_id
    return survivor


async def _global_exact_match(  # noqa: PLR0912,PLR0915
    mentions: list[ExtractedEntity], *, graph_store: GraphStore
) -> dict[int, Entity]:
    """Return each mention index's matching persisted Entity, if it has one.

    One batched read per distinct label present in mentions. Tombstoned
    nodes are never returned — if the matched row is a tombstone (older data
    where ``merge_key`` was not yet cleared), the ``merged_into`` chain is
    followed to its live survivor.

    Args:
        mentions: The entity mentions to look up.
        graph_store: Where the lookup runs.

    Returns:
        A map from mention index to its matching Entity.
    """
    if not mentions:
        return {}
    # Group merge keys by label.
    grouped: dict[str, list[str]] = defaultdict(list)
    mk_for_index: dict[int, str] = {}
    mk_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, mention in enumerate(mentions):
        mk = f"{mention.label}:{normalize_text(mention.text)}"
        grouped[mention.label].append(mk)
        mk_for_index[idx] = mk
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
            # Row may be {"n": Node} or {"n": {...}} or just node dict
            node = row.get("n") if isinstance(row, dict) and "n" in row else row
            # In some mocks, row is {"n": {...}} where inner has properties
            # _parse handles both.
            entity = _parse_entity_node(node)
            if entity is None:
                # Try alternative: row itself may be node props flat
                # e.g. row = {"id": "...", "merge_key": "...", ...}
                entity = _parse_entity_node(row)
            if entity is None:
                continue
            # If this row is a tombstone, follow its merged_into chain to
            # the live survivor. The new query filters tombstones, but this
            # handles data written before REMOVE merge_key was added.
            merged_into = _extract_merged_into(node, row)
            raw_mk = _extract_raw_merge_key(node)
            if merged_into is not None:
                raw_for_mapping = raw_mk or entity.merge_key
                survivor = await _resolve_tombstone_chain(
                    start_merged_into=merged_into, graph_store=graph_store
                )
                if survivor is None:
                    continue
                entity = survivor
                # Map via the original tombstone's merge_key first so exact-
                # match tier resolves re-ingest of the absorbed name to its
                # survivor even when survivor's own merge_key differs.
                if raw_for_mapping in mk_to_indices:
                    for idx in mk_to_indices[raw_for_mapping]:
                        if mentions[idx].label == entity.label:
                            result[idx] = entity
                mk = entity.merge_key
                for idx in mk_to_indices.get(mk, []):
                    if mentions[idx].label == entity.label:
                        result[idx] = entity
                continue
            mk = entity.merge_key
            for idx in mk_to_indices.get(mk, []):
                # Only map if mention label matches entity label (should)
                if mentions[idx].label == entity.label:
                    result[idx] = entity
            # Also handle case where row's merge_key directly maps
            # For mocks that return merge_key without normalized parsing,
            # try to map via raw mk.
            # If entity.merge_key not in map, try row's merge_key
            if mk not in mk_to_indices:
                # Try to extract merge_key from props directly
                try:
                    raw_mk2 = raw_mk
                    if raw_mk2 is None and isinstance(node, dict):
                        if "properties" in node:
                            raw_mk2 = node["properties"].get("merge_key")
                        else:
                            raw_mk2 = node.get("merge_key") or node.get("merge_key")
                    if raw_mk2:
                        for idx in mk_to_indices.get(str(raw_mk2), []):
                            if idx not in result:
                                result[idx] = entity
                except Exception:
                    pass
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


class Graph:
    """A knowledge graph that a caller can open and add content to."""

    def __init__(
        self,
        *,
        schema: GraphSchema,
        graph_store: GraphStore,
        embedder: Embedder,
        extractor: Extractor,
        tracer: Tracer | None = None,
    ) -> None:
        """Create a graph bound to a schema, store, embedder, and extractor.

        Args:
            schema: The entity/relation types this graph validates every
                extraction against.
            graph_store: Where entities, relations, chunks, and MENTIONED_IN
                edges are written.
            embedder: Populates entity embeddings for native vector search.
            extractor: Runs against each chunk.
            tracer: A tracer to record spans for every step. Pass None for none.
        """
        self._schema = schema
        self._graph_store = graph_store
        self._embedder = embedder
        self._extractor = extractor
        self._tracer = get_tracer(tracer)
        self._registry = _corpus_registry
        self._chunker = default_chunker()

    @classmethod
    async def open(
        cls,
        *,
        schema: GraphSchema,
        graph_store: GraphStore,
        embedder: Embedder,
        extractor: Extractor,
        tracer: Tracer | None = None,
    ) -> "Graph":
        """Open a graph, connecting and fully provisioning graph_store.

        Provisioning order: connect, then register every label/relation type
        this graph will ever write (schema's own labels/types plus the fixed
        system names CHUNK_LABEL/SYSTEM_RELATION_TYPES), then
        setup_constraints(), then setup_indexes(), then vector indexes for
        every schema entity label — so a brand-new database is fully ready,
        including the merge_key index the global exact-match tier needs and
        the embedding vector indexes native search needs, before this call
        returns.

        Args:
            schema: The entity/relation types this graph validates every
                extraction against.
            graph_store: Where entities, relations, chunks, and MENTIONED_IN
                edges are written.
            embedder: Populates entity embeddings for native vector search.
            extractor: Runs against each chunk.
            tracer: A tracer to record spans for every step. Pass None for none.

        Returns:
            A graph connected to graph_store and ready to accept add() calls.

        Raises:
            Exception: Whatever registration, constraint/index setup, or
                vector-index provisioning raises. graph_store is closed
                first, so a failed open() never leaks a connection.
        """
        await graph_store.connect()
        try:
            entity_labels = [entity_type.label for entity_type in schema.entities]
            relation_types = [relation_type.label for relation_type in schema.relations]
            await graph_store.register_labels([*entity_labels, CHUNK_LABEL])
            await graph_store.register_relation_types(
                [*relation_types, *SYSTEM_RELATION_TYPES]
            )
            await graph_store.setup_constraints()
            await graph_store.setup_indexes()
            dimensions = await embedder.dimensions()
            distance = embedder.distance
            for label in entity_labels:
                await graph_store.ensure_vector_index(
                    label=label,
                    vector_property="embedding",
                    dimensions=dimensions,
                    distance=distance,
                )
        except Exception:
            await graph_store.close()
            raise
        return cls(
            schema=schema,
            graph_store=graph_store,
            embedder=embedder,
            extractor=extractor,
            tracer=tracer,
        )

    async def add(  # noqa: PLR0912,PLR0915,PLR0913
        self,
        source: SourcesType | None = None,
        *,
        text: str | None = None,
        documents: Sequence[Document] | None = None,
        loader: Loader | None = None,
        error_policy: ErrorPolicy = ErrorPolicy.RAISE,
        on_progress: Callable[[AddResult], None] | None = None,
        return_chunks: bool = False,
    ) -> AddResult:
        """Add content to the graph.

        Give exactly one of ``source``, ``text``, and ``documents``.

        Args:
            source: A file path, a directory, a glob, or a list of these.
            text: Raw text to add as one document.
            documents: Already-built documents to add directly.
            loader: A loader to use instead of the registry default. Requires a
                single-file ``source``; a directory, glob, or list of sources raises an
                error.
            error_policy: The action to take on a per-source error.
            on_progress: A callback the call runs after each batch and once more
                at the end with the fully-populated result.
            return_chunks: Whether to include the produced chunks in the
                returned AddResult. False by default to avoid holding full text
                for a large corpus when not needed.

        Returns:
            A summary of what was added per pipeline stage.

        Raises:
            ValueError: The call got zero, or more than one, of ``source``, ``text``,
                and ``documents``. Also raised when ``loader`` is set without
                ``source``, or with a source that can match more than one file.
            UnsupportedFormatError: No loader is registered for a source's format.
            MissingExtraError: A loader is registered for a source's format, but its
                package extra is not installed. This error follows ``error_policy``
                instead of always stopping the call.
        """
        given = sum(x is not None for x in (source, text, documents))
        if given != 1:
            raise ValueError(
                f"Provide exactly one of 'source', 'text', or 'documents'; got {given}."
            )
        if loader is not None and source is None:
            raise ValueError(
                "A loader override requires 'source'; it has no effect on 'text' or "
                "'documents'."
            )

        chunks: list[Chunk] = []
        entities: list[ExtractedEntity] = []
        relations: list[ExtractedRelation] = []
        extraction_failures: list[StageFailure] = []

        # For ingestion stats accumulation
        final_stats = LoadStats()

        # For on_progress partial result helper
        def _build_partial_add_result() -> AddResult:
            ingest = IngestStats(
                documents=final_stats.documents,
                sources=final_stats.sources,
                skipped=final_stats.skipped,
                quarantined=final_stats.quarantined,
                quarantined_items=[
                    StageFailure(
                        item_id=str(uri),
                        error_type="Quarantined",
                        error_message=reason,
                    )
                    for uri, reason in final_stats.quarantined_items
                ],
            )
            extraction = ExtractionStats(
                chunks_processed=len(chunks),
                entities_extracted=len(entities),
                relations_extracted=len(relations),
                failures=_capped(list(extraction_failures)),
            )
            return AddResult(
                ingestion=ingest,
                extraction=extraction,
                resolution=ResolutionStats(),
                merge=MergeStats(),
                storage=StorageStats(),
                chunks=list(chunks) if return_chunks else [],
            )

        # Helper to extract one chunk with error_policy
        async def _extract_chunk(chunk: Chunk) -> None:
            # Use global entities/relations with index remapping
            offset = len(entities)
            try:
                result = await self._extractor.extract(chunk, self._schema)
            except Exception as exc:  # noqa: BLE001
                if error_policy is ErrorPolicy.RAISE:
                    raise
                extraction_failures.append(
                    StageFailure(
                        item_id=str(chunk.id),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
                return
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
                    extraction_failures.append(
                        StageFailure(
                            item_id=str(chunk.id),
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                    )
                    continue
                relations.append(new_rel)

        # Phase 1: Stream ingestion + extraction per walk-batch, collecting all mentions
        if documents is not None:
            # Single synthetic batch from provided documents
            docs_list = list(documents)
            final_stats.documents = len(docs_list)
            final_stats.sources = 0
            # Chunk all at once (still via thread)
            chunk_batch = await asyncio.to_thread(self._chunk_documents, docs_list)
            chunks.extend(chunk_batch)
            for chunk in chunk_batch:
                await _extract_chunk(chunk)
            # Fire on_progress once for the synthetic batch (partial)
            if on_progress is not None:
                with contextlib.suppress(Exception):
                    on_progress(_build_partial_add_result())
        elif text is not None:
            walk = _InMemoryWalk(text, opts=ReadOptions())
            batches = walk.iter_batches()
            async for batch, _cursor, stats in batches:
                # Stats is LoadStats
                final_stats.documents = stats.documents
                final_stats.sources = stats.sources
                final_stats.skipped = stats.skipped
                final_stats.quarantined = stats.quarantined
                final_stats.quarantined_items = list(stats.quarantined_items)
                # Chunk this batch
                chunk_batch = await asyncio.to_thread(self._chunk_documents, batch)
                chunks.extend(chunk_batch)
                for chunk in chunk_batch:
                    await _extract_chunk(chunk)
                if on_progress is not None:
                    with contextlib.suppress(Exception):
                        on_progress(_build_partial_add_result())
        else:
            assert source is not None
            paths, single_file = _resolve_paths(source)
            if loader is not None and not single_file:
                raise ValueError(
                    "A loader override requires a single-file source, not a directory, "
                    "glob, or list of sources."
                )
            walk = _CorpusWalk(
                paths,
                registry=self._registry,
                opts=ReadOptions(),
                error_policy=error_policy,
                loader=loader,
                tracer=self._tracer,
            )
            batches = walk.iter_batches()
            async for batch, _cursor, stats in batches:
                final_stats.documents = stats.documents
                final_stats.sources = stats.sources
                final_stats.skipped = stats.skipped
                final_stats.quarantined = stats.quarantined
                final_stats.quarantined_items = list(stats.quarantined_items)
                chunk_batch = await asyncio.to_thread(self._chunk_documents, batch)
                chunks.extend(chunk_batch)
                for chunk in chunk_batch:
                    await _extract_chunk(chunk)
                if on_progress is not None:
                    with contextlib.suppress(Exception):
                        on_progress(_build_partial_add_result())

        # If no chunks/entities, we can early return with empty stages
        if not chunks:
            # Build final result with zero stages
            ingestion = IngestStats(
                documents=final_stats.documents,
                sources=final_stats.sources,
                skipped=final_stats.skipped,
                quarantined=final_stats.quarantined,
                quarantined_items=[
                    StageFailure(
                        item_id=str(uri),
                        error_type="Quarantined",
                        error_message=reason,
                    )
                    for uri, reason in final_stats.quarantined_items
                ],
            )
            extraction = ExtractionStats(
                chunks_processed=0,
                entities_extracted=0,
                relations_extracted=0,
                failures=_capped(list(extraction_failures)),
            )
            result = AddResult(
                ingestion=ingestion,
                extraction=extraction,
                resolution=ResolutionStats(),
                merge=MergeStats(),
                storage=StorageStats(),
                chunks=list(chunks) if return_chunks else [],
            )
            if on_progress is not None:
                with contextlib.suppress(Exception):
                    on_progress(result)
            return result

        # Phase 2: Global exact-match + in-batch resolution (buffered over whole call)
        exact_matches = await _global_exact_match(
            entities, graph_store=self._graph_store
        )

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
        groups = await resolver.resolve(entities) if entities else []

        # Compute resolution stats
        exact_match_hits = len(exact_matches)
        # Groups include singletons; in_batch_groups is resolver group count.
        # ambiguous_count: no direct metric yet, use 0.
        resolution = ResolutionStats(
            exact_match_hits=exact_match_hits,
            in_batch_groups=len(groups) if groups else 0,
            ambiguous_count=0,
        )

        # Phase 3: Merge and write
        merge_stats = MergeStats()
        storage_stats = StorageStats()
        merge_failures: list[StageFailure] = []

        # Track survivors and mention->entity map
        mention_to_entity: dict[int, UUID] = {}
        survivors: dict[UUID, Entity] = {}
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
                    schema=self._schema,
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
                await apply_merge(
                    plan, graph_store=self._graph_store, schema=self._schema
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

        # If there were no entities (empty corpus) we have no survivors
        # but we still need to write chunks

        merge_stats = MergeStats(
            nodes_created=nodes_created,
            nodes_updated=nodes_updated,
            nodes_merged=nodes_merged,
            conflicts_resolved=conflicts_resolved,
            failures=_capped(merge_failures),
        )

        # Domain relation dedup + MENTIONED_IN
        # Build domain relation triples after mention->entity mapping
        # triples: list of (src_id, tgt_id, label)
        triple_to_chunk_ids: dict[tuple[UUID, UUID, str], list[UUID]] = {}
        # Keep track of which relations contributed which chunk ids
        for rel in relations:
            src_id = mention_to_entity.get(rel.source_index)
            tgt_id = mention_to_entity.get(rel.target_index)
            if src_id is None or tgt_id is None:
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
            triples_list, graph_store=self._graph_store
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

        mentioned_in_records: list[RelationRecord] = []
        for chunk_id, entity_id in mentioned_pairs:
            # Deterministic id
            edge_id = mentioned_in_id(chunk_id, entity_id)
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
        for ch in chunks:
            try:
                chunk_records.append(ch.to_node_record())
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

        # Write chunk nodes
        storage_failures: list[StageFailure] = list(relation_storage_failures)
        nodes_written = 0
        relationships_written_count = 0
        try:
            if chunk_records:
                # Grouping handled inside upsert_nodes
                await self._graph_store.upsert_nodes(CHUNK_LABEL, chunk_records)
                nodes_written += len(chunk_records)
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

        # Survivors already written via apply_merge; count them.
        nodes_written += len(survivors)

        # Write domain relations
        try:
            if relation_records:
                await self._graph_store.upsert_relations(relation_records)
                relationships_written_count += len(relation_records)
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
                await self._graph_store.upsert_relations(mentioned_in_records)
                relationships_written_count += len(mentioned_in_records)
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

        # Embedding stage: embed survivors and update them
        if survivors:
            try:
                texts = [ent.embedding_text for ent in survivors.values()]
                vectors = await self._embedder.embed(texts)
                # Assign and update
                updated_records = []
                for ent, vec in zip(survivors.values(), vectors, strict=False):
                    ent.embedding = vec
                    updated_records.append(ent.to_node_record())
                # Upsert with embeddings, grouped by label.
                by_label: dict[str, list] = defaultdict(list)
                for rec in updated_records:
                    ent = survivors[rec.id]
                    by_label[ent.label].append(rec)
                for label, recs in by_label.items():
                    await self._graph_store.upsert_nodes(label, recs)
                # Embedding upsert is an update, not new nodes.
            except Exception as exc:  # noqa: BLE001
                # A survivor's node was already committed with its (possibly
                # new) name and properties before this batch embed() call;
                # if the call fails, any embedding still on the node is from
                # before that update and would rank the entity by stale
                # text. Clear it rather than leave it searchable as current.
                # Best-effort: a failure here must not mask error_policy.
                with contextlib.suppress(Exception):
                    await self._graph_store.execute_write(
                        clear_property_query("embedding"),
                        {"ids": [str(entity_id) for entity_id in survivors]},
                    )
                if error_policy is ErrorPolicy.RAISE:
                    raise
                storage_failures.append(
                    StageFailure(
                        item_id="embeddings",
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )

        storage_stats = StorageStats(
            nodes_written=nodes_written,
            relationships_written=relationships_written_count,
            failures=_capped(storage_failures),
        )

        # Assemble final AddResult
        ingestion = IngestStats(
            documents=final_stats.documents,
            sources=final_stats.sources,
            skipped=final_stats.skipped,
            quarantined=final_stats.quarantined,
            quarantined_items=[
                StageFailure(
                    item_id=str(uri),
                    error_type="Quarantined",
                    error_message=reason,
                )
                for uri, reason in final_stats.quarantined_items
            ],
        )
        extraction = ExtractionStats(
            chunks_processed=len(chunks),
            entities_extracted=len(entities),
            relations_extracted=len(relations),
            failures=_capped(list(extraction_failures)),
        )

        result = AddResult(
            ingestion=ingestion,
            extraction=extraction,
            resolution=resolution,
            merge=merge_stats,
            storage=storage_stats,
            chunks=list(chunks) if return_chunks else [],
        )

        if on_progress is not None:
            with contextlib.suppress(Exception):
                on_progress(result)

        return result

    def _chunk_documents(self, documents: list[Document]) -> list[Chunk]:
        """Chunk a batch of documents with the right chunker each.

        Args:
            documents: The documents to chunk.

        Returns:
            The chunks, in document then chunk order.
        """
        chunks: list[Chunk] = []
        for document in documents:
            if document.loader_name == "docling":
                docling_doc = document.metadata.get("_docling_document")
                if docling_doc is not None:
                    chunks.extend(
                        traced(self._tracer)(chunk_docling_document)(
                            docling_doc, document.resolved_id
                        )
                    )
                    continue
            chunks.extend(traced(self._tracer)(chunk_document)(document, self._chunker))
        return chunks

    async def _all_entities_by_label(self, label: str) -> list[Entity]:
        """Return every persisted entity with label, for consolidate().

        Plain pagination through GraphStore.

        Args:
            label: The entity label to fetch.

        Returns:
            All entities with that label.
        """
        entities: list[Entity] = []
        skip = 0
        limit = 256
        while True:
            query = fetch_all_by_label_query(label)
            rows = await self._graph_store.execute_read(
                query, {"skip": skip, "limit": limit}
            )
            if not rows:
                break
            for row in rows:
                node = row.get("n") if isinstance(row, dict) and "n" in row else row
                ent = _parse_entity_node(node)
                if ent is not None:
                    # Skip tombstoned nodes with merged_into.
                    # Check node for merged_into property.
                    try:
                        raw_props = (
                            dict(node)  # ty: ignore[no-matching-overload]
                            if not isinstance(node, dict)
                            else node.get("properties", node)
                        )  # type: ignore[union-attr]
                        if isinstance(raw_props, dict) and raw_props.get("merged_into"):
                            continue
                        # Also check node dict directly
                        if isinstance(node, dict) and node.get("merged_into"):
                            continue
                        # Check row for merged_into
                        if isinstance(row, dict) and row.get("merged_into"):
                            continue
                    except Exception:
                        pass
                    entities.append(ent)
                else:
                    # Try parsing row directly if node was wrapped differently
                    ent2 = _parse_entity_node(row)
                    if ent2 is not None:
                        entities.append(ent2)
            if len(rows) < limit:
                break
            skip += limit
        return entities

    async def consolidate(self, *, apply: bool = False) -> ConsolidationReport:
        """Run full tiered resolution against everything persisted.

        Dry-run by default: produces a report of what would merge before any
        node is touched. Pass apply=True to write the merges.

        For each EntityType label in self._schema, fetches every persisted
        entity with that label and runs the same comparator sequence add() uses
        in-batch (ExactMatch, FuzzyMatch, LLMVerify) pairwise across all of
        them — O(n^2) within each label's population.
        Confirmed matches become MergePlans via compute_merge.

        Args:
            apply: Write the computed merges. False produces a report only.

        Returns:
            A report of every group consolidate() found, applied or not.
        """
        would_merge: list = []
        # For each label, fetch all entities, then pairwise compare via Resolver
        for entity_type in self._schema.entities:
            label = entity_type.label
            all_entities = await self._all_entities_by_label(label)
            if len(all_entities) < 2:
                continue
            # Synthesize mentions from persisted entities for resolver.
            synthetic_mentions: list[ExtractedEntity] = []
            # Dummy chunks for LLMVerify context.
            dummy_chunks_by_id: dict[UUID, Chunk] = {}
            for ent in all_entities:
                # Use first source chunk id if available, else new uuid
                dummy_cid = ent.source_chunk_ids[0] if ent.source_chunk_ids else uuid4()
                # Create dummy chunk if not exists
                if dummy_cid not in dummy_chunks_by_id:
                    dummy_chunks_by_id[dummy_cid] = Chunk(
                        document_id=dummy_cid,  # reuse
                        index=0,
                        text=ent.name,
                        provenance=TextProvenance(char_start=0, char_end=len(ent.name)),
                    )
                synthetic_mentions.append(
                    ExtractedEntity(
                        chunk_id=dummy_cid,
                        label=ent.label,
                        text=ent.name,
                        char_start=0,
                        char_end=len(ent.name),
                    )
                )

            resolver = Resolver(
                comparators=[
                    ExactMatch(),
                    FuzzyMatch(),
                    LLMVerify(chunks_by_id=dummy_chunks_by_id),
                ],
                candidate_source=InBatchCandidateSource(),
            )
            groups = await resolver.resolve(synthetic_mentions)
            # Filter groups of one (no merge)
            for group in groups:
                if len(group.entity_indices) <= 1:
                    continue
                # Collect existing_entities for this group
                group_entities = [all_entities[i] for i in group.entity_indices]
                # compute_merge with mentions=[] (per plan)
                try:
                    plan, _failures = await compute_merge(
                        existing_entities=group_entities,
                        mentions=[],
                        schema=self._schema,
                    )
                except Exception:
                    continue
                would_merge.append(plan)

        if apply and would_merge:
            for plan in would_merge:
                await apply_merge(
                    plan, graph_store=self._graph_store, schema=self._schema
                )

        return ConsolidationReport(
            would_merge=would_merge, applied=apply and bool(would_merge)
        )
