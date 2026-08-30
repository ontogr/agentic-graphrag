"""Validation helpers shared across storage backends."""

import urllib.parse
from collections.abc import Collection


_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


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
