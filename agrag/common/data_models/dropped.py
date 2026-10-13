"""Counts of items discarded during extraction or merge."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from agrag.common.data_models.candidate import CandidateRecord


DroppedKind = Literal["entity", "relation", "property"]
DroppedReason = Literal[
    "off_pattern",
    "below_relation_cut",
    "unresolved_endpoint",
    "entity_band",
    "property",
    "unmapped_endpoint",
    "merged_self_loop",
    "schema_validation",
]
_DropKey = tuple[DroppedKind, str, DroppedReason]


class DroppedCount(BaseModel):
    """Count items removed by one rule for one label.

    Attributes:
        kind: Whether the item was an entity, relation or property.
        label: The entity label, relation label or property key.
        reason: The rule that removed the item.
        count: The number of items removed.
        chunk_id: The source chunk when the count belongs to one extraction.
    """

    kind: DroppedKind
    label: str
    reason: DroppedReason
    count: int = Field(gt=0)
    chunk_id: UUID | None = None


def _counts(counter: Counter[_DropKey]) -> list[DroppedCount]:
    """Turn a counter into a sorted list of counts."""
    return [
        DroppedCount(kind=kind, label=label, reason=reason, count=count)
        for (kind, label, reason), count in sorted(counter.items())
    ]


def count_candidates(candidates: Iterable[CandidateRecord]) -> list[DroppedCount]:
    """Count extractor candidates by kind, label and reason."""
    counter: Counter[_DropKey] = Counter()
    for candidate in candidates:
        counter[(candidate.kind, candidate.label, candidate.reason)] += candidate.count
    return _counts(counter)


def sum_dropped(groups: Iterable[Sequence[DroppedCount]]) -> list[DroppedCount]:
    """Sum dropped counts from several groups."""
    counter: Counter[_DropKey] = Counter()
    for group in groups:
        for item in group:
            counter[(item.kind, item.label, item.reason)] += item.count
    return _counts(counter)
