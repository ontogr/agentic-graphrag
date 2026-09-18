"""Non-destructive semantic match decisions between raw entities."""

from datetime import UTC, datetime
from uuid import NAMESPACE_OID, UUID, uuid5

from pydantic import BaseModel, Field


def matches_id(left_entity_id: UUID, right_entity_id: UUID) -> UUID:
    """Return the order-independent identifier for a raw entity match edge."""
    left, right = sorted((str(left_entity_id), str(right_entity_id)))
    return uuid5(NAMESPACE_OID, f"matches:{left}:{right}")


class MatchDecision(BaseModel):
    """Evidence supporting an active semantic match between two raw entities.

    Attributes:
        id: Stable, order-independent relationship identifier.
        left_entity_id: One raw entity endpoint.
        right_entity_id: The other raw entity endpoint.
        comparator: The matching strategy that confirmed the pair.
        score: Numeric similarity evidence when available.
        reasoning: Natural-language evidence when available.
        decided_at: When the comparator confirmed the match.
        active: Whether this match currently contributes to a component.
    """

    id: UUID
    left_entity_id: UUID
    right_entity_id: UUID
    comparator: str
    score: float | None = None
    reasoning: str | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    active: bool = True

    @classmethod
    def create(
        cls,
        *,
        left_entity_id: UUID,
        right_entity_id: UUID,
        comparator: str,
        score: float | None = None,
        reasoning: str | None = None,
    ) -> "MatchDecision":
        """Create a decision with a stable relationship identifier.

        Raises:
            ValueError: Both endpoints identify the same raw entity.
        """
        if left_entity_id == right_entity_id:
            raise ValueError("A match decision requires two distinct raw entities.")
        return cls(
            id=matches_id(left_entity_id, right_entity_id),
            left_entity_id=left_entity_id,
            right_entity_id=right_entity_id,
            comparator=comparator,
            score=score,
            reasoning=reasoning,
        )
