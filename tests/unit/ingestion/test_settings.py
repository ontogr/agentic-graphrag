"""Check ingestion settings through environment and dotenv configuration."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from agrag.ingestion.settings import (
    CutoverJobSettings,
    ExtractionSettings,
    effective_mode,
)


class TestCutoverJobSettings:
    """Cutover job configuration validation."""

    def test_rejects_non_positive_lease_ttl(self) -> None:
        """A lease must stay live for a positive duration."""
        with pytest.raises(ValueError, match="greater than 0"):
            CutoverJobSettings(lease_ttl_seconds=0)


@pytest.fixture
def clean_extraction_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Use an isolated working directory with no extraction variables."""
    monkeypatch.chdir(tmp_path)
    for name in list(os.environ):
        if name.startswith("EXTRACTION_"):
            monkeypatch.delenv(name)
    return tmp_path


@pytest.mark.usefixtures("clean_extraction_env")
class TestExtractionSettings:
    """Extraction settings read valid environment and dotenv configuration."""

    def test_uses_contract_defaults(self) -> None:
        """Settings provide the agreed defaults for local extraction."""
        settings = ExtractionSettings()

        assert settings.mode == "hybrid"
        assert settings.model_name == "fastino/gliner2.5-base-v1"
        assert settings.dtype == "fp32"
        assert settings.entity_threshold == 0.5
        assert settings.relation_threshold == 0.7
        assert settings.relation_floor == 0.3
        assert settings.band_floor == 0.3
        assert settings.label_thresholds == {}
        assert settings.escalation_threshold == 0.75
        assert settings.escalation_budget == 0.2
        assert settings.min_escalation_words == 8
        assert settings.candidates_enabled is True

    def test_reads_scalar_overrides_from_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Environment values override scalar settings with typed values."""
        monkeypatch.setenv("EXTRACTION_MODEL_NAME", "fastino/gliner2.5-small-v1")
        monkeypatch.setenv("EXTRACTION_DTYPE", "bf16")
        monkeypatch.setenv("EXTRACTION_ENTITY_THRESHOLD", "0.6")
        monkeypatch.setenv("EXTRACTION_MIN_ESCALATION_WORDS", "12")
        monkeypatch.setenv("EXTRACTION_CANDIDATES_ENABLED", "false")

        settings = ExtractionSettings()

        assert settings.model_name == "fastino/gliner2.5-small-v1"
        assert settings.dtype == "bf16"
        assert settings.entity_threshold == 0.6
        assert settings.min_escalation_words == 12
        assert settings.candidates_enabled is False

    def test_reads_overrides_from_dotenv(self, tmp_path: Path) -> None:
        """A working-directory .env file supplies extraction configuration."""
        (tmp_path / ".env").write_text(
            "EXTRACTION_ENTITY_THRESHOLD=0.7\n"
            'EXTRACTION_LABEL_THRESHOLDS={"Person": 0.8}\n'
        )

        settings = ExtractionSettings()

        assert settings.entity_threshold == 0.7
        assert settings.label_thresholds == {"Person": 0.8}

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("0.35", 0.35), ("0", 0.0), ("1", 1.0), ("all", "all")],
    )
    def test_parses_escalation_budget_from_environment(
        self, monkeypatch: pytest.MonkeyPatch, raw: str, expected: float | str
    ) -> None:
        """Budget accepts a fraction or the word all from the environment."""
        monkeypatch.setenv("EXTRACTION_ESCALATION_BUDGET", raw)

        assert ExtractionSettings().escalation_budget == expected

    def test_parses_label_threshold_map_from_json_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A JSON environment value becomes the per-label threshold map."""
        monkeypatch.setenv(
            "EXTRACTION_LABEL_THRESHOLDS", '{"Person": 0.7, "Location": 0.4}'
        )

        assert ExtractionSettings().label_thresholds == {
            "Person": 0.7,
            "Location": 0.4,
        }

    def test_rejects_invalid_label_threshold_json(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Malformed JSON fails while settings are loaded."""
        monkeypatch.setenv("EXTRACTION_LABEL_THRESHOLDS", "Person=0.7")

        with pytest.raises(SettingsError):
            ExtractionSettings()

    @pytest.mark.parametrize("value", [1.5, -0.1])
    def test_rejects_out_of_range_label_thresholds(self, value: float) -> None:
        """Per-label scores must stay between zero and one."""
        with pytest.raises(ValidationError):
            ExtractionSettings(label_thresholds={"Person": value})

    def test_rejects_unknown_dtype(self) -> None:
        """Only fp32, fp16 and bf16 are valid model precisions."""
        with pytest.raises(ValidationError):
            ExtractionSettings(dtype="int8")

    @pytest.mark.parametrize(
        "overrides",
        [
            {"entity_threshold": 1.5},
            {"relation_threshold": -0.1},
            {"escalation_threshold": 2.0},
            {"escalation_budget": 1.5},
            {"escalation_budget": -0.1},
            {"escalation_budget": "most"},
            {"min_escalation_words": -1},
        ],
    )
    def test_rejects_invalid_ranges(self, overrides: dict[str, object]) -> None:
        """Scores and budgets stay in range, and word counts are non-negative."""
        with pytest.raises(ValidationError):
            ExtractionSettings(**overrides)

    def test_rejects_relation_floor_above_threshold(self) -> None:
        """The minimum returned relation score cannot exceed the keep threshold."""
        with pytest.raises(ValidationError, match="relation_floor"):
            ExtractionSettings(relation_floor=0.8, relation_threshold=0.7)

    def test_rejects_band_floor_above_entity_threshold(self) -> None:
        """The lower entity band cannot exceed the keep threshold."""
        with pytest.raises(ValidationError, match="band_floor"):
            ExtractionSettings(band_floor=0.6, entity_threshold=0.5)

    @pytest.mark.parametrize("value", ["local", "GLiNER", "", "llm_only", "all"])
    def test_rejects_unknown_mode(self, value: str) -> None:
        """Mode accepts only gliner, hybrid, or llm."""
        with pytest.raises(ValidationError):
            ExtractionSettings(**{"mode": value})

    @pytest.mark.parametrize("value", ["gliner", "hybrid", "llm"])
    def test_reads_mode_from_environment(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """EXTRACTION_MODE selects the configured extraction mode."""
        monkeypatch.setenv("EXTRACTION_MODE", value)

        assert ExtractionSettings().mode == value

    def test_ignores_extraction_llm_variables_in_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LLM-prefixed settings do not become extraction settings."""
        monkeypatch.setenv("EXTRACTION_LLM_STRATEGY", "round_robin")
        monkeypatch.setenv("EXTRACTION_LLM_CLIENTS", "[]")

        settings = ExtractionSettings()

        assert settings.entity_threshold == 0.5
        assert set(settings.model_dump()) == set(ExtractionSettings.model_fields)

    def test_ignores_extraction_llm_variables_in_dotenv(self, tmp_path: Path) -> None:
        """LLM-prefixed .env entries are ignored while extraction entries load."""
        (tmp_path / ".env").write_text(
            "EXTRACTION_LLM_STRATEGY=fallback\nEXTRACTION_ENTITY_THRESHOLD=0.7\n"
        )

        settings = ExtractionSettings()

        assert settings.entity_threshold == 0.7
        assert set(settings.model_dump()) == set(ExtractionSettings.model_fields)

    def test_has_no_llm_prefixed_field_names(self) -> None:
        """No field can collide with EXTRACTION_LLM_ variable names."""
        assert not any(
            name.startswith("llm_") for name in ExtractionSettings.model_fields
        )


class TestEffectiveMode:
    """Effective mode degrades only hybrid mode without an LLM."""

    @pytest.mark.parametrize(
        ("mode", "llm_available", "expected"),
        [
            ("gliner", False, "gliner"),
            ("gliner", True, "gliner"),
            ("hybrid", True, "hybrid"),
            ("hybrid", False, "gliner"),
            ("llm", True, "llm"),
            ("llm", False, "llm"),
        ],
    )
    def test_only_hybrid_degrades_without_llm(
        self, mode: str, llm_available: bool, expected: str
    ) -> None:
        """Only hybrid becomes gliner when no LLM is available."""
        assert effective_mode(ExtractionSettings(mode=mode), llm_available) == expected
