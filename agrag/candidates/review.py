"""List and change the review state of candidate groups."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from agrag.candidates.patch import (
    candidate_patch,
    declares_property,
    endpoint_type,
    write_patch,
)
from agrag.common.data_models.candidate import CandidateRecord
from agrag.common.data_models.candidate_review import (
    ApprovalResult,
    CandidateGroup,
    CandidateQuery,
    CandidateState,
    PruneReport,
    ReviewOutcome,
    states_that_reach,
)
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.text import normalize_text
from agrag.cypher.candidate_review import (
    alias_owners_query,
    approved_group_ids_query,
    delete_prunable_query,
    entity_labels_query,
    list_candidates_query,
    load_candidates_query,
    match_prunable_query,
    select_candidate_ids_query,
    select_candidate_keys_query,
    transition_candidates_query,
)
from agrag.graphdb.base import GraphStore


# The largest row count every graph backend accepts in a LIMIT clause.
_UNBOUNDED_LIMIT = 2**31 - 1


def _filter_params(query: CandidateQuery) -> dict[str, object]:
    return {
        "kind": query.kind,
        "label": query.label,
        "state": query.state,
        "min_count": query.min_count,
    }


async def _select_keys(
    graph_store: GraphStore,
    keys: Sequence[str] | None,
    query: CandidateQuery | None,
) -> list[str]:
    if (keys is None) == (query is None):
        raise ValueError("Pass exactly one of keys and query.")
    if keys is not None:
        return list(dict.fromkeys(keys))
    rows = await graph_store.execute_read(
        select_candidate_keys_query(), _filter_params(query or CandidateQuery())
    )
    return [str(row["key"]) for row in rows]


def _is_covered(group: CandidateGroup, schema: GraphSchema) -> bool:
    record = group.candidate
    if group.state != "pending":
        return False
    if record.kind == "entity":
        return any(entity.label == record.label for entity in schema.entities)
    if record.kind == "property":
        return bool(
            record.source_label
            and declares_property(schema, record.source_label, record.label)
        )
    if not (record.source_label and record.target_label):
        return False
    return schema.allows(record.label, record.source_label, record.target_label)


def _resolve_endpoint(
    entity_id: UUID | None,
    text: str | None,
    owner_map: dict[str, set[str]],
    labels: dict[str, list[str]],
    schema: GraphSchema,
    *,
    expected_type: str | None,
) -> tuple[str | None, str | None]:
    owners = (
        {str(entity_id)}
        if entity_id
        else {
            owner
            for key, found in owner_map.items()
            if text
            and key.endswith(":" + normalize_text(text))
            and (expected_type is None or key.startswith(expected_type + ":"))
            for owner in found
        }
    )
    if len(owners) != 1:
        return None, "endpoint_unresolved" if not owners else "endpoint_ambiguous"
    owner = next(iter(owners))
    if owner not in labels:
        return None, "endpoint_missing"
    if endpoint_type(labels[owner], schema) is None:
        return None, "endpoint_type_not_in_schema"
    return owner, None


async def list_candidates(
    graph_store: GraphStore,
    query: CandidateQuery | None = None,
    *,
    limit: int = 100,
    skip: int = 0,
    schema: GraphSchema | None = None,
    include_covered: bool = False,
) -> list[CandidateGroup]:
    """List candidate groups, ordered and paged by aggregate sightings.

    When a schema is supplied, covered pending candidates are hidden unless
    ``include_covered`` is true.

    Args:
        graph_store: Store used to read candidate groups.
        query: Optional filters for kind, label, state, and sighting count.
        limit: Maximum number of groups to return.
        skip: Number of groups to skip.
        schema: Schema used to identify already-covered candidates.
        include_covered: Whether to retain candidates covered by the schema.

    Returns:
        Matching candidate groups.

    Raises:
        ValueError: If ``limit`` or ``skip`` is negative.
    """
    if limit < 0 or skip < 0:
        raise ValueError("limit and skip must not be negative.")
    rows = await graph_store.execute_read(
        list_candidates_query(),
        {
            **_filter_params(query or CandidateQuery()),
            "limit": _UNBOUNDED_LIMIT
            if schema is not None and not include_covered
            else limit,
            "skip": 0 if schema is not None and not include_covered else skip,
        },
    )
    groups = [CandidateGroup.from_row(row) for row in rows]
    if schema is None or include_covered:
        return groups
    visible = [group for group in groups if not _is_covered(group, schema)]
    return visible[skip : skip + limit]


async def move_candidates(
    graph_store: GraphStore,
    rows: list[dict[str, str | None]],
    *,
    to_state: CandidateState,
    now: datetime | None = None,
) -> ReviewOutcome:
    """Move candidate groups whose current states allow ``to_state``.

    Groups that are missing or cannot make the transition remain unchanged
    and appear in ``skipped``. Successful writes update the candidate state
    and decision time.

    Args:
        graph_store: Store containing the candidate groups.
        rows: Group keys and optional endpoint ids used for approval.
        to_state: State to enter.
        now: Decision time, or the current UTC time when omitted.

    Returns:
        Keys changed and keys skipped with their reasons.
    """
    if not rows:
        return ReviewOutcome()
    moved = await graph_store.execute_write(
        transition_candidates_query(),
        {
            "rows": rows,
            "from_states": states_that_reach(to_state),
            "to_state": to_state,
            "decided_at": (now or datetime.now(UTC)).isoformat(),
        },
    )
    changed = [str(row["key"]) for row in moved]
    changed_set = set(changed)
    return ReviewOutcome(
        changed=changed,
        skipped={
            str(row["key"]): f"not found, or its state cannot move to {to_state}"
            for row in rows
            if str(row["key"]) not in changed_set
        },
    )


async def reject_candidates(
    graph_store: GraphStore,
    *,
    keys: Sequence[str] | None = None,
    query: CandidateQuery | None = None,
    now: datetime | None = None,
) -> ReviewOutcome:
    """Reject selected candidate groups and retain them as suppression records.

    Pass exactly one of ``keys`` or ``query``. Query selection deduplicates
    keys before attempting the pending-to-rejected transition.

    Args:
        graph_store: Store containing candidate groups.
        keys: Explicit group keys to reject.
        query: Filters used to select groups to reject.
        now: Decision time, or the current UTC time when omitted.

    Returns:
        Keys rejected and keys skipped with their reasons.

    Raises:
        ValueError: If both or neither of ``keys`` and ``query`` are supplied.
    """
    selected = await _select_keys(graph_store, keys, query)
    return await move_candidates(
        graph_store, [{"key": key} for key in selected], to_state="rejected", now=now
    )


async def prune_candidates(
    graph_store: GraphStore,
    *,
    rejected: bool = False,
    pending_older_than_days: int | None = None,
    pending_below_count: int | None = None,
    apply: bool = False,
    now: datetime | None = None,
) -> PruneReport:
    """Count or delete groups matching the selected prune criteria.

    Matching groups are only deleted when ``apply`` is true and at least
    one group matches. The report distinguishes a dry run from a deletion.

    Args:
        graph_store: Store containing candidate groups.
        rejected: Include rejected groups.
        pending_older_than_days: Include pending groups older than this many days.
        pending_below_count: Include pending groups below this sighting count.
        apply: Whether to delete matching groups.
        now: Reference time, or the current UTC time when omitted.

    Returns:
        Counts of matched and deleted groups and whether deletion ran.

    Raises:
        ValueError: If no criterion is set or a numeric threshold is below one.
    """
    if not (
        rejected
        or pending_older_than_days is not None
        or pending_below_count is not None
    ):
        raise ValueError("Give at least one prune criterion.")
    if pending_older_than_days is not None and pending_older_than_days < 1:
        raise ValueError("pending_older_than_days must be at least 1.")
    if pending_below_count is not None and pending_below_count < 1:
        raise ValueError("pending_below_count must be at least 1.")
    current = now or datetime.now(UTC)
    params: dict[str, object] = {
        "rejected": rejected,
        "older_than": (current - timedelta(days=pending_older_than_days))
        .astimezone(UTC)
        .isoformat()
        if pending_older_than_days is not None
        else None,
        "below_count": pending_below_count,
    }
    counted = await graph_store.execute_read(match_prunable_query(), params)
    matched = int(counted[0]["matched"]) if counted else 0
    if not apply or not matched:
        return PruneReport(matched=matched, deleted=0, applied=False)
    deleted_rows = await graph_store.execute_write(delete_prunable_query(), params)
    deleted = int(deleted_rows[0]["deleted"]) if deleted_rows else 0
    return PruneReport(matched=matched, deleted=deleted, applied=True)


async def approve_candidates(
    graph_store: GraphStore,
    schema: GraphSchema,
    *,
    ids: Sequence[UUID] | None = None,
    query: CandidateQuery | None = None,
    output: Path | None = None,
    overwrite: bool = False,
    now: datetime | None = None,
) -> ApprovalResult:
    """Approve resolvable candidates and plan a deterministic schema patch.

    Pass exactly one of ``ids`` or ``query``. Only pending candidates with
    resolvable endpoints are approved. If any candidate changes state, a patch
    is built from the approved groups; ``output`` also writes it as JSON.

    Args:
        graph_store: Store containing candidates and endpoint entities.
        schema: Schema used to resolve endpoints and plan additions.
        ids: Candidate ids to approve.
        query: Filters used to select candidate ids.
        output: Optional path for the patch JSON file.
        overwrite: Whether to replace an existing output file.
        now: Decision and patch creation time, or current UTC time.

    Returns:
        Approval results and a patch when at least one group changes state.
        The output path is set only when the file was written.

    Raises:
        ValueError: If both or neither of ``ids`` and ``query`` are supplied.
        FileExistsError: If ``output`` exists and ``overwrite`` is false.
    """
    if (ids is None) == (query is None):
        raise ValueError("Pass exactly one of ids and query.")
    if ids is None:
        selected = await graph_store.execute_read(
            select_candidate_ids_query(), _filter_params(query or CandidateQuery())
        )
        ids = [UUID(str(row["id"])) for row in selected]
    if not ids:
        return ApprovalResult(outcome=ReviewOutcome())
    if output is not None and output.exists() and not overwrite:
        raise FileExistsError(output)
    loaded = await graph_store.execute_read(
        load_candidates_query(), {"ids": [str(value) for value in ids]}
    )
    records = {
        record.id: (record, str(row["stored_key"]))
        for row in loaded
        for record in [CandidateRecord.model_validate(row["candidate"])]
    }
    skipped: dict[str, str] = {}
    pending: list[CandidateRecord] = []
    for candidate_id in ids:
        loaded_record = records.get(candidate_id)
        if loaded_record is None:
            skipped[str(candidate_id)] = "not found"
        elif loaded_record[0].state != "pending":
            skipped[str(candidate_id)] = f"state is {loaded_record[0].state}"
        else:
            pending.append(loaded_record[0])
    resolved = await _resolve_endpoints(
        graph_store,
        schema,
        pending,
        keys={record.id: records[record.id][1] for record in pending},
    )
    rows: list[dict[str, str | None]] = []
    for record in pending:
        result = resolved.get(record.id)
        if isinstance(result, str):
            skipped[str(record.id)] = result
        elif result is not None:
            rows.append(result)
    moved = await move_candidates(graph_store, rows, to_state="approved", now=now)
    skipped.update(moved.skipped)
    outcome = ReviewOutcome(changed=moved.changed, skipped=skipped)
    if not moved.changed:
        return ApprovalResult(outcome=outcome)
    approved_rows = await graph_store.execute_read(
        approved_group_ids_query(), {"keys": moved.changed}
    )
    approved_ids = [UUID(str(row["id"])) for row in approved_rows]
    patch = await candidate_patch(graph_store, schema, ids=approved_ids, now=now)
    path = write_patch(patch, output, overwrite=overwrite) if output else None
    return ApprovalResult(
        outcome=outcome, patch=patch, path=str(path) if path else None
    )


async def _resolve_endpoints(
    graph_store: GraphStore,
    schema: GraphSchema,
    records: Sequence[CandidateRecord],
    *,
    keys: dict[UUID, str],
) -> dict[UUID, dict[str, str | None] | str]:
    needs: set[str] = set()
    merge_keys: set[str] = set()
    for record in records:
        if record.kind == "entity":
            continue
        for entity_id, text in (
            (record.source_entity_id, record.source_text),
            (
                record.target_entity_id,
                record.target_text if record.kind == "relation" else None,
            ),
        ):
            if entity_id:
                needs.add(str(entity_id))
            elif text:
                merge_keys.update(
                    f"{entity.label}:{normalize_text(text)}"
                    for entity in schema.entities
                )
    owner_map: dict[str, set[str]] = {}
    if merge_keys:
        for row in await graph_store.execute_read(
            alias_owners_query(), {"merge_keys": sorted(merge_keys)}
        ):
            owner_map.setdefault(str(row["merge_key"]), set()).add(
                str(row["entity_id"])
            )
    needs.update(owner for owners in owner_map.values() for owner in owners)
    labels_rows = (
        await graph_store.execute_read(entity_labels_query(), {"ids": sorted(needs)})
        if needs
        else []
    )
    labels = {str(row["id"]): list(row["labels"]) for row in labels_rows}
    result: dict[UUID, dict[str, str | None] | str] = {}
    for record in records:
        row: dict[str, str | None] = {"key": keys[record.id]}
        if record.kind == "entity":
            result[record.id] = row
            continue
        reason: str | None = None
        sides = [("source", record.source_entity_id, record.source_text)]
        if record.kind == "relation":
            sides.append(("target", record.target_entity_id, record.target_text))
        for side, entity_id, text in sides:
            expected_type = (
                record.source_label if side == "source" else record.target_label
            )
            owner, reason = _resolve_endpoint(
                entity_id,
                text,
                owner_map,
                labels,
                schema,
                expected_type=expected_type,
            )
            if reason:
                break
            row[f"{side}_entity_id"] = owner
        result[record.id] = reason or row
    return result
