"""The escalation summary of a Graph.add() or Graph.update() call."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, Field


class EscalationReport(BaseModel):
    """How many chunks the LLM extractor read, and how many it left alone.

    The first extractor reads every chunk. A chunk is eligible for the LLM
    extractor when that first result is weak. The escalation budget then caps
    how many eligible chunks the LLM extractor reads, weakest first. All counts
    cover the chunks of one run. A run with several batches merges the batch
    reports.

    Attributes:
        mode: The effective extraction mode of the run. A run with no LLM
            extractor reports ``gliner``.
        total: The chunks that the run extracted from.
        skipped_short: In ``llm`` mode, the chunks under ``min_escalation_words``
            words that were not sent to the LLM extractor. Zero in other modes.
        eligible: The chunks whose first result was weak enough to escalate.
        escalated: The eligible chunks that the LLM extractor was called on.
        left_for_gliner: The eligible chunks that kept the first result because
            the budget ran out.
        lowest_score_left: The lowest span score among the chunks counted in
            ``left_for_gliner``, or ``None`` when no such chunk has a score.
        failed: The escalated chunks that kept the first result because the
            LLM call raised, its answer did not parse, or it parsed to no
            entities while the first result had some. Counted inside
            ``escalated``.
        budget_needed: The smallest ``escalation_budget`` that escalates every
            eligible chunk, as a share of the chunks in a batch. For a run of
            several batches it is the largest need of any one batch, because
            the budget applies to each batch on its own.
        primary_seconds: Wall-clock seconds the first extractor spent on all
            chunks, summed over batches.
        escalation_seconds: Wall-clock seconds the LLM extractor spent, summed
            over batches.
    """

    mode: Literal["gliner", "hybrid", "llm"] = "gliner"
    total: int = Field(default=0, ge=0)
    skipped_short: int = Field(default=0, ge=0)
    eligible: int = Field(default=0, ge=0)
    escalated: int = Field(default=0, ge=0)
    left_for_gliner: int = Field(default=0, ge=0)
    lowest_score_left: float | None = None
    failed: int = Field(default=0, ge=0)
    budget_needed: float = Field(default=0.0, ge=0.0)
    primary_seconds: float = Field(default=0.0, ge=0.0)
    escalation_seconds: float = Field(default=0.0, ge=0.0)

    @classmethod
    def merge(cls, reports: Iterable[EscalationReport]) -> EscalationReport:
        """Combine the reports of several batches into one.

        Args:
            reports: One report per batch.

        Returns:
            The mode of the batches (one run has one mode), the summed counts
            and seconds, the lowest ``lowest_score_left`` of any batch, and the
            largest ``budget_needed`` of any batch. No reports give the empty
            report.
        """
        batches = list(reports)
        lows = [r.lowest_score_left for r in batches if r.lowest_score_left is not None]
        return cls(
            mode=batches[0].mode if batches else "gliner",
            total=sum(r.total for r in batches),
            skipped_short=sum(r.skipped_short for r in batches),
            eligible=sum(r.eligible for r in batches),
            escalated=sum(r.escalated for r in batches),
            left_for_gliner=sum(r.left_for_gliner for r in batches),
            lowest_score_left=min(lows, default=None),
            failed=sum(r.failed for r in batches),
            budget_needed=max((r.budget_needed for r in batches), default=0.0),
            primary_seconds=sum(r.primary_seconds for r in batches),
            escalation_seconds=sum(r.escalation_seconds for r in batches),
        )
