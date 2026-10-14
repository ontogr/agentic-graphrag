"""Configuration for ingestion: the Cutover Job and local extraction."""

from typing import Annotated, Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_Score = Annotated[float, Field(ge=0, le=1)]


class CutoverJobSettings(BaseSettings):
    """Configuration for the Cutover Job crash-recovery machine.

    Attributes:
        lease_ttl_seconds: How long a worker lease stays valid before another
            worker can take it. Env: CUTOVER_JOB_LEASE_TTL_SECONDS.

    Env prefix: ``CUTOVER_JOB_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="CUTOVER_JOB_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    lease_ttl_seconds: int = Field(default=60, gt=0)


class ExtractionSettings(BaseSettings):
    """Configuration for local entity and relation extraction.

    Every score is between 0 and 1. ``ExtractionLLMSettings`` variables start
    with ``EXTRACTION_LLM_`` and are not read here, so no field may start with
    ``llm_``.

    The entity and relation thresholds, the relation floor, the entity band and
    the candidate switch shape what ``GlinerExtractor`` keeps and reports.
    The escalation threshold, budget and minimum word count decide which weak
    chunks go to the LLM extractor in ``hybrid`` mode.

    Attributes:
        mode: Extractor mode. ``gliner`` runs GLiNER only; ``hybrid`` runs
            GLiNER and may escalate weak chunks to the LLM; ``llm`` runs the
            LLM on every chunk. Escalation settings apply only to ``hybrid``.
            This mode does not control entity resolution. Resolution has its
            own optional LLM tier, which runs whenever LLM settings exist, even
            in ``gliner`` mode.
        model_name: GLiNER checkpoint.
        dtype: Model precision: ``fp32``, ``fp16`` or ``bf16``.
        entity_threshold: Minimum score for a kept entity span.
        relation_threshold: Minimum score for a kept relation.
        relation_floor: Minimum relation score returned by the model.
        band_floor: Minimum entity score in the band below the keep threshold.
        label_thresholds: Per-label thresholds keyed by entity or relation label.
            An entity label's threshold replaces ``entity_threshold`` for that
            label. A relation label's threshold replaces ``relation_threshold``
            as the cut for kept relations, and the model reads that relation at
            the lower of the threshold and ``relation_floor``.
        escalation_threshold: Entity score below which a chunk may use the LLM.
        escalation_budget: LLM chunk share from 0 to 1, or ``"all"`` for no
            limit.
        min_escalation_words: Minimum words for a chunk with no entities to
            use the LLM.
        candidates_enabled: Whether discarded items are kept as candidates.

    Env prefix: ``EXTRACTION_``. ``label_thresholds`` uses one JSON object,
    such as ``EXTRACTION_LABEL_THRESHOLDS='{"Person": 0.7}'``.
    """

    model_config = SettingsConfigDict(
        env_prefix="EXTRACTION_",
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
        # model_name uses the pydantic "model_" namespace.
        protected_namespaces=(),
    )

    mode: Literal["gliner", "hybrid", "llm"] = "hybrid"
    model_name: str = "fastino/gliner2.5-base-v1"
    dtype: Literal["fp32", "fp16", "bf16"] = "fp32"
    entity_threshold: _Score = 0.5
    relation_threshold: _Score = 0.7
    relation_floor: _Score = 0.3
    band_floor: _Score = 0.3
    label_thresholds: dict[str, _Score] = Field(default_factory=dict)
    escalation_threshold: _Score = 0.75
    escalation_budget: _Score | Literal["all"] = 0.2
    min_escalation_words: int = Field(default=8, ge=0)
    candidates_enabled: bool = True

    @model_validator(mode="after")
    def _validate_floors(self) -> "ExtractionSettings":
        """Reject a floor above the threshold it sits below."""
        if self.relation_floor > self.relation_threshold:
            raise ValueError(
                f"relation_floor ({self.relation_floor}) must not exceed "
                f"relation_threshold ({self.relation_threshold})"
            )
        if self.band_floor > self.entity_threshold:
            raise ValueError(
                f"band_floor ({self.band_floor}) must not exceed "
                f"entity_threshold ({self.entity_threshold})"
            )
        return self


# The prompt id is included in extraction fingerprints; prompt edits must bump it.
EXTRACTION_PROMPT_ID = "llm-prompt-2"


def effective_mode(
    settings: ExtractionSettings, llm_available: bool
) -> Literal["gliner", "hybrid", "llm"]:
    """Return the run mode, degrading hybrid to GLiNER when no LLM is available.

    Args:
        settings: Settings for the run.
        llm_available: Whether an LLM extractor can serve the run.

    Returns:
        The mode the run uses.
    """
    if settings.mode == "hybrid" and not llm_available:
        return "gliner"
    return settings.mode
