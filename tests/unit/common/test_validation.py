"""Tests for the shared guard functions in agrag.common.validation.

Covers require_encrypted_remote_connection's default posture (a remote
plaintext connection is allowed unless it carries a credential, since a
schemeless or unparsable URL is deliberately not flagged) versus its
stricter ``require_encryption=True`` mode (rejects any remote plaintext
connection, credential or not, while still allowing loopback hosts), and
and require_positive_batch_size enforcing its numeric contract, parametrized
over valid and invalid values.
"""

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

    def test_no_credential_allowed_by_default(self) -> None:
        """Without require_encryption, no credential means nothing secret leaks.

        Many production deployments run an unauthenticated backend on a
        private network and rely on network segmentation rather than
        transport encryption; this check cannot tell that apart from a
        public host from the URL alone, so it is opt-in via
        require_encryption rather than the default.
        """
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
            url="example.remote.network",
            has_credential=True,
            encrypted_schemes={"https"},
        )

    def test_require_encryption_allows_loopback_without_credential(self) -> None:
        """require_encryption still allows a loopback host with no credential."""
        require_encrypted_remote_connection(
            url="http://localhost:6333",
            has_credential=False,
            encrypted_schemes={"https"},
            require_encryption=True,
        )

    def test_require_encryption_allows_encrypted_remote_without_credential(
        self,
    ) -> None:
        """require_encryption allows an encrypted remote host with no credential."""
        require_encrypted_remote_connection(
            url="https://example.com:6333",
            has_credential=False,
            encrypted_schemes={"https"},
            require_encryption=True,
        )

    def test_require_encryption_rejects_remote_plaintext_without_credential(
        self,
    ) -> None:
        """require_encryption rejects plaintext to a remote host even without one.

        This is the opt-in stricter posture: a deployment that wants every
        non-local connection encrypted, not just ones carrying a credential.
        """
        with pytest.raises(ValueError, match="unencrypted"):
            require_encrypted_remote_connection(
                url="http://example.com:6333",
                has_credential=False,
                encrypted_schemes={"https"},
                require_encryption=True,
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
