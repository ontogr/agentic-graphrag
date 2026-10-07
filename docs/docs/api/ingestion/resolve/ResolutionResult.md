---
title: agrag.ingestion.resolve.ResolutionResult
sidebar_label: ResolutionResult
---

# `agrag.ingestion.resolve.ResolutionResult` \{#agrag-ingestion-resolve-ResolutionResult}

Bases: <code>BaseModel</code>

The groups, non-exact evidence, and ambiguity count of one pass.

**Attributes:**

- [**groups**](#agrag-ingestion-resolve-ResolutionResult-groups) (<code>list\[[ResolutionGroup](resolver/ResolutionGroup.md)\]</code>) – One group per transitively connected mention set.
- [**matches**](#agrag-ingestion-resolve-ResolutionResult-matches) (<code>list\[[ResolvedMatch](resolver/ResolvedMatch.md)\]</code>) – Evidence for every confirmed non-exact pair.
- [**ambiguous_count**](#agrag-ingestion-resolve-ResolutionResult-ambiguous_count) (<code>int</code>) – LLM verdicts that came back uncertain. These
  pairs never merge.
- [**failed_llm_requests**](#agrag-ingestion-resolve-ResolutionResult-failed_llm_requests) (<code>int</code>) – LLM verification requests that errored
  and were mapped to "no match".
- [**cap_truncated_pairs**](#agrag-ingestion-resolve-ResolutionResult-cap_truncated_pairs) (<code>int</code>) – Boundary pairs that never reached the LLM
  because of the per-label pair cap.

## `ambiguous_count` \{#agrag-ingestion-resolve-ResolutionResult-ambiguous_count}

```python
ambiguous_count: int = 0
```

## `cap_truncated_pairs` \{#agrag-ingestion-resolve-ResolutionResult-cap_truncated_pairs}

```python
cap_truncated_pairs: int = 0
```

## `failed_llm_requests` \{#agrag-ingestion-resolve-ResolutionResult-failed_llm_requests}

```python
failed_llm_requests: int = 0
```

## `groups` \{#agrag-ingestion-resolve-ResolutionResult-groups}

```python
groups: list[ResolutionGroup]
```

## `matches` \{#agrag-ingestion-resolve-ResolutionResult-matches}

```python
matches: list[ResolvedMatch]
```
