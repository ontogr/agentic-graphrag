"""Link and write candidates for one ingestion batch."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from uuid import NAMESPACE_OID, UUID, uuid5

from agrag.common.data_models.candidate import CandidateRecord
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.stage_failure import StageFailure
from agrag.common.text import normalize_text
from agrag.ingestion._stage_context import StageContext
from agrag.ingestion._storage import upsert_stage_failures
from agrag.loaders.types import ErrorPolicy
from agrag.observability import record_stage_failure


@dataclass(frozen=True)
class CandidateStageResult:
    """The outcome of one batch's candidate write.

    Attributes:
        written: Candidate nodes created by the store.
        skipped: Candidate occurrences not written because they were reviewed
            or became a relation self-loop.
        failures: Failures from the settled-key read or candidate write.
    """

    written: int = 0
    skipped: int = 0
    failures: list[StageFailure] = field(default_factory=list)


def candidate_node_id(job_id: UUID | None, chunk_id: UUID, key: str) -> UUID:
    """Return the deterministic candidate id for a job, chunk and key."""
    return uuid5(NAMESPACE_OID, f"Candidate:{job_id}:{chunk_id}:{key}")


def _mention_positions(
    entities: Sequence[ExtractedEntity],
) -> dict[tuple[UUID, str], int]:
    """Map each chunk and normalized mention text to its first position."""
    positions: dict[tuple[UUID, str], int] = {}
    for position, entity in enumerate(entities):
        positions.setdefault((entity.chunk_id, normalize_text(entity.text)), position)
    return positions


def _end(
    chunk_id: UUID,
    text: str | None,
    entities: Sequence[ExtractedEntity],
    positions: Mapping[tuple[UUID, str], int],
    mention_to_entity: Mapping[int, UUID],
) -> tuple[UUID | None, str | None]:
    if text is None:
        return None, None
    position = positions.get((chunk_id, normalize_text(text)))
    if position is None:
        return None, None
    return mention_to_entity.get(position), entities[position].label


def _link(
    candidate: CandidateRecord,
    entities: Sequence[ExtractedEntity],
    positions: Mapping[tuple[UUID, str], int],
    mention_to_entity: Mapping[int, UUID],
) -> CandidateRecord | None:
    """Link one candidate to final entities, or skip a merged self-loop."""
    if candidate.kind == "entity":
        return candidate
    source_id, source_label = _end(
        candidate.chunk_id,
        candidate.source_text,
        entities,
        positions,
        mention_to_entity,
    )
    target_id, target_label = (
        _end(
            candidate.chunk_id,
            candidate.target_text,
            entities,
            positions,
            mention_to_entity,
        )
        if candidate.kind == "relation"
        else (None, None)
    )
    if (
        candidate.kind == "relation"
        and source_id is not None
        and source_id == target_id
    ):
        return None
    return candidate.model_copy(
        update={
            "source_entity_id": source_id,
            "target_entity_id": target_id,
            "source_label": source_label,
            "target_label": target_label,
        }
    )


def _aggregate(
    linked: Sequence[CandidateRecord], *, job_id: UUID | None, schema_fingerprint: str
) -> dict[str, CandidateRecord]:
    """Aggregate linked candidates by their authoritative record key."""
    merged: dict[str, CandidateRecord] = {}
    for candidate in linked:
        key = candidate.key
        held = merged.get(key)
        if held is None:
            merged[key] = candidate.model_copy(
                update={
                    "id": candidate_node_id(job_id, candidate.chunk_id, key),
                    "schema_fingerprint": schema_fingerprint,
                }
            )
            continue
        merged[key] = held.model_copy(
            update={
                "count": held.count + candidate.count,
                "confidence": max(held.confidence, candidate.confidence),
            }
        )
    return merged


def _failure(item_id: str, exc: Exception) -> StageFailure:
    trace_id, span_id = record_stage_failure(exc)
    return StageFailure(
        item_id=item_id,
        error_type=type(exc).__name__,
        error_message=str(exc),
        trace_id=trace_id,
        span_id=span_id,
    )


async def candidate_stage(
    candidates: Sequence[CandidateRecord],
    entities: Sequence[ExtractedEntity],
    mention_to_entity: Mapping[int, UUID],
    ctx: StageContext,
    *,
    schema_fingerprint: str,
    enabled: bool,
) -> CandidateStageResult:
    """Link, aggregate and write candidates for one batch.

    The call runs after chunk, entity and relation writes, so its evidence and
    entity links refer to nodes in the current cutover job.

    Args:
        candidates: Items the extractor discarded in this batch.
        entities: Mentions indexed by the merge stage's final entity map.
        mention_to_entity: Final entity IDs keyed by mention index.
        ctx: Storage, job, tracing and failure policy for this batch.
        schema_fingerprint: Schema used to extract the candidates.
        enabled: Whether to write candidates. False performs no storage calls.

    Returns:
        Written nodes, skipped occurrences and storage failures.

    Raises:
        Exception: A storage call fails when the error policy is ``RAISE``.
    """
    if not enabled or not candidates:
        return CandidateStageResult()
    positions = _mention_positions(entities)
    linked: list[CandidateRecord] = []
    skipped = 0
    for candidate in candidates:
        item = _link(candidate, entities, positions, mention_to_entity)
        if item is None:
            skipped += candidate.count
        else:
            linked.append(item)
    merged = _aggregate(
        linked, job_id=ctx.job_id, schema_fingerprint=schema_fingerprint
    )
    if not merged:
        return CandidateStageResult(skipped=skipped)
    with ctx.tracer.start_as_current_span(
        "agrag.storage.upsert_candidates",
        attributes={"agrag.record_count": len(merged)},
    ) as span:
        try:
            blocked = await ctx.graph_store.blocked_candidate_keys(list(merged))
            fresh = [record for key, record in merged.items() if key not in blocked]
            skipped += sum(
                record.count for key, record in merged.items() if key in blocked
            )
            if not fresh:
                return CandidateStageResult(skipped=skipped)
            outcome = await ctx.graph_store.upsert_candidates(
                fresh, pending_job_id=ctx.job_id
            )
        except Exception as exc:
            if ctx.error_policy is ErrorPolicy.RAISE:
                raise
            return CandidateStageResult(
                skipped=skipped, failures=[_failure("candidates", exc)]
            )
        span.set_attribute("agrag.candidates_written", outcome.written)
    return CandidateStageResult(
        written=outcome.written,
        skipped=skipped,
        failures=upsert_stage_failures(outcome),
    )
