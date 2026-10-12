---
title: agrag.ingestion.resolve.resolver.ResolutionResult
sidebar_label: ResolutionResult
---

# `agrag.ingestion.resolve.resolver.ResolutionResult` \{#agrag-ingestion-resolve-resolver-ResolutionResult}

Bases: <code>BaseModel</code>

The groups, non-exact evidence, and failure counts of one pass.

**Attributes:**

- [**groups**](#agrag-ingestion-resolve-resolver-ResolutionResult-groups) (<code>list\[[ResolutionGroup](ResolutionGroup.md)\]</code>) – One group per transitively connected mention set.
- [**matches**](#agrag-ingestion-resolve-resolver-ResolutionResult-matches) (<code>list\[[ResolvedMatch](ResolvedMatch.md)\]</code>) – Evidence for every confirmed non-exact pair.
- [**ambiguous_count**](#agrag-ingestion-resolve-resolver-ResolutionResult-ambiguous_count) (<code>int</code>) – LLM answers that were uncertain, missing, or
  malformed. These pairs never merge.
- [**failed_llm_requests**](#agrag-ingestion-resolve-resolver-ResolutionResult-failed_llm_requests) (<code>int</code>) – LLM verification requests that errored. Their
  pairs are undecided.
- [**cap_truncated_pairs**](#agrag-ingestion-resolve-resolver-ResolutionResult-cap_truncated_pairs) (<code>int</code>) – Boundary pairs that never reached the LLM
  because of the per-label pair cap. They are undecided.
- [**llm_unavailable_pairs**](#agrag-ingestion-resolve-resolver-ResolutionResult-llm_unavailable_pairs) (<code>int</code>) – Boundary pairs skipped because no LLM
  settings were found or the resolver has no LLM comparator.
- [**unresolved_pairs**](#agrag-ingestion-resolve-resolver-ResolutionResult-unresolved_pairs) (<code>list\[tuple\[int, int\]\]</code>) – Every pair the resolver could not decide, sorted as
  `(left_index, right_index)` with the lower index first.

## `ambiguous_count` \{#agrag-ingestion-resolve-resolver-ResolutionResult-ambiguous_count}

```python
ambiguous_count: int = 0
```

## `cap_truncated_pairs` \{#agrag-ingestion-resolve-resolver-ResolutionResult-cap_truncated_pairs}

```python
cap_truncated_pairs: int = 0
```

## `failed_llm_requests` \{#agrag-ingestion-resolve-resolver-ResolutionResult-failed_llm_requests}

```python
failed_llm_requests: int = 0
```

## `groups` \{#agrag-ingestion-resolve-resolver-ResolutionResult-groups}

```python
groups: list[ResolutionGroup]
```

## `llm_unavailable_pairs` \{#agrag-ingestion-resolve-resolver-ResolutionResult-llm_unavailable_pairs}

```python
llm_unavailable_pairs: int = 0
```

## `matches` \{#agrag-ingestion-resolve-resolver-ResolutionResult-matches}

```python
matches: list[ResolvedMatch]
```

## `unresolved_pairs` \{#agrag-ingestion-resolve-resolver-ResolutionResult-unresolved_pairs}

```python
unresolved_pairs: list[tuple[int, int]] = Field(default_factory=list)
```
