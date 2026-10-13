"""Plan and serialize deterministic candidate schema patches."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from agrag.common.data_models.candidate import CandidateRecord
from agrag.common.data_models.candidate_review import (
    PatchBase,
    PatchProperty,
    SchemaPatch,
)
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.schema_fingerprint import schema_fingerprint
from agrag.cypher.candidate_review import (
    entity_labels_query,
    load_candidates_query,
    select_candidate_ids_query,
)
from agrag.graphdb.base import GraphStore


@dataclass
class _Pairs:
    pairs: set[tuple[str, str]] = field(default_factory=set)


def endpoint_type(labels: Sequence[str], schema: GraphSchema) -> str | None:
    """Select the most specific declared type among an entity's labels.

    If multiple leaf types remain, the alphabetically first label is returned.

    Args:
        labels: Labels attached to an entity.
        schema: Schema that declares entity types and their ancestry.

    Returns:
        Selected schema type, or ``None`` when no label is declared.
    """
    declared = {entity.label for entity in schema.entities}
    present = [label for label in labels if label in declared]
    leaves = [
        label
        for label in present
        if not any(
            label in schema.ancestors(other) for other in present if other != label
        )
    ]
    return min(leaves) if leaves else None


def declares_property(schema: GraphSchema, entity_label: str, name: str) -> bool:
    """Check whether an entity type or an ancestor declares a property.

    Args:
        schema: Schema containing entity definitions.
        entity_label: Entity type to check.
        name: Property name to find.

    Returns:
        Whether the type or any declared ancestor defines the property.
    """
    by_label = {entity.label: entity for entity in schema.entities}
    return any(
        name in by_label[label].properties
        for label in (entity_label, *schema.ancestors(entity_label))
        if label in by_label
    )


def plan_patch(
    records: Sequence[CandidateRecord],
    *,
    schema: GraphSchema,
    labels_by_entity: Mapping[str, Sequence[str]],
    base: PatchBase,
    created_at: datetime,
) -> SchemaPatch:
    """Plan sorted schema additions and evidence from candidate records.

    Records with unresolved endpoints are excluded. Entity, relation, and
    property changes already covered by the schema are omitted. A stable patch
    identifier is derived from the base fingerprint and included record ids.

    Args:
        records: Candidate records considered for inclusion.
        schema: Current schema used to identify existing definitions.
        labels_by_entity: Graph labels keyed by entity id.
        base: Name, version, and fingerprint of the base schema.
        created_at: Timestamp recorded in the resulting patch.

    Returns:
        Patch with sorted additions, evidence totals, and included candidate ids.
    """
    entity_labels = {entity.label for entity in schema.entities}
    relation_labels = {relation.label for relation in schema.relations}
    evidence: dict[str, int] = {}
    entities: set[str] = set()
    new_relations: dict[str, _Pairs] = {}
    widened: dict[str, _Pairs] = {}
    properties: dict[tuple[str, str], PatchProperty] = {}
    planned: list[str] = []

    def add_evidence(key: str, count: int) -> None:
        evidence[key] = evidence.get(key, 0) + count

    for record in sorted(
        records, key=lambda item: (item.kind, item.label, str(item.id))
    ):
        if record.kind == "entity":
            if record.label not in entity_labels:
                entities.add(record.label)
                add_evidence(f"entity:{record.label}", record.count)
            planned.append(str(record.id))
            continue
        source = (
            endpoint_type(
                labels_by_entity.get(str(record.source_entity_id), ()), schema
            )
            if record.source_entity_id
            else None
        )
        if source is None:
            continue
        if record.kind == "property":
            if not declares_property(schema, source, record.label):
                properties.setdefault(
                    (source, record.label),
                    PatchProperty(entity=source, name=record.label),
                )
                add_evidence(f"property:{source}.{record.label}", record.count)
            planned.append(str(record.id))
            continue
        target = (
            endpoint_type(
                labels_by_entity.get(str(record.target_entity_id), ()), schema
            )
            if record.target_entity_id
            else None
        )
        if target is None:
            continue
        planned.append(str(record.id))
        if record.label not in relation_labels:
            new_relations.setdefault(record.label, _Pairs()).pairs.add((source, target))
        elif not schema.allows(record.label, source, target):
            widened.setdefault(record.label, _Pairs()).pairs.add((source, target))
        else:
            continue
        add_evidence(f"relation:{record.label}", record.count)

    ids = sorted(planned)
    payload = json.dumps({"base": base.fingerprint, "ids": ids}, sort_keys=True)
    patch_id = hashlib.sha256(payload.encode()).hexdigest()[:16]
    relations: list[dict[str, Any]] = [
        {
            "label": label,
            "description": "",
            "patterns": sorted(map(list, pair_set.pairs)),
        }
        for label, pair_set in sorted(new_relations.items())
    ] + [
        {"label": label, "add_patterns": sorted(map(list, pair_set.pairs))}
        for label, pair_set in sorted(widened.items())
    ]
    return SchemaPatch(
        patch_id=patch_id,
        created_at=created_at,
        base_schema=base,
        additions={
            "entities": [
                {"label": label, "description": ""} for label in sorted(entities)
            ],
            "relations": relations,
        },
        add_properties=[properties[key] for key in sorted(properties)],
        evidence=dict(sorted(evidence.items())),
        candidate_ids=[UUID(value) for value in ids],
    )


def write_patch(patch: SchemaPatch, path: Path, *, overwrite: bool = False) -> Path:
    """Write the patch as indented JSON, refusing replacement by default.

    The file is created or truncated only after opening it in exclusive-create
    or write mode. A trailing newline is included.

    Args:
        patch: Patch to serialize.
        path: Destination file path.
        overwrite: Whether to truncate an existing file.

    Returns:
        The destination path after a successful write.

    Raises:
        FileExistsError: If the destination exists and overwrite is false.
        OSError: If the destination cannot be opened or written.
    """
    with path.open("w" if overwrite else "x", encoding="utf-8") as handle:
        handle.write(patch.model_dump_json(indent=2) + "\n")
    return path


def read_patch(path: Path) -> SchemaPatch:
    """Read a JSON file and validate it as a schema patch.

    Args:
        path: Patch file to read.

    Returns:
        Validated schema patch.

    Raises:
        OSError: If the file cannot be read.
        ValueError: If its contents are invalid JSON or do not match the model.
    """
    return SchemaPatch.model_validate_json(path.read_text(encoding="utf-8"))


async def candidate_patch(
    graph_store: GraphStore,
    schema: GraphSchema,
    *,
    ids: Sequence[UUID] | None = None,
    now: datetime | None = None,
) -> SchemaPatch:
    """Build a patch from approved candidate records in the graph.

    When ``ids`` is omitted, all approved candidates are selected. Supplied
    ids are loaded, then non-approved records and records with unresolved
    endpoints are excluded from the planned patch.

    Args:
        graph_store: Store containing candidates and endpoint entities.
        schema: Current schema used to plan additions.
        ids: Candidate ids to consider, or all approved ids when omitted.
        now: Patch creation time, or the current UTC time when omitted.

    Returns:
        Deterministic patch based on the selected approved records.
    """
    if ids is None:
        selected = await graph_store.execute_read(
            select_candidate_ids_query(),
            {"kind": None, "label": None, "state": "approved", "min_count": 1},
        )
        ids = [UUID(str(row["id"])) for row in selected]
    loaded = await graph_store.execute_read(
        load_candidates_query(), {"ids": [str(value) for value in ids]}
    )
    records = [CandidateRecord.model_validate(row["candidate"]) for row in loaded]
    records = [record for record in records if record.state == "approved"]
    entity_ids = sorted(
        {
            str(value)
            for record in records
            for value in (record.source_entity_id, record.target_entity_id)
            if value is not None
        }
    )
    label_rows = (
        await graph_store.execute_read(entity_labels_query(), {"ids": entity_ids})
        if entity_ids
        else []
    )
    labels = {str(row["id"]): list(row["labels"]) for row in label_rows}
    return plan_patch(
        records,
        schema=schema,
        labels_by_entity=labels,
        base=PatchBase(
            name=schema.name,
            version=schema.version,
            fingerprint=schema_fingerprint(schema),
        ),
        created_at=now or datetime.now(UTC),
    )
