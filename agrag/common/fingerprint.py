"""A short stable hash of a JSON-safe value."""

import hashlib
import json


def fingerprint_of(value: object) -> str:
    """Return a short stable hash of a JSON-safe value.

    Args:
        value: Data made of dicts, lists, strings, numbers, booleans and ``None``.

    Returns:
        The first 16 hex characters of the SHA-256 of the canonical JSON. Keys
        are sorted at every depth, so key order never changes the result. List
        order does.
    """
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
