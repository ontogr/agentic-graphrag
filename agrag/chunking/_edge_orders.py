"""Distinct edge orders under each parent node."""

from uuid import UUID


class EdgeOrders:
    """Hands out edge orders that no other edge under the same parent holds.

    Two chunks can have the same reading position under one section. Each edge
    needs its own order, so a taken order moves to the next free one.
    """

    def __init__(self) -> None:
        """Start with no order taken."""
        self._taken: set[tuple[UUID, int]] = set()

    def take(self, parent: UUID, order: int) -> int:
        """Reserve an order under a parent.

        Args:
            parent: The node the edge hangs under.
            order: The order the edge would like to have.

        Returns:
            ``order``, or the first larger order that no edge under ``parent``
            has taken yet.
        """
        while (parent, order) in self._taken:
            order += 1
        self._taken.add((parent, order))
        return order
