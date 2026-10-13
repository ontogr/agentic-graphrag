---
title: agrag.ingestion.reports.escalation_report.EscalationReport
sidebar_label: EscalationReport
---

# `agrag.ingestion.reports.escalation_report.EscalationReport` \{#agrag-ingestion-reports-escalation_report-EscalationReport}

Bases: <code>BaseModel</code>

How many chunks the LLM extractor read, and how many it left alone.

The first extractor reads every chunk. A chunk is eligible for the LLM
extractor when that first result is weak. The escalation budget then caps
how many eligible chunks the LLM extractor reads, weakest first. All counts
cover the chunks of one run. A run with several batches merges the batch
reports.

**Attributes:**

- [**mode**](#agrag-ingestion-reports-escalation_report-EscalationReport-mode) (<code>Literal['gliner', 'hybrid', 'llm']</code>) – The effective extraction mode of the run. A run with no LLM
  extractor reports `gliner`.
- [**total**](#agrag-ingestion-reports-escalation_report-EscalationReport-total) (<code>int</code>) – The chunks that the run extracted from.
- [**skipped_short**](#agrag-ingestion-reports-escalation_report-EscalationReport-skipped_short) (<code>int</code>) – In `llm` mode, the chunks under `min_escalation_words`
  words that were not sent to the LLM extractor. Zero in other modes.
- [**eligible**](#agrag-ingestion-reports-escalation_report-EscalationReport-eligible) (<code>int</code>) – The chunks whose first result was weak enough to escalate.
  Zero in `llm` mode, which has no first result to judge.
- [**escalated**](#agrag-ingestion-reports-escalation_report-EscalationReport-escalated) (<code>int</code>) – The chunks that the LLM extractor was called on. In `llm`
  mode these are the chunks that were not skipped short.
- [**left_for_gliner**](#agrag-ingestion-reports-escalation_report-EscalationReport-left_for_gliner) (<code>int</code>) – The eligible chunks that kept the first result because
  the budget ran out.
- [**lowest_score_left**](#agrag-ingestion-reports-escalation_report-EscalationReport-lowest_score_left) (<code>float | None</code>) – The lowest span score among the chunks counted in
  `left_for_gliner`, or `None` when no such chunk has a score.
- [**failed**](#agrag-ingestion-reports-escalation_report-EscalationReport-failed) (<code>int</code>) – The escalated chunks that kept the first result because the
  LLM call raised, its answer did not parse, or it parsed to no
  entities while the first result had some. Counted inside
  `escalated`.
- [**budget_needed**](#agrag-ingestion-reports-escalation_report-EscalationReport-budget_needed) (<code>float</code>) – The smallest `escalation_budget` that escalates every
  eligible chunk, as a share of the chunks in a batch. For a run of
  several batches it is the largest need of any one batch, because
  the budget applies to each batch on its own.
- [**primary_seconds**](#agrag-ingestion-reports-escalation_report-EscalationReport-primary_seconds) (<code>float</code>) – Wall-clock seconds the first extractor spent on all
  chunks, summed over batches.
- [**escalation_seconds**](#agrag-ingestion-reports-escalation_report-EscalationReport-escalation_seconds) (<code>float</code>) – Wall-clock seconds the LLM extractor spent, summed
  over batches.

**Functions:**

- [**merge**](#agrag-ingestion-reports-escalation_report-EscalationReport-merge) – Combine the reports of several batches into one.

## `budget_needed` \{#agrag-ingestion-reports-escalation_report-EscalationReport-budget_needed}

```python
budget_needed: float = Field(default=0.0, ge=0.0)
```

## `eligible` \{#agrag-ingestion-reports-escalation_report-EscalationReport-eligible}

```python
eligible: int = Field(default=0, ge=0)
```

## `escalated` \{#agrag-ingestion-reports-escalation_report-EscalationReport-escalated}

```python
escalated: int = Field(default=0, ge=0)
```

## `escalation_seconds` \{#agrag-ingestion-reports-escalation_report-EscalationReport-escalation_seconds}

```python
escalation_seconds: float = Field(default=0.0, ge=0.0)
```

## `failed` \{#agrag-ingestion-reports-escalation_report-EscalationReport-failed}

```python
failed: int = Field(default=0, ge=0)
```

## `left_for_gliner` \{#agrag-ingestion-reports-escalation_report-EscalationReport-left_for_gliner}

```python
left_for_gliner: int = Field(default=0, ge=0)
```

## `lowest_score_left` \{#agrag-ingestion-reports-escalation_report-EscalationReport-lowest_score_left}

```python
lowest_score_left: float | None = None
```

## `merge` \{#agrag-ingestion-reports-escalation_report-EscalationReport-merge}

```python
merge(reports:Iterable[EscalationReport]) -> EscalationReport
```

Combine the reports of several batches into one.

**Parameters:**

- **reports** (<code>Iterable\[EscalationReport\]</code>) – One report per batch.

**Returns:**

- <code>EscalationReport</code> – The mode of the batches (one run has one mode), the summed counts
- <code>EscalationReport</code> – and seconds, the lowest `lowest_score_left` of any batch, and the
- <code>EscalationReport</code> – largest `budget_needed` of any batch. No reports give the empty
- <code>EscalationReport</code> – report.

## `mode` \{#agrag-ingestion-reports-escalation_report-EscalationReport-mode}

```python
mode: Literal['gliner', 'hybrid', 'llm'] = 'gliner'
```

## `primary_seconds` \{#agrag-ingestion-reports-escalation_report-EscalationReport-primary_seconds}

```python
primary_seconds: float = Field(default=0.0, ge=0.0)
```

## `skipped_short` \{#agrag-ingestion-reports-escalation_report-EscalationReport-skipped_short}

```python
skipped_short: int = Field(default=0, ge=0)
```

## `total` \{#agrag-ingestion-reports-escalation_report-EscalationReport-total}

```python
total: int = Field(default=0, ge=0)
```
