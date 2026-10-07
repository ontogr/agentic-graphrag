---
title: agrag.ingestion.stats.ResolutionStats
sidebar_label: ResolutionStats
---

# `agrag.ingestion.stats.ResolutionStats` \{#agrag-ingestion-stats-ResolutionStats}

Bases: <code>BaseModel</code>

Resolution-stage results.

**Attributes:**

- [**exact_match_hits**](#agrag-ingestion-stats-ResolutionStats-exact_match_hits) (<code>int</code>) – Mentions that matched an already-persisted
  entity via the global exact-match tier.
- [**in_batch_groups**](#agrag-ingestion-stats-ResolutionStats-in_batch_groups) (<code>int</code>) – Resolution groups the in-batch fuzzy/LLM tier
  found.
- [**ambiguous_count**](#agrag-ingestion-stats-ResolutionStats-ambiguous_count) (<code>int</code>) – Comparisons no comparator could confidently
  decide. These pairs are never merged.

## `ambiguous_count` \{#agrag-ingestion-stats-ResolutionStats-ambiguous_count}

```python
ambiguous_count: int = 0
```

## `exact_match_hits` \{#agrag-ingestion-stats-ResolutionStats-exact_match_hits}

```python
exact_match_hits: int = 0
```

## `in_batch_groups` \{#agrag-ingestion-stats-ResolutionStats-in_batch_groups}

```python
in_batch_groups: int = 0
```
