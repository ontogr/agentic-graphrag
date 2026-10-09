---
title: agrag.ingestion.stats.extraction.ExtractionStats
sidebar_label: ExtractionStats
---

# `agrag.ingestion.stats.extraction.ExtractionStats` \{#agrag-ingestion-stats-extraction-ExtractionStats}

Bases: <code>BaseModel</code>

Extraction-stage results.

**Attributes:**

- [**chunks_processed**](#agrag-ingestion-stats-extraction-ExtractionStats-chunks_processed) (<code>int</code>) – Chunks the stage ran the extractor on.
- [**entities_extracted**](#agrag-ingestion-stats-extraction-ExtractionStats-entities_extracted) (<code>int</code>) – Entities the extractor returned.
- [**relations_extracted**](#agrag-ingestion-stats-extraction-ExtractionStats-relations_extracted) (<code>int</code>) – Relations the extractor returned.
- [**failures**](#agrag-ingestion-stats-extraction-ExtractionStats-failures) (<code>list\[[StageFailure](../../../common/data_models/stage_failure/StageFailure.md)\]</code>) – Per-item failures, capped per call.
- [**failures_total**](#agrag-ingestion-stats-extraction-ExtractionStats-failures_total) (<code>int</code>) – Failures recorded before capping.
- [**failures_truncated**](#agrag-ingestion-stats-extraction-ExtractionStats-failures_truncated) (<code>bool</code>) – Whether `failures` was cut to the cap.

## `chunks_processed` \{#agrag-ingestion-stats-extraction-ExtractionStats-chunks_processed}

```python
chunks_processed: int = 0
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
