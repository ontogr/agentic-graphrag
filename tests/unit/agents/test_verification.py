"""Validate verdict statuses and evidence defaults for verifier responses."""

from typing import Any

import pytest
from pydantic import ValidationError

from agrag.agents.verification import VerificationResult


class TestVerificationResult:
    """VerificationResult validates its status literal."""

    @pytest.mark.parametrize("status", ["PASS", "INSUFFICIENT", "CONTRADICTORY"])
    def test_valid_status_values_accepted(self, status: str) -> None:
        """Each documented verdict constructs."""
        result = VerificationResult(
            reasoning="checked every sub-question", status=status
        )
        assert result.status == status

    def test_invalid_status_rejected(self) -> None:
        """A value outside the three literals is a validation error."""
        data: dict[str, Any] = {
            "reasoning": "checked",
            "status": "MAYBE",
        }
        with pytest.raises(ValidationError):
            VerificationResult(**data)
