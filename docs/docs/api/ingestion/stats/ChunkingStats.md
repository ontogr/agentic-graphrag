---
title: agrag.ingestion.stats.ChunkingStats
sidebar_label: ChunkingStats
---

# `agrag.ingestion.stats.ChunkingStats` \{#agrag-ingestion-stats-ChunkingStats}

Bases: <code>BaseModel</code>

Chunking-stage results.

**Attributes:**

- [**chunks_by_strategy**](#agrag-ingestion-stats-ChunkingStats-chunks_by_strategy) (<code>dict\[str, int\]</code>) – Chunk counts per chunker name, so chunks that a fallback
  made are counted under `<strategy>:<fallback>`.
- [**documents_by_rule**](#agrag-ingestion-stats-ChunkingStats-documents_by_rule) (<code>dict\[str, int\]</code>) – Document counts per rule, keyed `"rule 0"`,
  `"rule 1"` and so on, and `"fallback"`.
- [**matches**](#agrag-ingestion-stats-ChunkingStats-matches) (<code>list\[[ChunkingMatch](chunking/ChunkingMatch.md)\]</code>) – One entry per chunked document, capped at 1000.
- [**matches_total**](#agrag-ingestion-stats-ChunkingStats-matches_total) (<code>int</code>) – Matches recorded before capping.
- [**matches_truncated**](#agrag-ingestion-stats-ChunkingStats-matches_truncated) (<code>bool</code>) – Whether `matches` was cut to the cap.

**Functions:**

- [**from_matches**](#agrag-ingestion-stats-ChunkingStats-from_matches) – Summarize per-document matches.

## `chunks_by_strategy` \{#agrag-ingestion-stats-ChunkingStats-chunks_by_strategy}

```python
chunks_by_strategy: dict[str, int] = Field(default_factory=dict)
```

## `documents_by_rule` \{#agrag-ingestion-stats-ChunkingStats-documents_by_rule}

```python
documents_by_rule: dict[str, int] = Field(default_factory=dict)
```

## `from_matches` \{#agrag-ingestion-stats-ChunkingStats-from_matches}

```python
from_matches(matches:list[ChunkingMatch]) -> ChunkingStats
```

Summarize per-document matches.

**Parameters:**

- **matches** (<code>list\[[ChunkingMatch](chunking/ChunkingMatch.md)\]</code>) – One match per chunked document, in chunking order.

**Returns:**

- <code>[ChunkingStats](chunking/ChunkingStats.md)</code> – The counters over all matches and the matches up to the cap.

## `matches` \{#agrag-ingestion-stats-ChunkingStats-matches}

```python
matches: list[ChunkingMatch] = Field(default_factory=list)
```

## `matches_total` \{#agrag-ingestion-stats-ChunkingStats-matches_total}

```python
matches_total: int = 0
```

## `matches_truncated` \{#agrag-ingestion-stats-ChunkingStats-matches_truncated}

```python
matches_truncated: bool = False
```
