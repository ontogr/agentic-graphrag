"""Tests for compute_over_evidence in agrag.agents.tools.aggregate.

The tool is stateless and queries nothing, so every test is a direct call.
Covers the three operations, the two-value/compare_op requirements of
"compare", and that a malformed call gets a readable message rather than a
Python traceback.
"""

from agrag.agents.tools.aggregate import compute_over_evidence


class TestComputeOverEvidence:
    """compute_over_evidence does exact arithmetic on supplied numbers."""

    def test_count_ignores_value_contents(self) -> None:
        """Count reports how many values there are, not what they are."""
        assert (
            compute_over_evidence.invoke(
                {"operation": "count", "values": [99.0, -1.5, 0.0]}
            )
            == "3"
        )

    def test_count_of_nothing(self) -> None:
        """An empty list counts as zero."""
        assert compute_over_evidence.invoke({"operation": "count", "values": []}) == "0"

    def test_sum(self) -> None:
        """Sum adds the values."""
        assert (
            compute_over_evidence.invoke(
                {"operation": "sum", "values": [1.5, 2.0, 0.5]}
            )
            == "4"
        )

    def test_sum_avoids_floating_point_noise(self) -> None:
        """Sum of 0.1 and 0.2 reads as 0.3, not 0.30000000000000004."""
        assert (
            compute_over_evidence.invoke({"operation": "sum", "values": [0.1, 0.2]})
            == "0.3"
        )

    def test_compare_gt(self) -> None:
        """Compare with gt reports whether the first value is greater."""
        assert (
            compute_over_evidence.invoke(
                {"operation": "compare", "values": [3.0, 2.0], "compare_op": "gt"}
            )
            == "true"
        )
        assert (
            compute_over_evidence.invoke(
                {"operation": "compare", "values": [2.0, 3.0], "compare_op": "gt"}
            )
            == "false"
        )

    def test_compare_lt(self) -> None:
        """Compare with lt reports whether the first value is smaller."""
        assert (
            compute_over_evidence.invoke(
                {"operation": "compare", "values": [2.0, 3.0], "compare_op": "lt"}
            )
            == "true"
        )

    def test_compare_eq(self) -> None:
        """Compare with eq reports whether the values are equal."""
        assert (
            compute_over_evidence.invoke(
                {"operation": "compare", "values": [2.0, 2.0], "compare_op": "eq"}
            )
            == "true"
        )

    def test_compare_requires_two_values(self) -> None:
        """One or three values get a clear message, not an IndexError."""
        for values in ([1.0], [1.0, 2.0, 3.0]):
            rendered = compute_over_evidence.invoke(
                {"operation": "compare", "values": values, "compare_op": "gt"}
            )
            assert "exactly two values" in rendered

    def test_compare_requires_compare_op(self) -> None:
        """Compare without compare_op says which argument is missing."""
        rendered = compute_over_evidence.invoke(
            {"operation": "compare", "values": [1.0, 2.0]}
        )

        assert "compare_op" in rendered
