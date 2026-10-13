"""Helpers that match the same entity mention across extractors."""


def endpoint_key(text: str) -> str:
    """Return the key that matches two mentions of the same entity.

    The key folds case and collapses runs of whitespace, so ``"Acme  Corp"``
    and ``"acme corp"`` give the same key.

    Args:
        text: The surface text of a mention.

    Returns:
        The normalized key of the mention.
    """
    return " ".join(text.casefold().split())
