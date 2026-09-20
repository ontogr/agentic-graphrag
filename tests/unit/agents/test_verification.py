"""Tests for the verifier's structured verdict model."""

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

    def test_missing_evidence_defaults_to_empty_list(self) -> None:
        """missing_evidence needs no value for PASS verdicts."""
        result = VerificationResult(reasoning="all cited", status="PASS")
        assert result.missing_evidence == []

    def test_missing_evidence_round_trips(self) -> None:
        """An INSUFFICIENT verdict carries the gaps to close."""
        result = VerificationResult(
            reasoning="two sub-questions uncited",
            status="INSUFFICIENT",
            missing_evidence=["founding date", "board members"],
        )
        assert result.missing_evidence == ["founding date", "board members"]
