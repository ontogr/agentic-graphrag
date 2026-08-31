"""Shared text normalization used across resolution and merge-key computation."""


def normalize_text(text: str) -> str:
    """Return text stripped and case-folded for identity comparison.

    Args:
        text: The text to normalize.

    Returns:
        The stripped, case-folded text.
    """
    return text.strip().casefold()
