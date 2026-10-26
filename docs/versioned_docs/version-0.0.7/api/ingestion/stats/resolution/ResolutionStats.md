---
title: agrag.ingestion.stats.resolution.ResolutionStats
sidebar_label: ResolutionStats
---

# `agrag.ingestion.stats.resolution.ResolutionStats` \{#agrag-ingestion-stats-resolution-ResolutionStats}

Bases: <code>BaseModel</code>

Resolution-stage results.

**Attributes:**

- [**exact_match_hits**](#agrag-ingestion-stats-resolution-ResolutionStats-exact_match_hits) (<code>int</code>) – Mentions that matched an already-persisted
  entity via the global exact-match tier.
- [**in_batch_groups**](#agrag-ingestion-stats-resolution-ResolutionStats-in_batch_groups) (<code>int</code>) – Groups of two or more mentions from this batch that
  the fuzzy, embedding, or LLM tier formed. Unmatched mentions are
  not groups.
- [**ambiguous_count**](#agrag-ingestion-stats-resolution-ResolutionStats-ambiguous_count) (<code>int</code>) – LLM answers that were uncertain, missing, or
  malformed. These pairs are never merged.
- [**failed_llm_requests**](#agrag-ingestion-stats-resolution-ResolutionStats-failed_llm_requests) (<code>int</code>) – LLM verification requests that raised. Their
  pairs stay undecided and are not merged.
- [**cap_truncated_pairs**](#agrag-ingestion-stats-resolution-ResolutionStats-cap_truncated_pairs) (<code>int</code>) – Ambiguous pairs over the per-label
  `max_llm_pairs` cap. They never reached the LLM.
- [**llm_unavailable_pairs**](#agrag-ingestion-stats-resolution-ResolutionStats-llm_unavailable_pairs) (<code>int</code>) – Ambiguous pairs skipped because no LLM
  settings were found.
- [**batches_done**](#agrag-ingestion-stats-resolution-ResolutionStats-batches_done) (<code>int</code>) – Resolver request batches completed so far.
- [**batches_total**](#agrag-ingestion-stats-resolution-ResolutionStats-batches_total) (<code>int</code>) – Total resolver request batches.
- [**elapsed_seconds**](#agrag-ingestion-stats-resolution-ResolutionStats-elapsed_seconds) (<code>float</code>) – Time spent resolving, in seconds.

## `ambiguous_count` \{#agrag-ingestion-stats-resolution-ResolutionStats-ambiguous_count}

```python
ambiguous_count: int = 0
```

## `batches_done` \{#agrag-ingestion-stats-resolution-ResolutionStats-batches_done}

```python
batches_done: int = 0
```

## `batches_total` \{#agrag-ingestion-stats-resolution-ResolutionStats-batches_total}

```python
batches_total: int = 0
```

## `cap_truncated_pairs` \{#agrag-ingestion-stats-resolution-ResolutionStats-cap_truncated_pairs}

```python
cap_truncated_pairs: int = 0
```

## `elapsed_seconds` \{#agrag-ingestion-stats-resolution-ResolutionStats-elapsed_seconds}

```python
elapsed_seconds: float = 0.0
```

## `exact_match_hits` \{#agrag-ingestion-stats-resolution-ResolutionStats-exact_match_hits}

```python
exact_match_hits: int = 0
```

## `failed_llm_requests` \{#agrag-ingestion-stats-resolution-ResolutionStats-failed_llm_requests}

```python
failed_llm_requests: int = 0
```

## `in_batch_groups` \{#agrag-ingestion-stats-resolution-ResolutionStats-in_batch_groups}

```python
in_batch_groups: int = 0
```

## `llm_unavailable_pairs` \{#agrag-ingestion-stats-resolution-ResolutionStats-llm_unavailable_pairs}

```python
llm_unavailable_pairs: int = 0
```
