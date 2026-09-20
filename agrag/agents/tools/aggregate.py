"""Deterministic arithmetic over numbers the agent has already gathered.

The researcher reads counts and totals off prior tool results into its own
reasoning; this tool exists so the arithmetic on them is exact rather than
recalled from a language model's head. It queries nothing.
"""

from typing import Literal

from langchain_core.tools import tool


def _format(value: float) -> str:
    """Render a computed number without trailing floating-point noise.

    Args:
        value: The number to render.

    Returns:
        The number as text, e.g. ``"2"`` or ``"3.5"``.
    """
    return f"{value:g}"


@tool("compute_over_evidence")
def compute_over_evidence(
    operation: Literal["count", "sum", "compare"],
    values: list[float],
    *,
    compare_op: Literal["gt", "lt", "eq"] | None = None,
) -> str:
    """Compute a count, a sum, or a comparison over numbers you supply.

    Use this instead of doing arithmetic in your head when a question
    asks how many, how much in total, or whether one figure exceeds
    another. It never queries the graph: pass the numbers you have
    already read from earlier tool results.

    Args:
        operation: "count" for how many values you supplied, "sum" for
            their total, "compare" for a comparison between exactly two
            of them.
        values: The numbers to compute over, in the order you read them.
        compare_op: Required for "compare": "gt" for values[0] greater
            than values[1], "lt" for less than, "eq" for equal.
    """
    if operation == "compare":
        if len(values) != 2:
            return (
                "compare needs exactly two values, in the order "
                f"[left, right]; got {len(values)}."
            )
        if compare_op is None:
            return 'compare needs compare_op: one of "gt", "lt", or "eq".'
        left, right = values
        outcomes = {"gt": left > right, "lt": left < right, "eq": left == right}
        return str(outcomes[compare_op]).lower()
    if operation == "count":
        return _format(float(len(values)))
    if operation == "sum":
        return _format(sum(values))
    return f'Unknown operation "{operation}": use count, sum, or compare.'
