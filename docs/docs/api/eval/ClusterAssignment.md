---
title: agrag.eval.ClusterAssignment
sidebar_label: ClusterAssignment
---

# `agrag.eval.ClusterAssignment` \{#agrag-eval-ClusterAssignment}

Bases: <code>BaseModel</code>

A grouping of mentions, listed by position in the mention list.

**Attributes:**

- [**size**](#agrag-eval-ClusterAssignment-size) (<code>int</code>) – The number of mentions.
- [**clusters**](#agrag-eval-ClusterAssignment-clusters) (<code>list\[list\[int\]\]</code>) – Groups of mention indices. An index in no group is a cluster
  of one.
- [**matches_by_tier**](#agrag-eval-ClusterAssignment-matches_by_tier) (<code>dict\[str, int\]</code>) – How many confirmed non-exact matches each comparator
  made. Empty for gold clusters.
- [**failed_llm_requests**](#agrag-eval-ClusterAssignment-failed_llm_requests) (<code>int</code>) – LLM verification requests that errored and were
  mapped to "no match". Zero on gold clusters.

## `clusters` \{#agrag-eval-ClusterAssignment-clusters}

```python
clusters: list[list[int]]
```

## `failed_llm_requests` \{#agrag-eval-ClusterAssignment-failed_llm_requests}

```python
failed_llm_requests: int = 0
```

## `matches_by_tier` \{#agrag-eval-ClusterAssignment-matches_by_tier}

```python
matches_by_tier: dict[str, int] = {}
```

## `size` \{#agrag-eval-ClusterAssignment-size}

```python
size: int
```
