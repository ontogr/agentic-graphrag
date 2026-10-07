---
title: agrag.eval.resolution.ClusterAssignment
sidebar_label: ClusterAssignment
---

# `agrag.eval.resolution.ClusterAssignment` \{#agrag-eval-resolution-ClusterAssignment}

Bases: <code>BaseModel</code>

A grouping of mentions, listed by position in the mention list.

**Attributes:**

- [**size**](#agrag-eval-resolution-ClusterAssignment-size) (<code>int</code>) – The number of mentions.
- [**clusters**](#agrag-eval-resolution-ClusterAssignment-clusters) (<code>list\[list\[int\]\]</code>) – Groups of mention indices. An index in no group is a cluster
  of one.
- [**matches_by_tier**](#agrag-eval-resolution-ClusterAssignment-matches_by_tier) (<code>dict\[str, int\]</code>) – How many confirmed non-exact matches each comparator
  made. Empty for gold clusters.
- [**failed_llm_requests**](#agrag-eval-resolution-ClusterAssignment-failed_llm_requests) (<code>int</code>) – LLM verification requests that errored and were
  mapped to "no match". Zero on gold clusters.

## `clusters` \{#agrag-eval-resolution-ClusterAssignment-clusters}

```python
clusters: list[list[int]]
```

## `failed_llm_requests` \{#agrag-eval-resolution-ClusterAssignment-failed_llm_requests}

```python
failed_llm_requests: int = 0
```

## `matches_by_tier` \{#agrag-eval-resolution-ClusterAssignment-matches_by_tier}

```python
matches_by_tier: dict[str, int] = {}
```

## `size` \{#agrag-eval-resolution-ClusterAssignment-size}

```python
size: int
```
