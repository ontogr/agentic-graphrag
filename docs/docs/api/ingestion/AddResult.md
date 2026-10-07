---
title: agrag.ingestion.AddResult
sidebar_label: AddResult
---

# `agrag.ingestion.AddResult` \{#agrag-ingestion-AddResult}

Bases: <code>BaseModel</code>

Graph.add()'s return type — one summary per pipeline stage.

**Attributes:**

- [**ingestion**](#agrag-ingestion-AddResult-ingestion) (<code>[IngestStats](stats/IngestStats.md)</code>) – Ingestion-stage results.
- [**chunking**](#agrag-ingestion-AddResult-chunking) (<code>[ChunkingStats](stats/ChunkingStats.md)</code>) – The chunker each document got and the chunks it made.
- [**extraction**](#agrag-ingestion-AddResult-extraction) (<code>[ExtractionStats](stats/ExtractionStats.md)</code>) – Extractor output across every chunk this call
  processed.
- [**resolution**](#agrag-ingestion-AddResult-resolution) (<code>[ResolutionStats](stats/ResolutionStats.md)</code>) – Resolution's tier-by-tier match counts.
- [**merge**](#agrag-ingestion-AddResult-merge) (<code>[MergeStats](stats/MergeStats.md)</code>) – What merge mechanics did with resolution's groups.
- [**storage**](#agrag-ingestion-AddResult-storage) (<code>[StorageStats](stats/StorageStats.md)</code>) – What made it to GraphStore, and what didn't.
- [**chunks**](#agrag-ingestion-AddResult-chunks) (<code>list\[[Chunk](../common/data_models/chunk/Chunk-ref.md)\]</code>) – Every Chunk this call produced. Empty unless
  return_chunks=True — holding full chunk text for a large
  corpus is a real memory cost most callers don't need paid
  for.

## `chunking` \{#agrag-ingestion-AddResult-chunking}

```python
chunking: ChunkingStats = Field(default_factory=ChunkingStats)
```

## `chunks` \{#agrag-ingestion-AddResult-chunks}

```python
chunks: list[Chunk] = Field(default_factory=list)
```

## `documents` \{#agrag-ingestion-AddResult-documents}

```python
documents: int
```

Proxy to ingestion.documents for backward compatibility.

## `extraction` \{#agrag-ingestion-AddResult-extraction}

```python
extraction: ExtractionStats = Field(default_factory=ExtractionStats)
```

## `ingestion` \{#agrag-ingestion-AddResult-ingestion}

```python
ingestion: IngestStats = Field(default_factory=IngestStats)
```

## `merge` \{#agrag-ingestion-AddResult-merge}

```python
merge: MergeStats = Field(default_factory=MergeStats)
```

## `quarantined` \{#agrag-ingestion-AddResult-quarantined}

```python
quarantined: int
```

Proxy to ingestion.quarantined for backward compatibility.

## `quarantined_items` \{#agrag-ingestion-AddResult-quarantined_items}

```python
quarantined_items: list[StageFailure]
```

Proxy to ingestion.quarantined_items for backward compatibility.

## `resolution` \{#agrag-ingestion-AddResult-resolution}

```python
resolution: ResolutionStats = Field(default_factory=ResolutionStats)
```

## `skipped` \{#agrag-ingestion-AddResult-skipped}

```python
skipped: int
```

Proxy to ingestion.skipped for backward compatibility.

## `sources` \{#agrag-ingestion-AddResult-sources}

```python
sources: int
```

Proxy to ingestion.sources for backward compatibility.

## `storage` \{#agrag-ingestion-AddResult-storage}

```python
storage: StorageStats = Field(default_factory=StorageStats)
```
