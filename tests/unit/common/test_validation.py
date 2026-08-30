"""Tests for validation helpers shared across storage backends."""

import pytest

from agrag.common.validation import (
    require_encrypted_remote_connection,
    require_positive_batch_size,
)


class TestRequireEncryptedRemoteConnection:
    """require_encrypted_remote_connection guards against leaking credentials."""

    def test_loopback_host_always_allowed(self) -> None:
        """A loopback host is fine regardless of scheme or credential."""
        require_encrypted_remote_connection(
            url="http://localhost:6333",
            has_credential=True,
            encrypted_schemes={"https"},
        )

    def test_no_credential_always_allowed(self) -> None:
        """No credential means nothing secret travels in the clear."""
        require_encrypted_remote_connection(
            url="http://example.com:6333",
            has_credential=False,
            encrypted_schemes={"https"},
        )

    def test_encrypted_scheme_always_allowed(self) -> None:
        """An encrypted scheme is fine for a remote host with a credential."""
        require_encrypted_remote_connection(
            url="https://example.com:6333",
            has_credential=True,
            encrypted_schemes={"https"},
        )

    def test_remote_plaintext_with_credential_raises(self) -> None:
        """A remote host, plaintext scheme, and a credential together raise."""
        with pytest.raises(ValueError, match="unencrypted"):
            require_encrypted_remote_connection(
                url="http://example.com:6333",
                has_credential=True,
                encrypted_schemes={"https"},
            )

    def test_schemeless_url_is_not_flagged(self) -> None:
        """A URL urlparse cannot resolve a host from is not flagged.

        Conservative by design: this only rejects connections it can
        positively identify as plaintext to a non-local host.
        """
        require_encrypted_remote_connection(
            url="example.weaviate.network",
            has_credential=True,
            encrypted_schemes={"https"},
        )


class TestRequirePositiveBatchSize:
    """require_positive_batch_size guards every backend's batching contract."""

    @pytest.mark.parametrize("batch_size", [1, 256, 10_000])
    def test_accepts_positive_values(self, batch_size: int) -> None:
        """A positive batch size passes without error."""
        require_positive_batch_size(batch_size)

    def test_rejects_zero(self) -> None:
        """Zero would raise from range() itself; reject it with a clear error."""
        with pytest.raises(ValueError):
            require_positive_batch_size(0)

    def test_rejects_negative(self) -> None:
        """A negative value would silently skip every record via range()."""
        with pytest.raises(ValueError):
            require_positive_batch_size(-1)
