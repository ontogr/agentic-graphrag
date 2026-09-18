"""Exact-name grouping for permanent raw entity records."""

from collections import defaultdict

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.text import normalize_text
from agrag.ingestion.resolve.resolver import ResolutionGroup


def exact_resolution_groups(
    mentions: list[ExtractedEntity], exact_matches: dict[int, Entity]
) -> list[ResolutionGroup]:
    """Group mentions only when they share exact raw-entity identity.

    A mention with a persisted exact match joins every other mention that
    resolves to the same raw Entity. Other mentions join only when their
    labels and normalized names match. Semantic matches deliberately remain
    separate raw records and are materialized through ``MATCHES`` later.
    """
    by_identity: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, mention in enumerate(mentions):
        existing = exact_matches.get(index)
        identity = (
            ("entity", str(existing.id))
            if existing is not None
            else ("name", f"{mention.label}:{normalize_text(mention.text)}")
        )
        by_identity[identity].append(index)
    return [
        ResolutionGroup(entity_indices=indices)
        for _, indices in sorted(by_identity.items(), key=lambda item: item[1][0])
    ]
