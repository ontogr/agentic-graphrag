"""Validation helpers shared across storage backends."""

import urllib.parse
from collections.abc import Collection


_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# The result-window ceiling a VectorStore.search/hybrid_search `limit` is held
# to across every backend, so an out-of-range value fails the same way
# everywhere instead of erroring on one backend and silently truncating or
# succeeding on another. Set to Milvus's own query/search result-window
# limit, the tightest of the three backends this project supports.
MAX_SEARCH_LIMIT = 16384


def require_encrypted_remote_connection(
    *, url: str, has_credential: bool, encrypted_schemes: Collection[str]
) -> None:
    """Reject a plaintext connection to a non-local host carrying a credential.

    A scheme outside ``encrypted_schemes`` sends everything on the
    connection, including any configured credential, unencrypted. That is
    the normal, safe shape of local development against a Docker Compose
    service on localhost, but the same plaintext default pointed at a real
    remote host would leak credentials and data to network interception.
    Loopback hosts are always allowed, regardless of scheme or credential.

    Args:
        url: The connection URL or URI to check.
        has_credential: Whether a credential (API key, token, password) is
            configured for this connection.
        encrypted_schemes: The URL schemes considered encrypted for this
            backend, for example ``{"https"}`` or ``{"bolt+s", "neo4j+s"}``.

    Raises:
        ValueError: ``url`` uses a scheme outside ``encrypted_schemes``, its
            host is not loopback, and ``has_credential`` is ``True``.
    """
    if not has_credential:
        return
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in encrypted_schemes:
        return
    if parsed.hostname is None or parsed.hostname in _LOOPBACK_HOSTS:
        return
    raise ValueError(
        f"{url!r} uses an unencrypted scheme ({parsed.scheme!r}) but sends a "
        f"configured credential to a non-local host; use one of "
        f"{sorted(encrypted_schemes)} instead"
    )


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


def require_valid_search_limit(limit: int) -> None:
    """Check that a search/hybrid_search ``limit`` is usable across every backend.

    Backends fail differently outside this range: Milvus raises for a
    non-positive ``limit`` or one above ``MAX_SEARCH_LIMIT`` (its own
    query/search result-window ceiling), while Qdrant and Weaviate may
    instead return an empty or silently truncated result. Enforcing the
    tightest bound uniformly means a given ``limit`` either works, or fails
    the same way, regardless of which backend is configured.

    Args:
        limit: The requested maximum number of hits.

    Raises:
        ValueError: ``limit`` is not a positive integer, or exceeds
            ``MAX_SEARCH_LIMIT``.
    """
    if limit <= 0:
        raise ValueError(f"limit must be positive, got {limit}")
    if limit > MAX_SEARCH_LIMIT:
        raise ValueError(f"limit must be at most {MAX_SEARCH_LIMIT}, got {limit}")


def require_valid_alpha(alpha: float) -> None:
    """Check that a ``hybrid_search`` ``alpha`` is a valid dense/keyword weight.

    ``alpha`` is only meaningful in ``[0.0, 1.0]``: ``1.0`` is pure dense,
    ``0.0`` is pure keyword. Outside that range, backends behave
    differently: Qdrant's client-side blend still produces a
    mathematically well-defined but meaningless score, while a backend's
    native ranker may reject the value outright.

    Args:
        alpha: The dense/keyword balance to check.

    Raises:
        ValueError: ``alpha`` is outside ``[0.0, 1.0]``.
    """
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be between 0.0 and 1.0, got {alpha}")
