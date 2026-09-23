"""Tests for Cutover Job configuration."""

import pytest

from agrag.ingestion.settings import CutoverJobSettings


class TestCutoverJobSettings:
    """Cutover Job configuration validation."""

    def test_rejects_non_positive_lease_ttl(self) -> None:
        """A lease must stay live for a positive duration."""
        with pytest.raises(ValueError, match="greater than 0"):
            CutoverJobSettings(lease_ttl_seconds=0)
