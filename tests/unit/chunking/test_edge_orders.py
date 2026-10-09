"""Tests for edge orders: each edge under a parent gets its own order."""

from uuid import uuid4

from agrag.chunking._edge_orders import EdgeOrders


class TestEdgeOrders:
    """Order reservation under one parent and across parents."""

    def test_returns_the_requested_order_when_free(self) -> None:
        """Check the order returned for the call sequence."""
        orders = EdgeOrders()
        parent = uuid4()

        assert orders.take(parent, 3) == 3

    def test_moves_to_the_next_free_order_under_the_same_parent(self) -> None:
        """Check the order returned for the call sequence."""
        orders = EdgeOrders()
        parent = uuid4()
        orders.take(parent, 3)
        orders.take(parent, 4)

        assert orders.take(parent, 3) == 5

    def test_a_different_parent_does_not_share_orders(self) -> None:
        """Check the order returned for the call sequence."""
        orders = EdgeOrders()
        orders.take(uuid4(), 3)

        assert orders.take(uuid4(), 3) == 3
