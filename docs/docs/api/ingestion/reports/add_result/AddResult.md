---
title: agrag.ingestion.reports.add_result.AddResult
sidebar_label: AddResult
---

# `agrag.ingestion.reports.add_result.AddResult` \{#agrag-ingestion-reports-add_result-AddResult}

Bases: <code>BaseModel</code>

Return type of Graph.add(). One summary per pipeline stage.

**Attributes:**

- [**ingestion**](#agrag-ingestion-reports-add_result-AddResult-ingestion) (<code>[IngestStats](../../stats/ingest/IngestStats.md)</code>) – Ingestion-stage results.
- [**chunking**](#agrag-ingestion-reports-add_result-AddResult-chunking) (<code>[ChunkingStats](../../stats/chunking/ChunkingStats.md)</code>) – The chunker each document got and the chunks it made.
- [**extraction**](#agrag-ingestion-reports-add_result-AddResult-extraction) (<code>[ExtractionStats](../../stats/extraction/ExtractionStats.md)</code>) – Extractor output across every chunk this call
  processed.
- [**escalation**](#agrag-ingestion-reports-add_result-AddResult-escalation) (<code>[EscalationReport](../escalation_report/EscalationReport.md)</code>) – How many chunks the LLM extractor read, how many the
  budget left to the first extractor, how many escalations failed,
  and the wall time of each phase. Only the chunk count and the
  first-phase time are set when the graph has no LLM extractor.
- [**resolution**](#agrag-ingestion-reports-add_result-AddResult-resolution) (<code>[ResolutionStats](../../stats/resolution/ResolutionStats.md)</code>) – Resolution's tier-by-tier match counts.
- [**merge**](#agrag-ingestion-reports-add_result-AddResult-merge) (<code>[MergeStats](../../stats/merge/MergeStats.md)</code>) – What merge mechanics did with resolution's groups.
- [**storage**](#agrag-ingestion-reports-add_result-AddResult-storage) (<code>[StorageStats](../../stats/storage/StorageStats.md)</code>) – What made it to GraphStore, and what didn't.
- [**chunks**](#agrag-ingestion-reports-add_result-AddResult-chunks) (<code>list\[[Chunk](../../../common/data_models/chunk/Chunk-ref.md)\]</code>) – Every Chunk this call produced. Empty unless
  return_chunks=True — holding full chunk text for a large
  corpus is a real memory cost most callers don't need paid
  for.

## `chunking` \{#agrag-ingestion-reports-add_result-AddResult-chunking}

```python
chunking: ChunkingStats = Field(default_factory=ChunkingStats)
```

## `chunks` \{#agrag-ingestion-reports-add_result-AddResult-chunks}

```python
chunks: list[Chunk] = Field(default_factory=list)
```

## `escalation` \{#agrag-ingestion-reports-add_result-AddResult-escalation}

```python
escalation: EscalationReport = Field(default_factory=EscalationReport)
```

## `extraction` \{#agrag-ingestion-reports-add_result-AddResult-extraction}

```python
extraction: ExtractionStats = Field(default_factory=ExtractionStats)
```

## `ingestion` \{#agrag-ingestion-reports-add_result-AddResult-ingestion}

```python
ingestion: IngestStats = Field(default_factory=IngestStats)
```

## `merge` \{#agrag-ingestion-reports-add_result-AddResult-merge}

```python
merge: MergeStats = Field(default_factory=MergeStats)
```

## `resolution` \{#agrag-ingestion-reports-add_result-AddResult-resolution}

```python
resolution: ResolutionStats = Field(default_factory=ResolutionStats)
```

## `storage` \{#agrag-ingestion-reports-add_result-AddResult-storage}

```python
storage: StorageStats = Field(default_factory=StorageStats)
```
