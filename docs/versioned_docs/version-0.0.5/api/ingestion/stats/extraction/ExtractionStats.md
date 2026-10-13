---
title: agrag.ingestion.stats.extraction.ExtractionStats
sidebar_label: ExtractionStats
---

# `agrag.ingestion.stats.extraction.ExtractionStats` \{#agrag-ingestion-stats-extraction-ExtractionStats}

Bases: <code>BaseModel</code>

Extraction-stage results.

**Attributes:**

- [**chunks_processed**](#agrag-ingestion-stats-extraction-ExtractionStats-chunks_processed) (<code>int</code>) – Chunks the stage read. In `llm` mode this counts
  every chunk, including chunks skipped for having fewer than
  `min_escalation_words` words. `EscalationReport.skipped_short`
  gives that skipped count.
- [**entities_extracted**](#agrag-ingestion-stats-extraction-ExtractionStats-entities_extracted) (<code>int</code>) – Entities the extractor returned.
- [**relations_extracted**](#agrag-ingestion-stats-extraction-ExtractionStats-relations_extracted) (<code>int</code>) – Relations the extractor returned.
- [**dropped**](#agrag-ingestion-stats-extraction-ExtractionStats-dropped) (<code>list\[[DroppedCount](../dropped/DroppedCount.md)\]</code>) – Extractor discards counted by kind, label and reason. Always
  filled, whether candidates are on or off.
- [**candidates_written**](#agrag-ingestion-stats-extraction-ExtractionStats-candidates_written) (<code>int</code>) – Candidates this run wrote to the graph.
- [**candidates_skipped**](#agrag-ingestion-stats-extraction-ExtractionStats-candidates_skipped) (<code>int</code>) – Discarded items not written because a reviewer
  settled the key or both relation ends merged into one entity.
- [**failures**](#agrag-ingestion-stats-extraction-ExtractionStats-failures) (<code>list\[[StageFailure](../../../common/data_models/stage_failure/StageFailure.md)\]</code>) – Per-item failures, capped per call.
- [**failures_total**](#agrag-ingestion-stats-extraction-ExtractionStats-failures_total) (<code>int</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag-ingestion-stats-extraction-ExtractionStats-failures_truncated) (<code>bool</code>) – Whether `failures` was cut to the cap.

## `candidates_skipped` \{#agrag-ingestion-stats-extraction-ExtractionStats-candidates_skipped}

```python
candidates_skipped: int = 0
```

## `candidates_written` \{#agrag-ingestion-stats-extraction-ExtractionStats-candidates_written}

```python
candidates_written: int = 0
```

## `chunks_processed` \{#agrag-ingestion-stats-extraction-ExtractionStats-chunks_processed}

```python
chunks_processed: int = 0
```

## `dropped` \{#agrag-ingestion-stats-extraction-ExtractionStats-dropped}

```python
dropped: list[DroppedCount] = Field(default_factory=list)
```

## `entities_extracted` \{#agrag-ingestion-stats-extraction-ExtractionStats-entities_extracted}

```python
entities_extracted: int = 0
```

## `failures` \{#agrag-ingestion-stats-extraction-ExtractionStats-failures}

```python
failures: list[StageFailure] = Field(default_factory=list)
```

## `failures_total` \{#agrag-ingestion-stats-extraction-ExtractionStats-failures_total}

```python
failures_total: int = 0
```

## `failures_truncated` \{#agrag-ingestion-stats-extraction-ExtractionStats-failures_truncated}

```python
failures_truncated: bool = False
```

## `relations_extracted` \{#agrag-ingestion-stats-extraction-ExtractionStats-relations_extracted}

```python
relations_extracted: int = 0
```
