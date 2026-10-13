"""Helpers that match entity mentions across extractors and locate them in chunks.

``endpoint_key`` and ``mention_key`` normalize mention text for comparison.
``locate_mentions`` finds where each reported mention sits in the chunk text,
so the code, not the model, sets the offsets.
"""

import re
from collections.abc import Sequence


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


def mention_key(text: str) -> str:
    """Return text with every run of whitespace collapsed to one space.

    Chunks keep the line breaks of their source, while a model usually
    answers on one line. Comparing by this key lets both spellings match.

    Args:
        text: A mention as the model wrote it, or as the chunk holds it.

    Returns:
        The text without leading or trailing space and with single spaces
        between words. Empty when text holds only whitespace.
    """
    return " ".join(text.split())


def _occurrences(key: str, chunk_text: str) -> list[tuple[int, int]]:
    """Return the (start, end) of each whole-word match of key in chunk_text."""
    body = r"\s+".join(re.escape(word) for word in key.split(" "))
    # Both edges need a non-word neighbor, even when the mention edge is
    # punctuation, so "U.S." does not match inside "U.S.A.".
    pattern = r"(?<!\w)" + body + r"(?!\w)"
    return [match.span() for match in re.finditer(pattern, chunk_text)]


def locate_mentions(
    mentions: Sequence[tuple[str, str]], chunk_text: str
) -> list[tuple[int, int] | None]:
    """Return the span in chunk_text of each reported (label, text) mention.

    The model reports names and labels only, so code finds the offsets. A
    mention matches the chunk text case-sensitively, at word boundaries, and
    across any whitespace run. The n-th time the same label and text appear
    in ``mentions``, the result is the n-th occurrence in the chunk; a
    listing past the last occurrence has no span. Two labels on one text
    share the same occurrence, so a name that is both a product and a
    company keeps both labels on one span.

    Args:
        mentions: The model's (label, text) pairs, in answer order.
        chunk_text: The text the model read.

    Returns:
        One entry per mention, in the same order. ``None`` marks a mention
        whose text is empty, is absent from chunk_text, or repeats a text
        the chunk holds fewer times.
    """
    found_by_key: dict[str, list[tuple[int, int]]] = {}
    listed: dict[tuple[str, str], int] = {}
    spans: list[tuple[int, int] | None] = []
    for label, text in mentions:
        key = mention_key(text)
        if not key:
            spans.append(None)
            continue
        if key not in found_by_key:
            found_by_key[key] = _occurrences(key, chunk_text)
        nth = listed.get((label, key), 0)
        listed[(label, key)] = nth + 1
        found = found_by_key[key]
        spans.append(found[nth] if nth < len(found) else None)
    return spans
