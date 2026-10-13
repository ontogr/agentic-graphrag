"""Convert approved candidates into entity nodes, relations and properties."""

from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.candidates.errors import PatchNotAppliedError
from agrag.candidates.patch import declares_property, endpoint_type
from agrag.common.data_models.candidate import CandidateRecord
from agrag.common.data_models.candidate_review import SchemaPatch
from agrag.common.data_models.graph_record import RelationRecord
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.stage_failure import StageFailure
from agrag.common.text import normalize_text
from agrag.cypher.candidate_conversion import (
    alias_owners_query,
    approved_evidence_query,
    convert_entity_candidates_query,
    delete_candidates_query,
    delete_evidence_edges_query,
    entity_labels_query,
    fold_entity_candidates_query,
    set_candidate_property_query,
    upsert_candidate_relations_query,
)
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.graphdb.entities import load_entities
from agrag.ingestion._ingest_pipeline import (
    _embed_and_upsert_survivors,
    _upsert_vectors,
    _vector_record,
)
from agrag.ingestion.merge import mentioned_in_id, relation_id
from agrag.ingestion.reports import ConversionReport
from agrag.loaders.types import ErrorPolicy
from agrag.observability import record_stage_failure
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore


_TRUE = {"true", "yes", "1"}
_FALSE = {"false", "no", "0"}
_Item = tuple[CandidateRecord, list[str]]


def check_patch_applied(schema: GraphSchema, patch: SchemaPatch) -> None:
    """Raise when the active schema does not include the patch additions."""
    entities = {entity.label for entity in schema.entities}
    relations = {relation.label for relation in schema.relations}
    missing: list[str] = []
    for entity in patch.additions.get("entities", []):
        if entity["label"] not in entities:
            missing.append(f"entity type {entity['label']}")
    for relation in patch.additions.get("relations", []):
        label = relation["label"]
        if label not in relations:
            missing.append(f"relation {label}")
        for source, target in [
            *relation.get("patterns", []),
            *relation.get("add_patterns", []),
        ]:
            if not schema.allows(label, source, target):
                missing.append(f"pattern {label} {source}->{target}")
    for prop in patch.add_properties:
        if not declares_property(schema, prop.entity, prop.name):
            missing.append(f"property {prop.entity}.{prop.name}")
    if missing:
        raise PatchNotAppliedError(missing)


def coerce_property(value: str, type_name: str) -> object:
    """Parse candidate text using its declared property type."""
    if type_name == "integer":
        return int(value.strip())
    if type_name == "float":
        return float(value.strip())
    if type_name == "date":
        parsed = date.fromisoformat(value.strip())
        if parsed.isoformat() != value.strip():
            raise ValueError(f"{value!r} is not an ISO date")
        return parsed.isoformat()
    if type_name == "boolean":
        folded = value.strip().casefold()
        if folded in _TRUE:
            return True
        if folded in _FALSE:
            return False
        raise ValueError(f"{value!r} is not a boolean")
    return value


async def convert_candidates(
    patch: SchemaPatch,
    *,
    graph_store: GraphStore,
    schema: GraphSchema,
    embedder: Embedder,
    vector_store: VectorStore | None,
    retrieval_settings: RetrievalSettings,
    error_policy: ErrorPolicy,
    tracer: Tracer,
) -> ConversionReport:
    """Convert approved patch rows atomically, then mirror committed vectors."""
    check_patch_applied(schema, patch)
    report = ConversionReport()
    now = datetime.now(UTC).isoformat()
    with tracer.start_as_current_span(
        "agrag.candidates.convert",
        attributes={"agrag.candidate_count": len(patch.candidate_ids)},
    ):
        rows = await graph_store.execute_read(
            approved_evidence_query(), {"ids": [str(i) for i in patch.candidate_ids]}
        )
        approved: dict[UUID, _Item] = {}
        for row in rows:
            record = CandidateRecord.model_validate(row["candidate"])
            approved[record.id] = (record, [str(value) for value in row["chunk_ids"]])
        for candidate_id in patch.candidate_ids:
            if candidate_id not in approved:
                report.skipped[str(candidate_id)] = "not approved"

        entities = [item for item in approved.values() if item[0].kind == "entity"]
        converts, folds = await _plan_entities(
            graph_store, schema, embedder, entities, report, now=now
        )
        relations, relation_candidates = await _plan_relations(
            graph_store,
            schema,
            [item for item in approved.values() if item[0].kind == "relation"],
            report,
            now,
        )
        properties, property_candidates = await _plan_properties(
            graph_store,
            schema,
            [item for item in approved.values() if item[0].kind == "property"],
            report,
        )

        async def write(
            transaction: GraphStoreTransaction,
        ) -> tuple[set[str], set[str], int, int, int]:
            """Apply writes and return the candidate ids actually handled."""
            return await _write(
                transaction,
                converts=converts,
                folds=folds,
                relations=relations,
                properties=properties,
                now=now,
            )

        (
            handled,
            converted_ids,
            folded_count,
            relation_count,
            property_count,
        ) = await graph_store.run_in_transaction(write)
        report.converted_entities += len(converted_ids)
        report.folded += folded_count
        report.created_relations += relation_count
        report.set_properties += property_count
        for candidate_id in (*relation_candidates, *property_candidates):
            if candidate_id not in handled:
                report.skipped.setdefault(candidate_id, "endpoint_missing")
        for record, _ in entities:
            candidate_id = str(record.id)
            if candidate_id not in handled and candidate_id not in report.skipped:
                report.skipped[candidate_id] = "not approved"

        converted_rows = [
            item
            for rows_by_label in converts.values()
            for item in rows_by_label
            if item["id"] in converted_ids
        ]
        written_properties = {
            name: [row for row in values if row["candidate_id"] in handled]
            for name, values in properties.items()
        }
        await _mirror_and_reembed(
            converted_rows,
            written_properties,
            graph_store=graph_store,
            embedder=embedder,
            vector_store=vector_store,
            retrieval_settings=retrieval_settings,
            error_policy=error_policy,
            report=report,
        )
    return report


async def _plan_entities(
    graph_store: GraphStore,
    schema: GraphSchema,
    embedder: Embedder,
    items: list[_Item],
    report: ConversionReport,
    *,
    now: str,
) -> tuple[dict[tuple[str, ...], list[dict[str, Any]]], list[dict[str, Any]]]:
    """Prepare entity rows for conversion or exact-name folding."""
    labels = {entity.label for entity in schema.entities}
    usable: list[tuple[CandidateRecord, list[str], str]] = []
    for record, chunks in items:
        if record.label not in labels or not record.text:
            report.skipped[str(record.id)] = "label_not_in_schema"
            continue
        usable.append((record, chunks, f"{record.label}:{normalize_text(record.text)}"))
    owners: dict[str, str] = {}
    if usable:
        rows = await graph_store.execute_read(
            alias_owners_query(), {"merge_keys": sorted({key for _, _, key in usable})}
        )
        owners = {str(row["merge_key"]): str(row["entity_id"]) for row in rows}
    grouped: dict[str, list[tuple[CandidateRecord, list[str]]]] = defaultdict(list)
    for record, chunks, key in usable:
        grouped[key].append((record, chunks))
    folds: list[dict[str, Any]] = []
    fresh: list[tuple[CandidateRecord, list[str], str]] = []
    for key, group in sorted(grouped.items()):
        group.sort(key=lambda item: str(item[0].id))
        if key in owners:
            owner_id = owners[key]
            fold_group = group
        else:
            first_record, first_chunks = group[0]
            fresh.append(
                (
                    first_record,
                    first_chunks,
                    key,
                )
            )
            owner_id = str(first_record.id)
            fold_group = group[1:]
        folds.extend(
            {
                "id": str(record.id),
                "owner_id": owner_id,
                "count": record.count,
                "chunk_ids": chunks,
            }
            for record, chunks in fold_group
        )
    vectors = (
        await embedder.embed([record.text for record, _, _ in fresh]) if fresh else []
    )
    converts: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for (record, chunks, key), vector in zip(fresh, vectors, strict=True):
        converts[tuple(schema.node_labels(record.label))].append(
            {
                "id": str(record.id),
                "label": record.label,
                "text": record.text,
                "merge_key": key,
                "chunk_ids": chunks,
                "count": record.count,
                "embedding": vector,
                "now": now,
            }
        )
    return converts, folds


async def _plan_relations(
    graph_store: GraphStore,
    schema: GraphSchema,
    items: list[_Item],
    report: ConversionReport,
    now: str,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """Prepare relation writes after checking endpoints and schema patterns."""
    endpoint_ids = sorted(
        {
            str(end)
            for record, _ in items
            for end in (record.source_entity_id, record.target_entity_id)
            if end is not None
        }
    )
    labels = await _entity_labels(graph_store, endpoint_ids)
    planned: dict[str, list[dict[str, Any]]] = defaultdict(list)
    handled_candidates: list[str] = []
    for record, chunks in items:
        source, target = record.source_entity_id, record.target_entity_id
        if source is None or target is None:
            report.skipped[str(record.id)] = "endpoint_missing"
            continue
        source_type = (
            endpoint_type(labels.get(str(source), ()), schema) if source else None
        )
        target_type = (
            endpoint_type(labels.get(str(target), ()), schema) if target else None
        )
        if source_type is None or target_type is None:
            report.skipped[str(record.id)] = "endpoint_missing"
        elif not schema.allows(record.label, source_type, target_type):
            report.skipped[str(record.id)] = "pattern_not_applied"
        else:
            planned[record.label].append(
                {
                    "candidate_id": str(record.id),
                    "id": str(relation_id(source, target, record.label)),
                    "start_id": str(source),
                    "end_id": str(target),
                    "chunk_ids": chunks,
                    "now": now,
                }
            )
            handled_candidates.append(str(record.id))
    return planned, handled_candidates


async def _plan_properties(
    graph_store: GraphStore,
    schema: GraphSchema,
    items: list[_Item],
    report: ConversionReport,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """Prepare declared property writes and coerce their values."""
    owner_ids = sorted(
        {
            str(record.source_entity_id)
            for record, _ in items
            if record.source_entity_id is not None
        }
    )
    labels = await _entity_labels(graph_store, owner_ids)
    types = {entity.label: entity for entity in schema.entities}
    planned: dict[str, list[dict[str, Any]]] = defaultdict(list)
    handled_candidates: list[str] = []
    for record, chunks in items:
        candidate_id = str(record.id)
        owner = record.source_entity_id
        owner_type = (
            endpoint_type(labels.get(str(owner), ()), schema) if owner else None
        )
        if owner_type is None:
            report.skipped[candidate_id] = "endpoint_missing"
            continue
        spec = next(
            (
                types[label].properties[record.label]
                for label in (owner_type, *schema.ancestors(owner_type))
                if label in types and record.label in types[label].properties
            ),
            None,
        )
        if spec is None:
            report.skipped[candidate_id] = "property_not_declared"
            continue
        if spec.enum and record.text not in spec.enum:
            report.skipped[candidate_id] = "not_in_enum"
            continue
        try:
            value = coerce_property(record.text, spec.type)
        except ValueError:
            report.skipped[candidate_id] = "bad_value"
            continue
        planned[record.label].append(
            {
                "candidate_id": candidate_id,
                "entity_id": str(owner),
                "value": value,
                "chunk_ids": chunks,
            }
        )
        handled_candidates.append(candidate_id)
    return planned, handled_candidates


async def _entity_labels(
    graph_store: GraphStore, ids: list[str]
) -> dict[str, list[str]]:
    """Return stored labels keyed by entity id."""
    if not ids:
        return {}
    rows = await graph_store.execute_read(entity_labels_query(), {"ids": ids})
    return {str(row["id"]): list(row["labels"]) for row in rows}


async def _write(
    transaction: GraphStoreTransaction,
    *,
    converts: dict[tuple[str, ...], list[dict[str, Any]]],
    folds: list[dict[str, Any]],
    relations: dict[str, list[dict[str, Any]]],
    properties: dict[str, list[dict[str, Any]]],
    now: str,
) -> tuple[set[str], set[str], int, int, int]:
    """Write all prepared changes in the enclosing transaction."""
    handled: set[str] = set()
    folded_count = relation_count = property_count = 0
    mentions: list[RelationRecord] = []
    converted_ids: list[str] = []
    relation_ids: set[str] = set()
    for labels, rows in converts.items():
        returned = await transaction.execute_write(
            convert_entity_candidates_query(labels), {"rows": rows}
        )
        won = {str(row["id"]) for row in returned}
        handled.update(won)
        converted = {str(row["id"]) for row in returned if row["converted"]}
        converted_ids.extend(converted)
        folded_count += len(won - converted)
        mentions.extend(
            _mention(chunk, row["id"], now)
            for row in rows
            if row["id"] in converted
            for chunk in row["chunk_ids"]
        )
        mentions.extend(
            _mention(chunk, row["owner_id"], now)
            for row in returned
            if not row["converted"]
            for source in rows
            if source["id"] == row["id"]
            for chunk in source["chunk_ids"]
        )
    if converted_ids:
        await transaction.execute_write(
            delete_evidence_edges_query(), {"ids": converted_ids}
        )
    if folds:
        returned = await transaction.execute_write(
            fold_entity_candidates_query(), {"rows": folds}
        )
        won = {str(row["id"]) for row in returned}
        handled.update(won)
        folded_count += len(won)
        mentions.extend(
            _mention(chunk, fold["owner_id"], now)
            for fold in folds
            if fold["id"] in won
            for chunk in fold["chunk_ids"]
        )
    if mentions:
        by_id = {mention.id: mention for mention in mentions}
        await transaction.upsert_relations(list(by_id.values()))
    for rel_type, rows in relations.items():
        returned = await transaction.execute_write(
            upsert_candidate_relations_query(rel_type), {"records": rows}
        )
        won = {str(row["candidate_id"]) for row in returned}
        handled.update(won)
        relation_ids.update(str(row["id"]) for row in returned)
        relation_count = len(relation_ids)
    for name, rows in properties.items():
        returned = await transaction.execute_write(
            set_candidate_property_query(name), {"rows": rows}
        )
        won = {str(row["candidate_id"]) for row in returned}
        handled.update(won)
        property_count += len(won)
    if handled:
        await transaction.execute_write(
            delete_candidates_query(), {"ids": sorted(handled)}
        )
    return handled, set(converted_ids), folded_count, relation_count, property_count


def _mention(chunk_id: str, entity_id: str, now: str) -> RelationRecord:
    """Build the deterministic MENTIONED_IN relation record."""
    chunk, entity = UUID(chunk_id), UUID(entity_id)
    return RelationRecord(
        id=mentioned_in_id(chunk, entity),
        type="MENTIONED_IN",
        start_id=chunk,
        end_id=entity,
        properties={"created_at": now},
    )


async def _mirror_and_reembed(
    converted: list[dict[str, Any]],
    property_rows: Mapping[str, list[dict[str, Any]]],
    *,
    graph_store: GraphStore,
    embedder: Embedder,
    vector_store: VectorStore | None,
    retrieval_settings: RetrievalSettings,
    error_policy: ErrorPolicy,
    report: ConversionReport,
) -> None:
    """Mirror committed entity vectors and refresh changed descriptions."""
    if vector_store is not None and converted:
        records = [
            _vector_record(
                UUID(row["id"]),
                row["embedding"],
                label=row["label"],
                text=row["text"],
                properties={},
            )
            for row in converted
        ]
        try:
            await _upsert_vectors(
                vector_store, retrieval_settings.entity_collection, records
            )
        except Exception as exc:  # noqa: BLE001
            if error_policy is ErrorPolicy.RAISE:
                raise
            report.failures.append(_failure("entity_vector_store", exc))
    descriptions = property_rows.get("description", [])
    if descriptions:
        try:
            entities = await load_entities(
                graph_store, [UUID(row["entity_id"]) for row in descriptions]
            )
            report.failures.extend(
                await _embed_and_upsert_survivors(
                    entities,
                    embedder=embedder,
                    graph_store=graph_store,
                    error_policy=error_policy,
                    vector_store=vector_store,
                    vector_collection=retrieval_settings.entity_collection,
                    labels_by_id={
                        entity.id: entity.label for entity in entities.values()
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            if error_policy is ErrorPolicy.RAISE:
                raise
            report.failures.append(_failure("description_embedding", exc))


def _failure(item_id: str, error: Exception) -> StageFailure:
    """Build a report item with the active trace and span ids."""
    trace_id, span_id = record_stage_failure(error)
    return StageFailure(
        item_id=item_id,
        error_type=type(error).__name__,
        error_message=str(error),
        trace_id=trace_id,
        span_id=span_id,
    )
