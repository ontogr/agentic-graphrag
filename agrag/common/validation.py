"""Validation helpers shared across storage backends."""


def require_positive_batch_size(batch_size: int) -> None:
    """Check that a backend write's ``batch_size`` is usable.

    Every backend chunks writes with ``range(0, len(records), batch_size)``.
    A non-positive value breaks that: zero raises ``ValueError`` from
    ``range`` itself, and a negative value silently produces an empty range,
    skipping every record without error.

    Args:
        batch_size: The batch size to check.

    Raises:
        ValueError: ``batch_size`` is not positive.
    """
    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive, got {batch_size}")
